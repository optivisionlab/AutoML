import { configureStore } from "@reduxjs/toolkit";
import { baseApi } from "./api/baseApi";
import { listenerMiddleware } from "./listeners";
import trainWizardReducer from "./slices/trainWizardSlice";

export const store = configureStore({
  // tổng hợp các ruducer
  reducer: {
    // nơi RTK Query lưu cache API,
    [baseApi.reducerPath]: baseApi.reducer,
    trainWizard: trainWizardReducer,
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
