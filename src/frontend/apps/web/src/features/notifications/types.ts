import { AutoNotification, NotificationsResponse, GetNotificationsParams } from "@automl/domain";

export type { AutoNotification, NotificationsResponse, GetNotificationsParams };

export type NotificationType =
  | "job_success"
  | "job_progress"
  | "job_failed"
  | "system_alert"
  | "dataset_ready";

export type NotificationLevel = "success" | "info" | "warning" | "error";

export interface NotificationItem {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  level: NotificationLevel;
  timestamp: number; // Unix timestamp in ms
  read: boolean;
  job_id?: string;
  dataset_id?: string;
  data?: {
    best_model?: string;
    best_score?: number;
    metric?: string;
    completed_models?: number;
    total_models?: number;
    progress?: number;
    error_message?: string;
    dataset_name?: string;
  };
}

/**
 * Chuyển đổi AutoNotification từ backend thành NotificationItem hiển thị trên UI
 */
export const mapAutoNotificationToItem = (item: AutoNotification): NotificationItem => {
  const isSuccess = item.status === 1;
  const level: NotificationLevel = isSuccess ? "success" : "error";
  const type: NotificationType = isSuccess ? "job_success" : "job_failed";
  const title = isSuccess ? "Huấn luyện thành công" : "Huấn luyện gặp sự cố";

  // timestamp backend trả về dạng giây, quy đổi ra milliseconds nếu cần
  const timestamp = item.created_at
    ? item.created_at < 1e11
      ? Math.round(item.created_at * 1000)
      : Math.round(item.created_at)
    : Date.now();

  return {
    id: item.id,
    type,
    title,
    message: item.message || (isSuccess ? "Mô hình đã được huấn luyện hoàn tất." : "Quá trình huấn luyện không thành công."),
    level,
    timestamp,
    read: Boolean(item.is_read),
    job_id: item.job_id,
    data: {
      best_model: item.metadata?.best_model,
      best_score: item.metadata?.best_score,
    },
  };
};
