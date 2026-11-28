/**
 * Test logic form "Kết nối database". Ràng buộc chép theo backend database_connections
 * (schemas.py, service.py::_validate_fields).
 *
 * Chạy: npm run test:connections (ở src/frontend). Dùng node:test, không cần thư viện test.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  buildCreatePayload,
  buildUpdatePayload,
  changeType,
  columnLabel,
  emptyForm,
  formatCell,
  validateForm,
  type ConnectionFormState,
} from "./connectionForm";

const pg = (over: Partial<ConnectionFormState> = {}): ConnectionFormState => ({
  ...emptyForm("postgres"),
  name: "Bench Postgres",
  database: "datasets",
  host: "hautoml-test-postgres",
  username: "hautoml_ro",
  password: "ro-test-password",
  ...over,
});

test("form mới có port mặc định theo loại", () => {
  assert.equal(emptyForm("postgres").port, "5432");
  assert.equal(emptyForm("mysql").port, "3306");
  assert.equal(emptyForm("mongodb").port, "27017");
  assert.equal(emptyForm("sqlite").port, "");
});

test("đổi loại giữ tên / mô tả, xoá host / tài khoản / mật khẩu cũ", () => {
  const next = changeType(pg({ description: "demo" }), "sqlite");
  assert.equal(next.name, "Bench Postgres");
  assert.equal(next.description, "demo");
  assert.equal(next.host, "");
  assert.equal(next.password, "");
  assert.equal(next.port, "");
});

test("payload Postgres đầy đủ, cắt khoảng trắng, port là số", () => {
  const payload = buildCreatePayload(pg({ name: "  Bench  ", host: " h ", schema_name: " lab " }));
  assert.deepEqual(payload, {
    name: "Bench",
    db_type: "postgres",
    database: "datasets",
    host: "h",
    port: 5432,
    username: "hautoml_ro",
    password: "ro-test-password",
    schema_name: "lab",
  });
});

test("mật khẩu giữ nguyên từng ký tự, không cắt khoảng trắng", () => {
  assert.equal(buildCreatePayload(pg({ password: " a b " })).password, " a b ");
});

test("SQLite / DuckDB chỉ gửi tên file - backend từ chối host / tài khoản", () => {
  const form = { ...changeType(pg(), "sqlite"), database: "glass.sqlite", host: "x", username: "u", password: "p" };
  assert.deepEqual(buildCreatePayload(form), { name: "Bench Postgres", db_type: "sqlite", database: "glass.sqlite" });
});

test("MySQL / MongoDB không gửi schema_name (backend chỉ nhận cho PostgreSQL)", () => {
  const mysql = { ...changeType(pg(), "mysql"), database: "datasets", host: "m", username: "u", schema_name: "x" };
  assert.equal("schema_name" in buildCreatePayload(mysql), false);
  const mongo = { ...changeType(pg(), "mongodb"), database: "shop", host: "mongo", schema_name: "x" };
  assert.equal("schema_name" in buildCreatePayload(mongo), false);
});

test("kiểm form tạo mới: thiếu trường bắt buộc theo loại", () => {
  const errors = validateForm({ ...emptyForm("postgres") }, "create");
  assert.equal(errors.name, "nameRequired");
  assert.equal(errors.database, "databaseRequired");
  assert.equal(errors.host, "hostRequired");
  assert.equal(errors.username, "usernameRequired");
  // MongoDB không bắt buộc username; SQLite không cần host.
  const mongo = validateForm({ ...emptyForm("mongodb"), name: "m", database: "shop", host: "mongo" }, "create");
  assert.deepEqual(mongo, {});
  const sqlite = validateForm({ ...emptyForm("sqlite"), name: "s", database: "glass.sqlite" }, "create");
  assert.deepEqual(sqlite, {});
});

test("kiểm port, host, schema sai định dạng", () => {
  assert.equal(validateForm(pg({ port: "70000" }), "create").port, "portInvalid");
  assert.equal(validateForm(pg({ port: "54a" }), "create").port, "portInvalid");
  assert.equal(validateForm(pg({ port: "" }), "create").port, undefined);
  assert.equal(validateForm(pg({ host: "a,b" }), "create").host, "hostInvalid");
  assert.equal(validateForm(pg({ host: "/run/postgresql" }), "create").host, "hostInvalid");
  assert.equal(validateForm(pg({ schema_name: "pg-x" }), "create").schema_name, "schemaInvalid");
  assert.equal(validateForm(pg({ schema_name: "lab" }), "create").schema_name, undefined);
});

test("sửa: trường kết nối để trống = giữ nguyên, chỉ gửi thứ đã nhập", () => {
  const edit: ConnectionFormState = { ...emptyForm("postgres"), port: "", name: "Mới", description: "cũ" };
  assert.deepEqual(validateForm(edit, "edit"), {});
  assert.deepEqual(buildUpdatePayload(edit, "cũ"), { name: "Mới" });
  // Đổi mật khẩu và mô tả; xoá mô tả bằng chuỗi rỗng.
  assert.deepEqual(buildUpdatePayload({ ...edit, password: "new" }, "cũ"), { name: "Mới", password: "new" });
  assert.deepEqual(buildUpdatePayload({ ...edit, description: "" }, "cũ"), { name: "Mới", description: "" });
  assert.equal("db_type" in buildUpdatePayload(edit, "cũ"), false);
});

test("sửa: KHÔNG bao giờ gửi password rỗng (backend coi \"\" là xoá mật khẩu đã lưu)", () => {
  const edit: ConnectionFormState = { ...emptyForm("mysql"), port: "", name: "x", password: "" };
  const payload = buildUpdatePayload(edit, null);
  assert.equal("password" in payload, false);
  // Port để trống khi sửa = giữ port cũ, không tự gửi port mặc định.
  assert.equal("port" in payload, false);
  assert.equal(buildUpdatePayload({ ...edit, port: "53306" }, null).port, 53306);
});

test("hiển thị ô dữ liệu: NULL, object, cắt chuỗi dài", () => {
  assert.equal(formatCell(null), "NULL");
  assert.equal(formatCell({ a: 1 }), '{"a":1}');
  assert.equal(formatCell("<b>x</b>"), "<b>x</b>");
  assert.equal(formatCell("x".repeat(300)).length, 200);
  assert.deepEqual(columnLabel({ name: "ri", type: "double precision", nullable: true }), {
    name: "ri",
    type: "double precision",
  });
});
