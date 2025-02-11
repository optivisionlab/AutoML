import { configureStore } from '@reduxjs/toolkit';
import postsSlice from "./slices/postsSlice";

export const store = configureStore({
  reducer: {
    posts: postsSlice
  },
})

// lấy kiểu dispatch từ store
export type AppDispatch = typeof store.dispatch;

// lấy kiểu state từ store
export type RootState = ReturnType<typeof store.getState>;