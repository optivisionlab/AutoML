import { configureStore } from '@reduxjs/toolkit';
import registerSlice from "./slices/registerSlice";

export const store = configureStore({
  reducer: {
    register: registerSlice
  },
})

// lấy kiểu dispatch từ store
export type AppDispatch = typeof store.dispatch;

// lấy kiểu state từ store
export type RootState = ReturnType<typeof store.getState>;