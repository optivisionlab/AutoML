"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDispatch, useSelector } from "react-redux";
import { useSession } from "next-auth/react";
import {
  Bell,
  CheckCheck,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Loader2,
  Cpu,
  TrendingUp,
} from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/shared/components/ui/popover";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { type RootState } from "@/core/store/store";
import {
  useLazyGetNotificationsQuery,
  useLazyGetUnreadNotificationsQuery,
  useMarkNotificationReadMutation,
} from "@/core/api/notificationApi";
import {
  setInitialNotifications,
  appendNotifications,
  markAsRead,
  markAllAsRead,
  setFilter,
  setLoading,
  setLoadingMore,
} from "../store/notificationSlice";
import { useNotificationSocket } from "../hooks/useNotificationSocket";
import { type AutoNotification } from "../types";

const formatRelativeTime = (timestampInSecondsOrMs: number): string => {
  if (!timestampInSecondsOrMs) return "Vừa xong";
  // Nếu nhỏ hơn 1e11 thì là giây, quy đổi sang ms
  const ms =
    timestampInSecondsOrMs < 1e11
      ? timestampInSecondsOrMs * 1000
      : timestampInSecondsOrMs;

  const diff = Math.max(0, Date.now() - ms);
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "Vừa xong";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} ngày trước`;
  return new Date(ms).toLocaleDateString("vi-VN");
};

export default function NotificationBell() {
  const router = useRouter();
  const dispatch = useDispatch();
  const { data: session } = useSession();

  const userId = session?.user?.id;

  // Kích hoạt kết nối MQTT WebSocket thời gian thực (cổng 1884)
  useNotificationSocket();

  const [isOpen, setIsOpen] = useState(false);

  // Redux state
  const {
    rawNotifications,
    unreadCount,
    hasMore,
    offset,
    limit,
    filter,
    isLoading,
    isLoadingMore,
    mqttConnected,
    isInitialized,
  } = useSelector((state: RootState) => state.notifications);

  // RTK Query API
  const [fetchNotificationsTrigger] = useLazyGetNotificationsQuery();
  const [fetchUnreadNotificationsTrigger] = useLazyGetUnreadNotificationsQuery();
  const [markNotificationReadApi] = useMarkNotificationReadMutation();

  // 1. Tải danh sách thông báo ban đầu khi vào ứng dụng
  useEffect(() => {
    if (!userId || isInitialized) return;

    let isMounted = true;
    const fetchInitialData = async () => {
      dispatch(setLoading(true));
      try {
        const res = await fetchNotificationsTrigger({
          userId,
          offset: 0,
          limit: 10,
        }).unwrap();

        if (isMounted) {
          dispatch(
            setInitialNotifications({
              data: res.data || [],
              unread_count: res.unread_count ?? 0,
              has_more: Boolean(res.has_more),
              filter: "all",
            })
          );
        }
      } catch (err) {
        console.warn("[Notifications] Không thể tải thông báo ban đầu:", err);
        if (isMounted) {
          dispatch(setLoading(false));
        }
      }
    };

    fetchInitialData();

    return () => {
      isMounted = false;
    };
  }, [userId, isInitialized, fetchNotificationsTrigger, dispatch]);

  // 2. Xử lý chuyển tab ("Tất cả" vs "Chưa đọc") theo phong cách Facebook
  const handleTabChange = async (targetFilter: "all" | "unread") => {
    if (filter === targetFilter) return;
    dispatch(setFilter(targetFilter));

    if (!userId) return;

    dispatch(setLoading(true));
    try {
      const fetchFn =
        targetFilter === "unread"
          ? fetchUnreadNotificationsTrigger
          : fetchNotificationsTrigger;

      const res = await fetchFn({
        userId,
        offset: 0,
        limit: 10,
      }).unwrap();

      dispatch(
        setInitialNotifications({
          data: res.data || [],
          unread_count: res.unread_count ?? 0,
          has_more: Boolean(res.has_more),
          filter: targetFilter,
        })
      );
    } catch (err) {
      console.warn("[Notifications] Lỗi khi đổi tab:", err);
      dispatch(setLoading(false));
    }
  };

  // 3. Xử lý cuộn trang vô hạn (Infinite Scroll)
  const handleLoadMore = useCallback(async () => {
    if (!userId || !hasMore || isLoadingMore || isLoading) return;

    dispatch(setLoadingMore(true));
    try {
      const fetchFn =
        filter === "unread"
          ? fetchUnreadNotificationsTrigger
          : fetchNotificationsTrigger;

      const res = await fetchFn({
        userId,
        offset: offset,
        limit: limit || 10,
      }).unwrap();

      dispatch(
        appendNotifications({
          data: res.data || [],
          has_more: Boolean(res.has_more),
        })
      );
    } catch (err) {
      console.warn("[Notifications] Lỗi khi tải thêm thông báo:", err);
      dispatch(setLoadingMore(false));
    }
  }, [
    userId,
    hasMore,
    isLoadingMore,
    isLoading,
    filter,
    offset,
    limit,
    fetchNotificationsTrigger,
    fetchUnreadNotificationsTrigger,
    dispatch,
  ]);

  // Observer theo dõi phần tử sentinel ở đáy danh sách
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen || !hasMore || isLoadingMore || isLoading) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          handleLoadMore();
        }
      },
      { threshold: 0.1 }
    );

    const currentSentinel = sentinelRef.current;
    if (currentSentinel) {
      observer.observe(currentSentinel);
    }

    return () => {
      if (currentSentinel) {
        observer.unobserve(currentSentinel);
      }
    };
  }, [isOpen, hasMore, isLoadingMore, isLoading, handleLoadMore]);

  // 4. Xử lý khi click vào một thông báo
  const handleNotificationClick = async (item: AutoNotification) => {
    // Nếu chưa đọc: Optimistic update giảm unreadCount và gọi API
    if (!item.is_read) {
      dispatch(markAsRead(item.id));
      if (userId) {
        markNotificationReadApi({ notificationId: item.id, userId })
          .unwrap()
          .catch((err) => {
            console.warn("[Notifications] Không thể cập nhật trạng thái đọc:", err);
          });
      }
    }

    // Điều hướng tới chi tiết Job nếu có
    if (item.job_id) {
      setIsOpen(false);
      router.push(`/training-history?highlight=${encodeURIComponent(item.job_id)}`);
    }
  };

  // 5. Đánh dấu tất cả đã đọc
  const handleMarkAllAsRead = async () => {
    if (unreadCount === 0) return;

    dispatch(markAllAsRead());
    if (userId) {
      // Gọi API đọc các thông báo chưa đọc
      const unreadItems = rawNotifications.filter((n) => !n.is_read);
      unreadItems.forEach((n) => {
        markNotificationReadApi({ notificationId: n.id, userId }).catch(() => {});
      });
    }
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="icon"
          className="relative h-10 w-10 rounded-xl border-slate-200/80 bg-white text-slate-600 shadow-none hover:bg-slate-50 hover:text-slate-900 dark:border-white/10 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/15 dark:hover:text-white transition-all active:scale-95"
          aria-label="Notifications"
        >
          <Bell className="h-4.5 w-4.5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] font-black text-white shadow-sm ring-2 ring-white dark:ring-slate-950 animate-in fade-in zoom-in-75">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        sideOffset={8}
        className="w-[360px] sm:w-[420px] p-0 rounded-2xl border-slate-200/90 bg-white shadow-2xl dark:border-white/10 dark:bg-slate-950 backdrop-blur-xl overflow-hidden"
      >
        {/* Header - Thiết kế Facebook Web */}
        <div className="flex items-center justify-between border-b border-slate-100 p-3.5 dark:border-white/10">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Thông báo
            </h3>
            {unreadCount > 0 && (
              <Badge
                variant="secondary"
                className="h-5 px-1.5 text-[11px] font-bold rounded-full bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
              >
                {unreadCount} mới
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-1">
            {unreadCount > 0 && (
              <Button
                variant="ghost"
                size="icon"
                onClick={handleMarkAllAsRead}
                className="h-8 w-8 text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white rounded-lg"
                title="Đánh dấu tất cả đã đọc"
              >
                <CheckCheck className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Tab Lọc theo chuẩn Facebook: [Tất cả] và [Chưa đọc] */}
        <div className="flex items-center gap-2 border-b border-slate-100 px-3.5 py-2 dark:border-white/10">
          <button
            onClick={() => handleTabChange("all")}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-all ${
              filter === "all"
                ? "bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/5"
            }`}
          >
            Tất cả
          </button>
          <button
            onClick={() => handleTabChange("unread")}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-all ${
              filter === "unread"
                ? "bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/5"
            }`}
          >
            Chưa đọc {unreadCount > 0 && `(${unreadCount})`}
          </button>
        </div>

        {/* Danh sách thông báo dạng Facebook */}
        <ScrollArea className="max-h-[380px] min-h-[180px] overflow-y-auto">
          {isLoading && rawNotifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center text-slate-400">
              <Loader2 className="mb-2 h-6 w-6 animate-spin text-blue-500" />
              <p className="text-xs font-medium">Đang tải thông báo...</p>
            </div>
          ) : rawNotifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center text-slate-400 dark:text-slate-500">
              <Bell className="mb-2 h-8 w-8 stroke-[1.5] opacity-40" />
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Không có thông báo nào
              </p>
              <p className="mt-1 text-[11px] opacity-75">
                {filter === "unread"
                  ? "Bạn đã đọc hết tất cả thông báo"
                  : "Các thông báo huấn luyện AutoML sẽ xuất hiện tại đây"}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-white/5">
              {rawNotifications.map((item) => {
                const isSuccess = item.status === 1;
                const bestModel = item.metadata?.best_model;
                const bestScore = item.metadata?.best_score;

                return (
                  <div
                    key={item.id}
                    onClick={() => handleNotificationClick(item)}
                    className={`group relative flex cursor-pointer items-start gap-3 p-3.5 transition-colors hover:bg-slate-50 dark:hover:bg-white/5 ${
                      !item.is_read
                        ? "bg-blue-50/40 dark:bg-blue-950/20"
                        : "bg-transparent"
                    }`}
                  >
                    {/* Icon đại diện trạng thái */}
                    <div className="relative mt-0.5 shrink-0">
                      <div
                        className={`flex h-9 w-9 items-center justify-center rounded-full shadow-xs ${
                          isSuccess
                            ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400"
                            : "bg-rose-100 text-rose-600 dark:bg-rose-950/50 dark:text-rose-400"
                        }`}
                      >
                        {isSuccess ? (
                          <CheckCircle2 className="h-5 w-5" />
                        ) : (
                          <XCircle className="h-5 w-5" />
                        )}
                      </div>
                    </div>

                    {/* Nội dung thông báo */}
                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-xs leading-snug ${
                          !item.is_read
                            ? "font-bold text-slate-900 dark:text-white"
                            : "font-normal text-slate-700 dark:text-slate-300"
                        }`}
                      >
                        {item.message}
                      </p>

                      {/* Thông tin mô hình tốt nhất & Điểm số nếu có */}
                      {bestModel && (
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                            <Cpu className="h-3 w-3 text-blue-500" />
                            {bestModel}
                          </span>

                          {typeof bestScore === "number" && (
                            <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400">
                              <TrendingUp className="h-3 w-3" />
                              {(bestScore * 100).toFixed(1)}%
                            </span>
                          )}
                        </div>
                      )}

                      {/* Thời gian tương đối và action Xem Job */}
                      <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400 dark:text-slate-500">
                        <span
                          className={
                            !item.is_read
                              ? "font-medium text-blue-600 dark:text-blue-400"
                              : ""
                          }
                        >
                          {formatRelativeTime(item.created_at)}
                        </span>

                        {item.job_id && (
                          <span className="inline-flex items-center gap-0.5 text-[11px] text-blue-600 hover:underline dark:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity">
                            Xem Job <ExternalLink className="h-2.5 w-2.5" />
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Dấu chấm xanh unread chuẩn Facebook */}
                    {!item.is_read && (
                      <span className="mt-3 h-2.5 w-2.5 shrink-0 rounded-full bg-blue-600 shadow-xs ring-2 ring-white dark:ring-slate-950" />
                    )}
                  </div>
                );
              })}

              {/* Phần tử Sentinel để kích hoạt tải thêm (Infinite Scroll) */}
              <div ref={sentinelRef} className="h-1" />

              {/* Trạng thái tải thêm */}
              {isLoadingMore && (
                <div className="flex items-center justify-center p-3 text-xs text-slate-500 gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                  Đang tải thêm...
                </div>
              )}

              {/* Báo đã hết dữ liệu */}
              {!hasMore && rawNotifications.length > 0 && (
                <div className="p-3 text-center text-[11px] text-slate-400 dark:text-slate-500">
                  Bạn đã xem hết thông báo
                </div>
              )}
            </div>
          )}
        </ScrollArea>

        {/* Footer - Trạng thái kết nối MQTT WebSocket (cổng 1884) */}
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/70 px-3.5 py-2 text-[10px] font-medium text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span
                className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  mqttConnected
                    ? "animate-ping bg-emerald-400"
                    : "bg-amber-400"
                }`}
              />
              <span
                className={`relative inline-flex h-2 w-2 rounded-full ${
                  mqttConnected ? "bg-emerald-500" : "bg-amber-500"
                }`}
              />
            </span>
            {mqttConnected
              ? "MQTT WebSocket đã kết nối (1884)"
              : "MQTT WebSocket sẵn sàng"}
          </span>

          <span className="text-[9px] text-slate-400">
            Kênh: <code className="font-mono">hautoml/users/{userId ? `${userId.slice(0, 6)}...` : "{id}"}/notifications</code>
          </span>
        </div>
      </PopoverContent>
    </Popover>
  );
}
