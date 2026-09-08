import { createApi } from "@reduxjs/toolkit/query/react";
import type { BaseQueryFn } from "@reduxjs/toolkit/query";
import { getSession } from "next-auth/react";
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
