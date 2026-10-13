"use client";

import { useEffect, useRef } from "react";
import { useDispatch } from "react-redux";
import { useSession } from "next-auth/react";
import mqtt, { type MqttClient } from "mqtt";
import { useToast } from "@/shared/hooks/use-toast";
import { getStoredAppSettings } from "@/shared/hooks/useAppSettings";
import { baseApi } from "@/core/api/baseApi";
import {
  receiveRealtimeNotification,
  setMqttConnected,
} from "../store/notificationSlice";
import { type AutoNotification } from "../types";

export const getMqttBrokerUrl = (): string => {
  let url = process.env.NEXT_PUBLIC_MQTT_URL;

  // Lấy host từ NEXT_PUBLIC_BASE_API nếu có
  const baseApiUrl = process.env.NEXT_PUBLIC_BASE_API;
  let apiHost: string | null = null;
  if (baseApiUrl) {
    try {
      apiHost = new URL(baseApiUrl).hostname;
    } catch {
      // ignore
    }
  }

  if (!url) {
    if (apiHost) {
      url = `ws://${apiHost}:1884/mqtt`;
    } else if (typeof window !== "undefined") {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.hostname || "localhost";
      url = `${protocol}//${host}:1884/mqtt`;
    } else {
      url = "ws://localhost:1884/mqtt";
    }
  } else if (
    url.includes("localhost") &&
    apiHost &&
    apiHost !== "localhost" &&
    apiHost !== "127.0.0.1"
  ) {
    // Tự động thay thế localhost bằng remote host từ BASE_API
    url = url.replace("localhost", apiHost).replace("127.0.0.1", apiHost);
  }

  // Đảm bảo URL kết nối qua WebSocket tới broker có path /mqtt
  try {
    const parsed = new URL(url);
    if (!parsed.pathname || parsed.pathname === "/" || parsed.pathname === "") {
      parsed.pathname = "/mqtt";
      url = parsed.toString();
    }
  } catch {
    if (!url.includes("/mqtt")) {
      url = url.replace(/\/?$/, "/mqtt");
    }
  }

  return url;
};

export const getMqttCredentials = () => {
  return {
    username: process.env.NEXT_PUBLIC_MQTT_USERNAME || "admin",
    password: process.env.NEXT_PUBLIC_MQTT_PASSWORD || "Admin@123",
  };
};

// Quản lý singleton client để tránh duplicate connection khi nhiều component mount hook
let globalMqttClient: MqttClient | null = null;
let currentSubscribedUserId: string | null = null;
let activeHookCount = 0;

