/**
 * Universal file type supporting both browser Web (File, Blob)
 * and React Native / Mobile file descriptors ({ uri, name, type }).
 */
export type UniversalFile =
  | Blob
  | File
  | {
      uri: string;
      name?: string;
      type?: string;
    };

/**
 * Standard Single Response Envelope (BaseResponse<T>)
 */
export interface BaseResponse<T = unknown> {
  success: boolean;
  message: string;
  data: T;
  meta?: Record<string, unknown> | null;
}

/**
 * Standard Page-based Pagination Envelope (PaginatedResponse<T>)
 */
export interface PaginationMeta {
  total_items: number;
  current_page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedResponse<T = unknown> {
  success: boolean;
  message: string;
  data: T[];
  meta: PaginationMeta;
}

/**
 * Standard Offset/Limit Pagination Envelope (OffsetPaginatedResponse<T>)
 */
export interface OffsetPaginationMeta {
  offset: number;
  limit: number;
  total_items: number;
  has_more: boolean;
}

export interface OffsetPaginatedResponse<T = unknown> {
  success: boolean;
  message: string;
  data: T[];
  meta: OffsetPaginationMeta;
}

/**
 * Standard Error Envelope
 */
export interface ApiValidationErrorDetail {
  field: string;
  message: string;
}

export interface ApiErrorResponse {
  success: false;
  error_code:
    | "BAD_REQUEST"
    | "VALIDATION_ERROR"
    | "UNAUTHORIZED"
    | "FORBIDDEN"
    | "NOT_FOUND"
    | "INTERNAL_SERVER_ERROR"
    | string;
  detail: string;
  extra?: {
    errors?: ApiValidationErrorDetail[];
    [key: string]: unknown;
  };
}

export type ApiMessageResponse = {
  detail?: string;
  message?: string;
  password?: string;
  [key: string]: unknown;
};

export type ApiErrorData = {
  status?: number;
  data: unknown;
};
