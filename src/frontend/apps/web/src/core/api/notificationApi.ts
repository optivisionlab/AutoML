import {
  type AutoNotification,
  type GetNotificationsParams,
  type MarkNotificationReadParams,
  type MarkNotificationReadResponse,
  type NotificationsListResponse,
  type NotificationsResponse,
  type UnreadNotificationsResponse,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  AutoNotification,
  GetNotificationsParams,
  MarkNotificationReadParams,
  MarkNotificationReadResponse,
  NotificationsListResponse,
  NotificationsResponse,
  UnreadNotificationsResponse,
};

export const notificationApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // 4.1 GET /api/v1/notifications
    getNotifications: builder.query<
      NotificationsListResponse,
      GetNotificationsParams | void
    >({
      query: (params) => ({
        url: "/api/v1/notifications",
        params: {
          offset: params?.offset ?? 0,
          limit: params?.limit ?? 10,
        },
      }),
      providesTags: ["Notification"],
    }),

    // 4.2 GET /api/v1/notifications/unread
    getUnreadNotifications: builder.query<UnreadNotificationsResponse, void>({
      query: () => ({
        url: "/api/v1/notifications/unread",
      }),
      providesTags: ["Notification"],
    }),

    // 4.3 PUT /api/v1/notifications/{notification_id}/read
    markNotificationRead: builder.mutation<
      MarkNotificationReadResponse,
      string | MarkNotificationReadParams
    >({
      query: (arg) => {
        const id = typeof arg === "string" ? arg : arg.notificationId;
        return {
          url: `/api/v1/notifications/${id}/read`,
          method: "PUT",
        };
      },
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