export function useNotificationSocket() {
  const dispatch = useDispatch();
  const { toast } = useToast();
  const { data: session } = useSession();
  const clientRef = useRef<MqttClient | null>(globalMqttClient);

  const userId = session?.user?.id;

  useEffect(() => {
    if (!userId) {
      if (globalMqttClient) {
        console.info("[MQTT] Người dùng đăng xuất, ngắt kết nối broker...");
        globalMqttClient.end(true);
        globalMqttClient = null;
        currentSubscribedUserId = null;
        dispatch(setMqttConnected(false));
      }
      return;
    }

    activeHookCount += 1;

    // Nếu đã có client đang chạy cho chính user này thì tái sử dụng
    if (globalMqttClient && currentSubscribedUserId === userId) {
      clientRef.current = globalMqttClient;
      return () => {
        activeHookCount = Math.max(0, activeHookCount - 1);
        if (activeHookCount === 0 && globalMqttClient) {
          globalMqttClient.end(true);
          globalMqttClient = null;
          currentSubscribedUserId = null;
          dispatch(setMqttConnected(false));
        }
      };
    }

    // Nếu đổi user khác, dọn dẹp kết nối cũ trước
    if (globalMqttClient && currentSubscribedUserId !== userId) {
      globalMqttClient.end(true);
      globalMqttClient = null;
      currentSubscribedUserId = null;
    }

    const brokerUrl = getMqttBrokerUrl();
    const { username, password } = getMqttCredentials();
    const clientId = `hautoml_web_${userId}_${Math.random().toString(16).slice(2, 8)}`;

    console.info(`[MQTT] Đang kết nối tới broker tại ${brokerUrl} với user_id: ${userId}...`);

    let client: MqttClient;
    try {
      client = mqtt.connect(brokerUrl, {
        clientId,
        username,
        password,
        clean: true,
        reconnectPeriod: 5000,
        connectTimeout: 10000,
        keepalive: 30,
      });

      globalMqttClient = client;
      currentSubscribedUserId = userId;
      clientRef.current = client;
    } catch (err) {
      console.warn("[MQTT] Không thể khởi tạo kết nối MQTT WebSocket:", err);
      return () => {
        activeHookCount = Math.max(0, activeHookCount - 1);
      };
    }

    client.on("connect", () => {
      console.info("[MQTT] Đã kết nối WebSockets thành công!");
      dispatch(setMqttConnected(true));

      // Topic chuẩn backend yêu cầu: f"hautoml/users/{user_id}/notifications"
      const primaryTopic = `hautoml/users/${userId}/notifications`;

      // Các topic dự phòng mở rộng
      const topics = [
        primaryTopic,
        "hautoml/users/+/notifications",
        `automl/users/${userId}/notifications`,
        `autonotifications/${userId}`,
        `notifications/${userId}`,
      ];

      topics.forEach((topic) => {
        client.subscribe(topic, { qos: 1 }, (err) => {
          if (err) {
            console.warn(`[MQTT] Không thể subscribe topic: ${topic}`, err);
          } else {
            console.info(`[MQTT] Đã đăng ký lắng nghe topic: ${topic}`);
          }
        });
      });
    });

    client.on("message", (topic, payload) => {
      try {
        const rawString = payload.toString();
        console.info(`[MQTT] Nhận thông báo mới từ topic [${topic}]:`, rawString);

        let parsed: any;
        try {
          parsed = JSON.parse(rawString);
        } catch {
          parsed = { message: rawString };
        }

        // Kiểm tra đúng user_id (nếu tin nhắn có chỉ định user_id)
        const notifUserId = parsed.user_id || parsed.userId;
        if (
          notifUserId &&
          String(notifUserId) !== String(userId) &&
          !topic.includes(String(userId))
        ) {
          return;
        }

        // Chuẩn hóa trạng thái (1 = thành công, khác 1 = cảnh báo / lỗi)
        let status = 1;
        if (typeof parsed.status === "number") {
          status = parsed.status;
        } else if (typeof parsed.status === "string") {
          const s = parsed.status.toLowerCase();
          status = s === "success" || s === "completed" || s === "1" ? 1 : 0;
        }

        const message =
          parsed.message ||
          parsed.msg ||
          parsed.title ||
          (status === 1
            ? "Mô hình đã được huấn luyện hoàn tất thành công!"
            : "Tác vụ huấn luyện gặp lỗi hoặc sự cố.");

        const jobId = parsed.job_id || parsed.jobId;

        const metadata = parsed.metadata || {
          best_model: parsed.best_model || parsed.bestModel || parsed.model_name,
          best_score: parsed.best_score || parsed.bestScore || parsed.score,
        };

        const notificationId =
          parsed.id ||
          parsed._id ||
          `mqtt_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

        const createdAt = parsed.created_at || parsed.createdAt
          ? typeof (parsed.created_at || parsed.createdAt) === "number"
            ? parsed.created_at || parsed.createdAt
            : Math.floor(Date.now() / 1000)
          : Math.floor(Date.now() / 1000);

        const notificationData: AutoNotification = {
          id: String(notificationId),
          user_id: String(userId),
          job_id: jobId ? String(jobId) : undefined,
          status,
          message,
          metadata,
          is_read: Boolean(parsed.is_read),
          created_at: createdAt,
        };

        // Chèn thông báo vào Redux store để cập nhật Bell UI ngay tức thì
        dispatch(receiveRealtimeNotification(notificationData));

        // Tự động invalidate tag RTK Query để cập nhật bảng Lịch sử (Job) và Notification ngay lập tức
        dispatch(baseApi.util.invalidateTags(["Job", "Notification"]));

        // Kiểm tra cấu hình cài đặt người dùng (Settings)
        const appSettings = getStoredAppSettings();
        if (appSettings.trainingNotifications !== false) {
          const isSuccess = status === 1;
          const bestModel = metadata?.best_model;
          const bestScore = metadata?.best_score;

          let extraDesc = "";
          if (bestModel) {
            extraDesc = ` • Mô hình: ${bestModel}`;
            if (typeof bestScore === "number") {
              extraDesc += ` (${(bestScore * 100).toFixed(1)}%)`;
            }
          }

          toast({
            title: isSuccess ? "🎉 Huấn luyện thành công!" : "⚠️ Huấn luyện gặp sự cố",
            description: `${message}${extraDesc}`,
          });
        }
      } catch (err) {
        console.error("[MQTT] Lỗi phân tích gói tin JSON từ MQTT broker:", err);
      }
    });

    client.on("error", (err) => {
      console.warn("[MQTT] Lỗi kết nối MQTT WebSocket:", err.message);
      dispatch(setMqttConnected(false));
    });

    client.on("close", () => {
      dispatch(setMqttConnected(false));
    });

    client.on("reconnect", () => {
      console.info("[MQTT] Đang thử kết nối lại tới MQTT broker (cổng 1884)...");
    });

    return () => {
      activeHookCount = Math.max(0, activeHookCount - 1);
      if (activeHookCount === 0 && globalMqttClient) {
        globalMqttClient.end(true);
        globalMqttClient = null;
        currentSubscribedUserId = null;
        dispatch(setMqttConnected(false));
      }
    };
  }, [userId, dispatch, toast]);

  return {
    client: clientRef.current,
  };
}
