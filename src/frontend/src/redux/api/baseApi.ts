import axios, { AxiosError, Method, ResponseType } from "axios";
import { createApi } from "@reduxjs/toolkit/query/react";
import type { BaseQueryFn } from "@reduxjs/toolkit/query";
import { getSession } from "next-auth/react";

type AxiosBaseQueryArgs = {
  url: string;
  method?: Method;
  data?: unknown;
  params?: Record<string, unknown>;
  responseType?: ResponseType;
};

type ApiError = {
  status?: number;
  data: unknown;
};

const serializeBlob = async (blob: Blob) => {
  if (blob.size === 0) return null;

  const text = await blob.text().catch(() => "");

  if (!text) {
    return blob.type
      ? `${blob.type} response (${blob.size} bytes)`
      : `Binary response (${blob.size} bytes)`;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
};

const serializeApiErrorData = async (data: unknown) => {
  if (typeof Blob !== "undefined" && data instanceof Blob) {
    return serializeBlob(data);
  }

  if (typeof ArrayBuffer !== "undefined" && data instanceof ArrayBuffer) {
    return `Binary response (${data.byteLength} bytes)`;
  }

  return data ?? null;
};

export const getApiErrorMessage = (error: unknown, fallback: string) => {
  if (typeof error === "object" && error !== null && "data" in error) {
    const data = (error as { data?: unknown }).data;

    if (typeof data === "string") return data;
    if (typeof data === "object" && data !== null) {
      const detail = (data as { detail?: unknown }).detail;
      const message = (data as { message?: unknown }).message;

      if (typeof detail === "string") return detail;
      if (typeof message === "string") return message;
    }
  }

  if (error instanceof Error) return error.message;

  return fallback;
};

// Gọi có token
export const axiosClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_BASE_API,
});

// Gọi ko cần token
export const publicClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_BASE_API,
});

axiosClient.interceptors.request.use(async (config) => {
  const session = await getSession();

  if (session?.user.access_token) {
    config.headers.Authorization = `Bearer ${session.user.access_token}`;
  }

  return config;
});

// Config
const axiosBaseQuery =
  (): BaseQueryFn<AxiosBaseQueryArgs, unknown, ApiError> =>
  async ({ url, method = "GET", data, params, responseType }) => {
    try {
      const result = await axiosClient({
        url,
        method,
        data,
        params,
        responseType,
      });

      return { data: result.data };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError;

        return {
          error: {
            status: axiosError.response?.status,
            data:
              (await serializeApiErrorData(axiosError.response?.data)) ??
              axiosError.message,
          },
        };
      }

      return {
        error: {
          data: "NETWORK ERROR or unexpected error",
        },
      };
    }
  };

// config api
export const baseApi = createApi({
  // Là tên key mà RTK Query dùng để lưu cache và trạng thái API trong Redux Store.
  reducerPath: "api",
  baseQuery: axiosBaseQuery(),

  // Khai báo các loại tag dùng để quản lý cache.
  tagTypes: ["Auth", "User", "Dataset", "AutoML", "Job", "Inference"],
  endpoints: () => ({}),
});
