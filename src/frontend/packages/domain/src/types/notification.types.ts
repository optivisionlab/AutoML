import { BaseResponse, OffsetPaginatedResponse } from "./common.types";

export interface NotificationMetadata {
  best_model?: string;
  best_score?: number;
  [key: string]: unknown;
}

export interface AutoNotification {
  _id?: string;
  id?: string;
  user_id?: string;
  job_id?: string;
  status: string | number; // "1" | 1 = thành công, khác 1 = thất bại/lỗi
  message: string;
  metadata?: NotificationMetadata;
  is_read: boolean;
  created_at: number; // Unix timestamp
}

export interface GetNotificationsParams {
  userId?: string;
  offset?: number;
  limit?: number;
}

export type NotificationItem = AutoNotification;
export type NotificationsListResponse = OffsetPaginatedResponse<AutoNotification>;
export type UnreadNotificationsResponse = OffsetPaginatedResponse<AutoNotification>;

export interface MarkNotificationReadParams {
  notificationId: string;
  userId?: string;
}

export type MarkNotificationReadResponse = BaseResponse<null>;

// Legacy compatibility
export interface NotificationsResponse {
  data: AutoNotification[];
  unread_count?: number;
  has_more?: boolean;
  meta?: {
    offset: number;
    limit: number;
    total_items: number;
    has_more: boolean;
  };
}
