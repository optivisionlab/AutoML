import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import {
  type AutoNotification,
  type NotificationItem,
  mapAutoNotificationToItem,
} from "../types";

export interface NotificationState {
  rawNotifications: AutoNotification[];
  items: NotificationItem[];
  unreadCount: number;
  hasMore: boolean;
  offset: number;
  limit: number;
  filter: "all" | "unread";
  isInitialized: boolean;
  isLoading: boolean;
  isLoadingMore: boolean;
  mqttConnected: boolean;
}

const initialState: NotificationState = {
  rawNotifications: [],
  items: [],
  unreadCount: 0,
  hasMore: false,
  offset: 0,
  limit: 10,
  filter: "all",
  isInitialized: false,
  isLoading: false,
  isLoadingMore: false,
  mqttConnected: false,
};

export const notificationSlice = createSlice({
  name: "notifications",
  initialState,
  reducers: {
    setInitialNotifications: (
      state,
      action: PayloadAction<{
        data: AutoNotification[];
        unread_count: number;
        has_more: boolean;
        filter?: "all" | "unread";
      }>
    ) => {
      const { data, unread_count, has_more, filter } = action.payload;
      state.rawNotifications = data;
      state.items = data.map(mapAutoNotificationToItem);
      state.unreadCount = unread_count;
      state.hasMore = has_more;
      state.offset = data.length;
      if (filter) state.filter = filter;
      state.isInitialized = true;
      state.isLoading = false;
    },

    appendNotifications: (
      state,
      action: PayloadAction<{
        data: AutoNotification[];
        has_more: boolean;
      }>
    ) => {
      const { data, has_more } = action.payload;
      const existingIds = new Set(state.rawNotifications.map((n) => n.id));
      const newRaw = data.filter((n) => !existingIds.has(n.id));

      state.rawNotifications.push(...newRaw);
      state.items.push(...newRaw.map(mapAutoNotificationToItem));
      state.offset = state.rawNotifications.length;
      state.hasMore = has_more;
      state.isLoadingMore = false;
    },

    receiveRealtimeNotification: (state, action: PayloadAction<AutoNotification>) => {
      const payload = action.payload;
      const existingIndex = state.rawNotifications.findIndex((n) => n.id === payload.id);

      if (existingIndex !== -1) {
        // Đã tồn tại, cập nhật nếu cần
        state.rawNotifications[existingIndex] = payload;
        state.items[existingIndex] = mapAutoNotificationToItem(payload);
      } else {
        // Chưa tồn tại -> chèn lên đầu danh sách
        state.rawNotifications.unshift(payload);
        state.items.unshift(mapAutoNotificationToItem(payload));
        state.offset += 1;

        // Nếu thông báo chưa đọc, tăng unreadCount
        if (!payload.is_read) {
          state.unreadCount += 1;
        }
      }
    },

    markAsRead: (state, action: PayloadAction<string>) => {
      const id = action.payload;
      const rawTarget = state.rawNotifications.find((n) => n.id === id);
      if (rawTarget && !rawTarget.is_read) {
        rawTarget.is_read = true;
        state.unreadCount = Math.max(0, state.unreadCount - 1);
      }

      const itemTarget = state.items.find((item) => item.id === id);
      if (itemTarget) {
        itemTarget.read = true;
      }
    },

    markAllAsRead: (state) => {
      state.rawNotifications.forEach((n) => {
        n.is_read = true;
      });
      state.items.forEach((item) => {
        item.read = true;
      });
      state.unreadCount = 0;
    },

    setUnreadCount: (state, action: PayloadAction<number>) => {
      state.unreadCount = action.payload;
    },

    setFilter: (state, action: PayloadAction<"all" | "unread">) => {
      state.filter = action.payload;
    },

    setLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload;
    },

    setLoadingMore: (state, action: PayloadAction<boolean>) => {
      state.isLoadingMore = action.payload;
    },

    setMqttConnected: (state, action: PayloadAction<boolean>) => {
      state.mqttConnected = action.payload;
    },

    removeNotification: (state, action: PayloadAction<string>) => {
      const id = action.payload;
      const rawIndex = state.rawNotifications.findIndex((n) => n.id === id);
      if (rawIndex !== -1) {
        if (!state.rawNotifications[rawIndex].is_read) {
          state.unreadCount = Math.max(0, state.unreadCount - 1);
        }
        state.rawNotifications.splice(rawIndex, 1);
      }

      const itemIndex = state.items.findIndex((item) => item.id === id);
      if (itemIndex !== -1) {
        state.items.splice(itemIndex, 1);
      }
    },

    clearAll: (state) => {
      state.rawNotifications = [];
      state.items = [];
      state.unreadCount = 0;
      state.hasMore = false;
      state.offset = 0;
    },
  },
});

export const {
  setInitialNotifications,
  appendNotifications,
  receiveRealtimeNotification,
  markAsRead,
  markAllAsRead,
  setUnreadCount,
  setFilter,
  setLoading,
  setLoadingMore,
  setMqttConnected,
  removeNotification,
  clearAll,
} = notificationSlice.actions;

export default notificationSlice.reducer;
