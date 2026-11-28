/**
 * Logic thuần cho màn hình "Kết nối database" (không import React / alias "@/" để chạy được bằng
 * node:test - xem connectionForm.test.ts). Ràng buộc chép theo backend:
 * src/backend/src/modules/database_connections/schemas.py và service.py (_validate_fields).
 */

export type ConnectionType = "postgres" | "mysql" | "sqlite" | "duckdb" | "mongodb";
export type ConnectionKind = "server" | "file" | "mongo";

export interface ConnectionTypeConfig {
  label: string;
  kind: ConnectionKind;
  defaultPort?: number;
  usernameRequired: boolean;
  hasSchema: boolean;
  databasePlaceholder: string;
  hostPlaceholder?: string;
  usernamePlaceholder?: string;
}

export const CONNECTION_TYPES: Record<ConnectionType, ConnectionTypeConfig> = {
  postgres: {
    label: "PostgreSQL",
    kind: "server",
    defaultPort: 5432,
    usernameRequired: true,
    hasSchema: true,
    databasePlaceholder: "datasets",
    hostPlaceholder: "db.example.internal",
    usernamePlaceholder: "hautoml_ro",
  },
  mysql: {
    label: "MySQL",
    kind: "server",
    defaultPort: 3306,
    usernameRequired: true,
    hasSchema: false,
    databasePlaceholder: "datasets",
    hostPlaceholder: "db.example.internal",
    usernamePlaceholder: "hautoml_ro",
  },
  sqlite: {
    label: "SQLite",
    kind: "file",
    usernameRequired: false,
    hasSchema: false,
    databasePlaceholder: "glass.sqlite",
  },
  duckdb: {
    label: "DuckDB",
    kind: "file",
    usernameRequired: false,
    hasSchema: false,
    databasePlaceholder: "sales.duckdb",
  },
  mongodb: {
    label: "MongoDB",
    kind: "mongo",
    defaultPort: 27017,
    usernameRequired: false,
    hasSchema: false,
    databasePlaceholder: "shop",
    hostPlaceholder: "mongo.example.internal",
    usernamePlaceholder: "reader",
  },
};

export const CONNECTION_TYPE_ORDER: ConnectionType[] = [
  "postgres",
  "mysql",
  "sqlite",
  "duckdb",
  "mongodb",
];

export const isConnectionType = (value: unknown): value is ConnectionType =>
  typeof value === "string" && value in CONNECTION_TYPES;

/** Giới hạn độ dài chép từ schemas.py. */
export const LIMITS = {
  name: 100,
  database: 255,
  host: 255,
  username: 255,
  description: 1000,
} as const;

const SCHEMA_PATTERN = /^[A-Za-z_][A-Za-z0-9_$]{0,62}$/;

export interface ConnectionFormState {
  name: string;
  db_type: ConnectionType;
  database: string;
  host: string;
  port: string;
  username: string;
  password: string;
  schema_name: string;
  description: string;
}

export const emptyForm = (dbType: ConnectionType = "postgres"): ConnectionFormState => ({
  name: "",
  db_type: dbType,
  database: "",
  host: "",
  port: CONNECTION_TYPES[dbType].defaultPort ? String(CONNECTION_TYPES[dbType].defaultPort) : "",
  username: "",
  password: "",
  schema_name: "",
  description: "",
});

/** Đổi loại: giữ tên / mô tả, xoá các trường không còn hợp lệ, port về mặc định của loại mới. */
export const changeType = (
  form: ConnectionFormState,
  dbType: ConnectionType,
): ConnectionFormState => ({
  ...emptyForm(dbType),
  name: form.name,
  description: form.description,
});

export type FormMode = "create" | "edit";

/** Khoá i18n (namespace DatabaseConnections.errors) của lỗi đầu tiên theo từng trường. */
export type FieldErrors = Partial<Record<keyof ConnectionFormState, string>>;

const parsePort = (raw: string): number | null | "invalid" => {
  const text = raw.trim();
  if (!text) return null;
  if (!/^\d{1,5}$/.test(text)) return "invalid";
  const port = Number(text);
  return port >= 1 && port <= 65535 ? port : "invalid";
};

