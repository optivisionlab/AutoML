import { AxiosInstance } from "axios";
import {
  GetNotificationsParams,
  NotificationsResponse,
  MarkNotificationReadParams,
  MarkNotificationReadResponse,
} from "@automl/domain";

export const createNotificationService = (client: AxiosInstance) => ({
  getNotifications: async ({
    userId,
    offset = 0,
    limit = 10,
  }: GetNotificationsParams): Promise<NotificationsResponse> => {
    const res = await client.get<NotificationsResponse>("/v2/autonotifications", {
      params: { user_id: userId, offset, limit },
    });
    return res.data;
  },

  getUnreadNotifications: async ({
    userId,
    offset = 0,
    limit = 10,
  }: GetNotificationsParams): Promise<NotificationsResponse> => {
    const res = await client.get<NotificationsResponse>("/v2/autonotifications/unread", {
      params: { user_id: userId, offset, limit },
    });
    return res.data;
  },

  markAsRead: async ({
    notificationId,
    userId,
  }: MarkNotificationReadParams): Promise<MarkNotificationReadResponse> => {
    const res = await client.put<MarkNotificationReadResponse>(
      `/v2/autonotifications/${notificationId}/read`,
      {},
      {
        params: { user_id: userId },
      }
    );
    return res.data;
  },
});
