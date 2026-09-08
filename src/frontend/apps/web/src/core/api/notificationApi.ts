import {
  type AutoNotification,
  type GetNotificationsParams,
  type NotificationsResponse,
  type MarkNotificationReadParams,
  type MarkNotificationReadResponse,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  AutoNotification,
  GetNotificationsParams,
  NotificationsResponse,
  MarkNotificationReadParams,
  MarkNotificationReadResponse,
};

export const notificationApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getNotifications: builder.query<NotificationsResponse, GetNotificationsParams>({
      query: ({ userId, offset = 0, limit = 10 }) => ({
        url: "/v2/autonotifications",
        params: { user_id: userId, offset, limit },
      }),
      providesTags: ["Notification"],
    }),
    getUnreadNotifications: builder.query<NotificationsResponse, GetNotificationsParams>({
      query: ({ userId, offset = 0, limit = 10 }) => ({
        url: "/v2/autonotifications/unread",
        params: { user_id: userId, offset, limit },
      }),
      providesTags: ["Notification"],
    }),
    markNotificationRead: builder.mutation<
      MarkNotificationReadResponse,
      MarkNotificationReadParams
    >({
      query: ({ notificationId, userId }) => ({
        url: `/v2/autonotifications/${notificationId}/read`,
        method: "PUT",
        params: { user_id: userId },
      }),
      invalidatesTags: ["Notification"],
    }),
  }),
});

export const {
  useGetNotificationsQuery,
  useLazyGetNotificationsQuery,
  useGetUnreadNotificationsQuery,
  useLazyGetUnreadNotificationsQuery,
  useMarkNotificationReadMutation,
} = notificationApi;
