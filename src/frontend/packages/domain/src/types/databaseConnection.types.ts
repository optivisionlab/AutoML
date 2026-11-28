import type { BaseResponse, PaginatedResponse } from "./common.types";

/**
 * Kết nối database ĐÃ LƯU cho SQL Agent (backend: /api/v1/database-connections).
 * Backend không bao giờ trả host, username, port hay mật khẩu - chỉ nhãn database.
 */
export type DatabaseConnectionType =
  | "postgres"
  | "mysql"
  | "sqlite"
  | "duckdb"
  | "mongodb";

export interface DatabaseConnection {
  id: string;
  name: string;
  db_type: DatabaseConnectionType;
  database_label: string;
  description?: string | null;
  version: number;
  created_at: number;
  updated_at: number;
}

export interface DatabaseConnectionCreatePayload {
  name: string;
  db_type: DatabaseConnectionType;
  database: string;
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  schema_name?: string;
  description?: string;
}

/** Trường bỏ trống = giữ nguyên (backend bỏ qua giá trị null / không gửi). */
export type DatabaseConnectionUpdatePayload = Partial<
  Omit<DatabaseConnectionCreatePayload, "db_type">
>;

export interface DatabaseConnectionTable {
  name: string;
  kind: "table" | "collection" | string;
}

export interface DatabaseConnectionTestResult {
  connected: boolean;
  table_count: number;
}

export interface DatabaseTableDescription {
  table: string;
  columns: Array<Record<string, unknown>>;
  rows: Array<Record<string, unknown>>;
  schema_inferred?: boolean;
  omitted_columns?: number;
}

export type DatabaseConnectionsListResponse =
  PaginatedResponse<DatabaseConnection>;
export type DatabaseConnectionResponse = BaseResponse<DatabaseConnection>;
