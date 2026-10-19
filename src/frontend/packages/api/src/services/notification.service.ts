import { AxiosInstance } from "axios";
import {
  GetNotificationsParams,
  MarkNotificationReadParams,
  MarkNotificationReadResponse,
  NotificationsListResponse,
  UnreadNotificationsResponse,
} from "@automl/domain";

export const createNotificationService = (client: AxiosInstance) => ({
  // 4.1 GET /api/v1/notifications
  getNotifications: async (
    params?: GetNotificationsParams,
  ): Promise<NotificationsListResponse> => {
    const res = await client.get<NotificationsListResponse>(
      "/api/v1/notifications",
      {
        params: {
          offset: params?.offset ?? 0,
          limit: params?.limit ?? 10,
        },
      },
    );
    return res.data;
  },

  // 4.2 GET /api/v1/notifications/unread
  getUnreadNotifications: async (): Promise<UnreadNotificationsResponse> => {
    const res = await client.get<UnreadNotificationsResponse>(
      "/api/v1/notifications/unread",
    );
    return res.data;
  },

  // 4.3 PUT /api/v1/notifications/{notification_id}/read
  markAsRead: async (
    notificationId: string,
  ): Promise<MarkNotificationReadResponse> => {
    const res = await client.put<MarkNotificationReadResponse>(
      `/api/v1/notifications/${notificationId}/read`,
    );
    return res.data;
  },

  // Legacy compatibility
  markNotificationRead: async ({
    notificationId,
  }: MarkNotificationReadParams): Promise<any> => {
    const res = await client.put<MarkNotificationReadResponse>(
      `/api/v1/notifications/${notificationId}/read`,
    );
    return res.data;
  },
});
