import axios, { AxiosError, AxiosInstance, Method, ResponseType } from "axios";
import { serializeApiErrorData } from "./errors";

export type TokenProvider = () =>
  | Promise<string | null | undefined>
  | string
  | null
  | undefined;

export type BaseUrlProvider = () => string;

export interface ApiClientConfig {
  baseUrl: string | BaseUrlProvider;
  getToken?: TokenProvider;
  timeout?: number;
  headers?: Record<string, string>;
}

export type AxiosBaseQueryArgs = {
  url: string;
  method?: Method;
  data?: unknown;
  params?: Record<string, unknown>;
  responseType?: ResponseType;
};

export type ApiError = {
  status?: number;
  data: unknown;
};

/**
 * Creates an Axios client with customizable baseUrl and token resolution.
 * Suitable for both Web (NextAuth session token) and Mobile (SecureStore token).
 */
export const createApiClient = (config: ApiClientConfig): AxiosInstance => {
  const getBaseUrl =
    typeof config.baseUrl === "function"
      ? config.baseUrl
      : () => config.baseUrl as string;

  const client = axios.create({
    timeout: config.timeout ?? 30000,
    headers: config.headers,
  });

  client.interceptors.request.use(async (reqConfig) => {
    // Dynamically attach baseURL if needed
    if (!reqConfig.baseURL) {
      reqConfig.baseURL = getBaseUrl();
    }

    // Attach authorization header if getToken is provided
    if (config.getToken) {
      const token = await config.getToken();
      if (token) {
        reqConfig.headers.Authorization = `Bearer ${token}`;
      }
    }

    return reqConfig;
  });

  return client;
};

/**
 * Creates a public Axios client without token attachment.
 */
export const createPublicClient = (baseUrl: string | BaseUrlProvider): AxiosInstance => {
  const getBaseUrl =
    typeof baseUrl === "function" ? baseUrl : () => baseUrl;

  const client = axios.create({
    timeout: 30000,
  });

  client.interceptors.request.use(async (reqConfig) => {
    if (!reqConfig.baseURL) {
      reqConfig.baseURL = getBaseUrl();
    }
    return reqConfig;
  });

  return client;
};

/**
 * Resolves downloadable file name from Content-Disposition header.
 */
export const resolveFileName = (contentDisposition?: string, defaultName = "result.csv") => {
  if (!contentDisposition) return defaultName;

  const match =
    contentDisposition.match(/filename\*=UTF-8''(.+)/) ||
    contentDisposition.match(/filename="?([^"]+)"?/);

  return match?.[1] ? decodeURIComponent(match[1]) : defaultName;
};

/**
 * Creates an RTK Query compatible baseQuery from an Axios instance.
 */
export const createAxiosBaseQuery = (client: AxiosInstance) => {
  return async ({
    url,
    method = "GET",
    data,
    params,
    responseType,
  }: AxiosBaseQueryArgs) => {
    try {
      const result = await client({
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
};
