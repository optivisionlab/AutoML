-- Bộ Glass (UCI) thật; DECIMAL để kiểm đường DECIMAL -> số thực có ghi chú.
USE lab;
CREATE TABLE glass (
    RI DECIMAL(8,5), Na DECIMAL(6,2), Mg DECIMAL(6,2), Al DECIMAL(6,2), Si DECIMAL(6,2),
    K DECIMAL(6,2), Ca DECIMAL(6,2), Ba DECIMAL(6,2), Fe DECIMAL(6,2), Type INT
);
-- Không viết LINES TERMINATED BY '\n': server chạy NO_BACKSLASH_ESCAPES nên '\n' là 2 ký tự.
LOAD DATA INFILE '/var/lib/mysql-files/glass.csv' INTO TABLE glass FIELDS TERMINATED BY ',' IGNORE 1 LINES;

-- Bảng "canary" KHÔNG cấp quyền.
CREATE TABLE secret_salaries (note TEXT);
INSERT INTO secret_salaries VALUES ('canary-do-not-read');

CREATE USER 'hautoml_ro'@'%' IDENTIFIED BY 'ro-test-password';
GRANT SELECT ON lab.glass TO 'hautoml_ro'@'%';

CREATE USER 'hautoml_rw'@'%' IDENTIFIED BY 'rw-test-password';
GRANT SELECT, INSERT, DELETE ON lab.glass TO 'hautoml_rw'@'%';
