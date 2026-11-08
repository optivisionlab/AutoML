-- Bộ Glass (UCI) thật; cột chữ thường như thói quen PostgreSQL.
CREATE TABLE glass (
    ri double precision, na double precision, mg double precision, al double precision,
    si double precision, k double precision, ca double precision, ba double precision,
    fe double precision, type integer
);
COPY glass FROM '/fixtures/glass.csv' WITH (FORMAT csv, HEADER true);

-- Schema thứ hai (kiểm schema_name): thống kê suy từ chính dữ liệu thật.
CREATE SCHEMA lab;
CREATE TABLE lab.glass_types AS SELECT type, COUNT(*) AS n, AVG(ri) AS avg_ri FROM glass GROUP BY type;

-- Bảng "canary" KHÔNG cấp quyền: agent không được thấy, không được đọc.
CREATE TABLE secret_salaries (note text);
INSERT INTO secret_salaries VALUES ('canary-do-not-read');
REVOKE ALL ON secret_salaries FROM PUBLIC;

-- Tài khoản đúng khuyến nghị: CHỈ SELECT trên bảng được chia sẻ.
CREATE ROLE hautoml_ro LOGIN PASSWORD 'ro-test-password';
GRANT CONNECT ON DATABASE lab TO hautoml_ro;
GRANT USAGE ON SCHEMA public, lab TO hautoml_ro;
GRANT SELECT ON glass, lab.glass_types TO hautoml_ro;

-- Tài khoản CÓ quyền ghi: để kiểm transaction chỉ-đọc của bộ chạy vẫn chặn ghi.
CREATE ROLE hautoml_rw LOGIN PASSWORD 'rw-test-password';
GRANT CONNECT ON DATABASE lab TO hautoml_rw;
GRANT USAGE ON SCHEMA public TO hautoml_rw;
GRANT SELECT, INSERT, DELETE ON glass TO hautoml_rw;
