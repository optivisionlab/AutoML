import { configureStore, type Action } from "@reduxjs/toolkit";
import { baseApi } from "@/core/api/baseApi";
import { listenerMiddleware } from "./listeners";
import trainWizardReducer from "@/features/training/store/trainWizardSlice";
import notificationReducer from "@/features/notifications/store/notificationSlice";

// Mật khẩu database (trang Kết nối database) đi qua tham số mutation của RTK Query; Redux DevTools
// lưu lịch sử action + state nên che các khoá này. Chỉ áp cho phần mutation để không tốn công.
const SECRET_KEYS = new Set(["password"]);

function redactSecrets(value: unknown, depth = 0): unknown {
  if (depth > 8 || value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map((item) => redactSecrets(item, depth + 1));
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      SECRET_KEYS.has(key) ? "[redacted]" : redactSecrets(item, depth + 1),
    ]),
  );
}

const isMutationAction = (action: Action) =>
  action.type.startsWith(`${baseApi.reducerPath}/executeMutation/`);

export const store = configureStore({
  devTools: {
    actionSanitizer: <A extends Action>(action: A): A =>
      isMutationAction(action) ? (redactSecrets(action) as A) : action,
    stateSanitizer: <S,>(state: S): S => {
      const api = (state as Record<string, unknown>)[baseApi.reducerPath] as
        | { mutations?: unknown }
        | undefined;
      if (!api?.mutations) return state;
      return {
        ...state,
        [baseApi.reducerPath]: { ...api, mutations: redactSecrets(api.mutations) },
      } as S;
    },
  },
  // tổng hợp các ruducer
  reducer: {
    // nơi RTK Query lưu cache API,
    [baseApi.reducerPath]: baseApi.reducer,
    trainWizard: trainWizardReducer,
    notifications: notificationReducer,
  },

  // Chạy middleware
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware()
      .prepend(listenerMiddleware.middleware)
      .concat(baseApi.middleware),
});

// lấy kiểu dispatch từ store
export type AppDispatch = typeof store.dispatch;

// lấy kiểu state từ store
export type RootState = ReturnType<typeof store.getState>;

export type AppStore = typeof store;
