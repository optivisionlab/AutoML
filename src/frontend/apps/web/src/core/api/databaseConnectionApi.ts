import {
  type BaseResponse,
  type DatabaseConnection,
  type DatabaseConnectionCreatePayload,
  type DatabaseConnectionResponse,
  type DatabaseConnectionsListResponse,
  type DatabaseConnectionTable,
  type DatabaseConnectionTestResult,
  type DatabaseConnectionUpdatePayload,
  type DatabaseTableDescription,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  DatabaseConnection,
  DatabaseConnectionCreatePayload,
  DatabaseConnectionTable,
  DatabaseConnectionTestResult,
  DatabaseConnectionUpdatePayload,
  DatabaseTableDescription,
};

const BASE = "/api/v1/database-connections";
const PAGE_SIZE = 100;
const MAX_PAGES = 20;
const enc = encodeURIComponent;

/**
 * Kết nối database đã lưu (dùng cho SQL Agent). Mật khẩu chỉ đi một chiều: gửi lên khi tạo / sửa,
 * backend mã hoá và không bao giờ trả lại.
 */
export const databaseConnectionApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getDatabaseConnections: builder.query<DatabaseConnection[], void>({
      // Backend giới hạn page_size <= 100 và không có tìm kiếm: tải đủ các trang để ô tìm kiếm
      // phía giao diện lọc trên TOÀN BỘ kết nối (chặn trên MAX_PAGES cho an toàn).
      async queryFn(_arg, _api, _extraOptions, baseQuery) {
        const all: DatabaseConnection[] = [];
        for (let page = 1; page <= MAX_PAGES; page += 1) {
          const result = await baseQuery({
            url: BASE,
            params: { current_page: page, page_size: PAGE_SIZE },
          });
          if (result.error) return { error: result.error };
          const body = result.data as DatabaseConnectionsListResponse;
          all.push(...(body.data ?? []));
          if (page >= (body.meta?.total_pages ?? 1)) break;
        }
        return { data: all };
      },
      providesTags: (result) => [
        { type: "DatabaseConnection" as const, id: "LIST" },
        ...(result ?? []).map((c) => ({
          type: "DatabaseConnection" as const,
          id: c.id,
        })),
      ],
    }),

    createDatabaseConnection: builder.mutation<
      DatabaseConnection,
      DatabaseConnectionCreatePayload
    >({
      query: (payload) => ({ url: BASE, method: "POST", data: payload }),
      transformResponse: (response: DatabaseConnectionResponse) => response.data,
      invalidatesTags: [{ type: "DatabaseConnection", id: "LIST" }],
    }),

    updateDatabaseConnection: builder.mutation<
      DatabaseConnection,
      { id: string; payload: DatabaseConnectionUpdatePayload }
    >({
      query: ({ id, payload }) => ({
        url: `${BASE}/${enc(id)}`,
        method: "PATCH",
        data: payload,
      }),
      transformResponse: (response: DatabaseConnectionResponse) => response.data,
      invalidatesTags: (_result, _error, { id }) => [
        { type: "DatabaseConnection", id },
        { type: "DatabaseConnection", id: "LIST" },
      ],
    }),

    deleteDatabaseConnection: builder.mutation<null, string>({
      query: (id) => ({ url: `${BASE}/${enc(id)}`, method: "DELETE" }),
      invalidatesTags: (_result, _error, id) => [
        { type: "DatabaseConnection", id },
        { type: "DatabaseConnection", id: "LIST" },
      ],
    }),

    testDatabaseConnection: builder.mutation<DatabaseConnectionTestResult, string>({
      query: (id) => ({ url: `${BASE}/${enc(id)}/test`, method: "POST" }),
      transformResponse: (response: BaseResponse<DatabaseConnectionTestResult>) =>
        response.data,
    }),

    // Danh sách bảng / mô tả bảng là dữ liệu sống của database: không cache lâu.
    getDatabaseConnectionTables: builder.query<DatabaseConnectionTable[], string>({
      query: (id) => ({ url: `${BASE}/${enc(id)}/tables` }),
      transformResponse: (
        response: BaseResponse<{ tables: DatabaseConnectionTable[] }>,
      ) => response.data?.tables ?? [],
      keepUnusedDataFor: 0,
      providesTags: (_result, _error, id) => [{ type: "DatabaseConnection", id }],
    }),

    describeDatabaseTable: builder.mutation<
      DatabaseTableDescription,
      { id: string; table: string; sample_rows?: number }
    >({
      query: ({ id, table, sample_rows = 5 }) => ({
        url: `${BASE}/${enc(id)}/describe`,
        method: "POST",
        data: { table, sample_rows },
      }),
      transformResponse: (response: BaseResponse<DatabaseTableDescription>) =>
        response.data,
    }),
  }),
});

export const {
  useGetDatabaseConnectionsQuery,
  useCreateDatabaseConnectionMutation,
  useUpdateDatabaseConnectionMutation,
  useDeleteDatabaseConnectionMutation,
  useTestDatabaseConnectionMutation,
  useGetDatabaseConnectionTablesQuery,
  useDescribeDatabaseTableMutation,
} = databaseConnectionApi;