export function validateForm(form: ConnectionFormState, mode: FormMode): FieldErrors {
  const config = CONNECTION_TYPES[form.db_type];
  const errors: FieldErrors = {};
  const name = form.name.trim();
  if (!name) errors.name = "nameRequired";
  else if (name.length > LIMITS.name) errors.name = "tooLong";

  // Sửa: trường kết nối để trống = giữ nguyên (backend không trả các giá trị cũ để điền sẵn).
  const required = mode === "create";
  if (required && !form.database.trim()) errors.database = "databaseRequired";
  if (form.database.trim().length > LIMITS.database) errors.database = "tooLong";

  if (config.kind !== "file") {
    if (required && !form.host.trim()) errors.host = "hostRequired";
    else if (/[\s,/]/.test(form.host.trim())) errors.host = "hostInvalid";
    if (form.host.trim().length > LIMITS.host) errors.host = "tooLong";
    if (parsePort(form.port) === "invalid") errors.port = "portInvalid";
    if (required && config.usernameRequired && !form.username.trim()) {
      errors.username = "usernameRequired";
    }
    if (form.username.trim().length > LIMITS.username) errors.username = "tooLong";
  }
  if (config.hasSchema && form.schema_name.trim() && !SCHEMA_PATTERN.test(form.schema_name.trim())) {
    errors.schema_name = "schemaInvalid";
  }
  if (form.description.length > LIMITS.description) errors.description = "tooLong";
  return errors;
}

export interface CreatePayload {
  name: string;
  db_type: ConnectionType;
  database: string;
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  schema_name?: string;
  description?: string;
}

export type UpdatePayload = Partial<Omit<CreatePayload, "db_type">>;

/** Chỉ gửi trường đúng loại nguồn: SQLite/DuckDB bị backend từ chối nếu có host / tài khoản. */
function connectionFields(form: ConnectionFormState): UpdatePayload {
  const config = CONNECTION_TYPES[form.db_type];
  const out: UpdatePayload = {};
  const database = form.database.trim();
  if (database) out.database = database;
  if (config.kind === "file") return out;

  const host = form.host.trim();
  if (host) out.host = host;
  const port = parsePort(form.port);
  if (typeof port === "number") out.port = port;
  const username = form.username.trim();
  if (username) out.username = username;
  // Mật khẩu giữ nguyên từng ký tự (có thể có dấu cách ở đầu / cuối).
  if (form.password) out.password = form.password;
  const schema = form.schema_name.trim();
  if (config.hasSchema && schema) out.schema_name = schema;
  return out;
}

export function buildCreatePayload(form: ConnectionFormState): CreatePayload {
  const description = form.description.trim();
  return {
    name: form.name.trim(),
    db_type: form.db_type,
    database: form.database.trim(),
    ...connectionFields(form),
    ...(description ? { description } : {}),
  };
}

/**
 * Sửa: tên luôn gửi; mô tả gửi khi khác bản cũ (chuỗi rỗng = xoá mô tả); trường kết nối chỉ gửi
 * khi người dùng nhập, mật khẩu trống = giữ mật khẩu cũ.
 */
export function buildUpdatePayload(
  form: ConnectionFormState,
  previousDescription?: string | null,
): UpdatePayload {
  const payload: UpdatePayload = { name: form.name.trim(), ...connectionFields(form) };
  const description = form.description.trim();
  if (description !== (previousDescription ?? "").trim()) payload.description = description;
  return payload;
}

// ------------------------------------------------------------------ hiển thị

/** Ô dữ liệu -> chuỗi hiển thị (React tự escape, không dùng HTML). */
export function formatCell(value: unknown, maxLength = 200): string {
  let text: string;
  if (value === null || value === undefined) text = "NULL";
  else if (typeof value === "object") {
    try {
      text = JSON.stringify(value);
    } catch {
      text = String(value);
    }
  } else text = String(value);
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}

/** Tên cột trong kết quả describe (SQL: {name, type}; MongoDB: {name, types}). */
export function columnLabel(column: Record<string, unknown>): { name: string; type: string } {
  const name = typeof column.name === "string" ? column.name : formatCell(column.name);
  const raw = column.type ?? column.types ?? column.data_type ?? "";
  const type = Array.isArray(raw) ? raw.join(" | ") : formatCell(raw, 60);
  return { name, type: type === "NULL" ? "" : type };
}
