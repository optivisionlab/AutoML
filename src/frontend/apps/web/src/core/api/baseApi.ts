import { createApi } from "@reduxjs/toolkit/query/react";
import type { BaseQueryFn } from "@reduxjs/toolkit/query";
import { getSession, signOut } from "next-auth/react";
import {
  createApiClient,
  createPublicClient,
  createAxiosBaseQuery,
  getApiErrorMessage,
  serializeApiErrorData,
  serializeBlob,
  type AxiosBaseQueryArgs,
  type ApiError,
} from "@automl/api";

// Re-export error and query helpers from shared package for backward compatibility
export { getApiErrorMessage, serializeApiErrorData, serializeBlob };
export type { AxiosBaseQueryArgs, ApiError };

// Client with dynamic NextAuth session token injection
export const axiosClient = createApiClient({
  baseUrl: () => process.env.NEXT_PUBLIC_BASE_API || "",
  getToken: async () => {
    const session = await getSession();
    return session?.user?.access_token;
  },
});

// Xử lý tự động khi token bị hết hạn hoặc không hợp lệ (401)
axiosClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (
      error.response?.status === 401 &&
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login") &&
      !window.location.pathname.startsWith("/register")
    ) {
      console.warn("[Auth] Phiên đăng nhập đã hết hạn (401), tự động đăng xuất...");
      await signOut({ callbackUrl: "/login" });
    }
    return Promise.reject(error);
  }
);

// Public client without authentication token
export const publicClient = createPublicClient(
  () => process.env.NEXT_PUBLIC_BASE_API || ""
);

// RTK Query Base Query using configured web axios client
const axiosBaseQuery =
  (): BaseQueryFn<AxiosBaseQueryArgs, unknown, ApiError> =>
  createAxiosBaseQuery(axiosClient);

// RTK Query base API
export const baseApi = createApi({
  reducerPath: "api",
  baseQuery: axiosBaseQuery(),
  tagTypes: ["Auth", "User", "Dataset", "AutoML", "Job", "Inference", "Notification"],
  endpoints: () => ({}),
});
