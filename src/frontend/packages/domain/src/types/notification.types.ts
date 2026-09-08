export interface NotificationMetadata {
  best_model?: string;
  best_score?: number;
  [key: string]: unknown;
}

export interface AutoNotification {
  id: string;
  user_id: string;
  job_id?: string;
  status: number; // 1 = thành công, khác 1 = thất bại/lỗi
  message: string;
  metadata?: NotificationMetadata;
  is_read: boolean;
  created_at: number; // Unix timestamp tính bằng giây (e.g. 1788804743.46836)
}

export interface GetNotificationsParams {
  userId: string;
  offset?: number;
  limit?: number;
}

export interface NotificationsResponse {
  data: AutoNotification[];
  unread_count: number;
  has_more: boolean;
}

export interface MarkNotificationReadParams {
  notificationId: string;
  userId: string;
}

export interface MarkNotificationReadResponse {
  status?: string;
  detail?: string;
}
