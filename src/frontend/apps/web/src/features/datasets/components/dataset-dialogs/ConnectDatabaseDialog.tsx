"use client";

import { useState } from "react";
import {
  Database,
  ShieldCheck,
  CheckCircle2,
  ArrowLeft,
  ArrowRight,
  RotateCcw,
  Table2,
  Server,
  AlertCircle,
  Loader2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { useToast } from "@/shared/hooks/use-toast";
import { useTranslations } from "next-intl";
import {
  useConnectDatabaseMutation,
  useImportDatabaseTableMutation,
} from "@/core/api/datasetApi";
import { getApiErrorMessage } from "@/core/api/baseApi";

type ConnectDatabaseDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
};

type DatabaseType =
  | "postgres"
  | "mysql"
  | "sqlite"
  | "duckdb"
  | "mssql"
  | "oracle"
  | "clickhouse"
  | "snowflake"
  | "redshift";

interface DatabaseOptionConfig {
  label: string;
  defaultPort?: string;
  isFilePath?: boolean;
  hasSchema?: boolean;
  defaultSchema?: string;
  hostPlaceholder?: string;
  userPlaceholder?: string;
  databasePlaceholder: string;
}

const databaseConfigs: Record<DatabaseType, DatabaseOptionConfig> = {
  postgres: {
    label: "PostgreSQL",
    defaultPort: "5432",
    hasSchema: true,
    defaultSchema: "public",
    hostPlaceholder: "localhost",
    userPlaceholder: "postgres",
    databasePlaceholder: "my_database",
  },
  mysql: {
    label: "MySQL",
    defaultPort: "3306",
    hostPlaceholder: "localhost",
    userPlaceholder: "root",
    databasePlaceholder: "my_database",
  },
  sqlite: {
    label: "SQLite",
    isFilePath: true,
    databasePlaceholder: "/path/to/database.db hoặc :memory:",
  },
  duckdb: {
    label: "DuckDB",
    isFilePath: true,
    databasePlaceholder: "/path/to/database.duckdb",
  },
  mssql: {
    label: "SQL Server (MSSQL)",
    defaultPort: "1433",
    hasSchema: true,
    defaultSchema: "dbo",
    hostPlaceholder: "localhost",
    userPlaceholder: "sa",
    databasePlaceholder: "my_database",
  },
  oracle: {
    label: "Oracle Database",
    defaultPort: "1521",
    hostPlaceholder: "localhost",
    userPlaceholder: "system",
    databasePlaceholder: "ORCL",
  },
  clickhouse: {
    label: "ClickHouse",
    defaultPort: "8123",
    hostPlaceholder: "localhost",
    userPlaceholder: "default",
    databasePlaceholder: "default",
  },
  snowflake: {
    label: "Snowflake",
    hostPlaceholder: "account.region.snowflakecomputing.com",
    userPlaceholder: "user_name",
    databasePlaceholder: "SNOWFLAKE_SAMPLE_DATA",
  },
  redshift: {
    label: "Amazon Redshift",
    defaultPort: "5439",
    hasSchema: true,
    defaultSchema: "public",
    hostPlaceholder: "cluster.redshift.amazonaws.com",
    userPlaceholder: "awsuser",
    databasePlaceholder: "dev",
  },
};

type FormState = {
  db_type: DatabaseType;
  database: string;
  host: string;
  port: string;
  user: string;
  password: string;
  schema_name: string;
};

const initialForm: FormState = {
  db_type: "postgres",
  database: "",
  host: "localhost",
  port: "5432",
  user: "",
  password: "",
  schema_name: "public",
};

export default function ConnectDatabaseDialog({
  open,
  onOpenChange,
  onSuccess,
}: ConnectDatabaseDialogProps) {
  const t = useTranslations("DatasetDialogs.database");
  const { toast } = useToast();

  const [connectDatabase, { isLoading: isConnecting }] =
    useConnectDatabaseMutation();
  const [importDatabaseTable, { isLoading: isImporting }] =
    useImportDatabaseTableMutation();

  // Wizard step: 1 = Cấu hình kết nối, 2 = Chọn bảng & Đặt tên
  const [step, setStep] = useState<1 | 2>(1);
  const [form, setForm] = useState<FormState>(initialForm);

  // Dữ liệu sau khi kết nối bước 1
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>("");
  const [dataName, setDataName] = useState<string>("");

  const selectedConfig = databaseConfigs[form.db_type];

  const updateField = <K extends keyof FormState>(
    field: K,
    value: FormState[K]
  ) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleTypeChange = (newType: DatabaseType) => {
    const config = databaseConfigs[newType];
    setForm((prev) => ({
      ...prev,
      db_type: newType,
      port: config.defaultPort || "",
      schema_name: config.defaultSchema || "",
      host: config.isFilePath ? "" : prev.host || "localhost",
    }));
  };

  const resetForm = () => {
    setForm(initialForm);
    setTables([]);
    setSelectedTable("");
    setDataName("");
    setStep(1);
  };

  const handleDialogChange = (isOpen: boolean) => {
    onOpenChange(isOpen);
    if (!isOpen) {
      // Khi đóng modal, reset về bước 1
      setStep(1);
    }
  };

  // Bước 1: Kiểm tra kết nối & lấy danh sách tables
  const handleConnect = async () => {
    if (!form.database.trim()) {
      toast({
        title: t("missingDb"),
        variant: "destructive",
      });
      return;
    }

    try {
      const payload = {
        db_type: form.db_type,
        database: form.database.trim(),
        host: selectedConfig.isFilePath
          ? undefined
          : form.host.trim() || "localhost",
        port:
          selectedConfig.isFilePath || !form.port
            ? undefined
            : Number(form.port),
        user: selectedConfig.isFilePath
          ? undefined
          : form.user.trim() || undefined,
        password: selectedConfig.isFilePath
          ? undefined
          : form.password || undefined,
        schema_name:
          selectedConfig.hasSchema && form.schema_name.trim()
            ? form.schema_name.trim()
            : undefined,
        extra_params: {},
      };

      const res = await connectDatabase(payload).unwrap();

      const tableList = res.tables || [];
      setTables(tableList);

      if (tableList.length > 0) {
        setSelectedTable(tableList[0]);
        setDataName(tableList[0]);
      } else {
        setSelectedTable("");
        setDataName("");
      }

      toast({
        title: t("connectSuccess"),
        description: res.message || t("tablesFound", { count: tableList.length }),
      });

      setStep(2);
    } catch (err: unknown) {
      console.error("Connect DB error:", err);
      const errorMsg =
        (err as { data?: { detail?: string; message?: string } })?.data
          ?.detail ||
        (err as { data?: { detail?: string; message?: string } })?.data
          ?.message ||
        getApiErrorMessage(err, t("connectFailed"));

      toast({
        title: t("connectFailed"),
        description: String(errorMsg),
        variant: "destructive",
        duration: 5000,
      });
    }
  };

  // Bước 2: Import bảng vào AutoML
  const handleImport = async () => {
    if (!selectedTable || !dataName.trim()) {
      toast({
        title: t("missingTableOrName"),
        variant: "destructive",
      });
      return;
    }

    try {
      const payload = {
        db_type: form.db_type,
        database: form.database.trim(),
        host: selectedConfig.isFilePath
          ? undefined
          : form.host.trim() || "localhost",
        port:
          selectedConfig.isFilePath || !form.port
            ? undefined
            : Number(form.port),
        user: selectedConfig.isFilePath
          ? undefined
          : form.user.trim() || undefined,
        password: selectedConfig.isFilePath
          ? undefined
          : form.password || undefined,
        schema_name:
          selectedConfig.hasSchema && form.schema_name.trim()
            ? form.schema_name.trim()
            : undefined,
        extra_params: {},
        table_name: selectedTable,
        data_name: dataName.trim(),
      };

      const res = await importDatabaseTable(payload).unwrap();

      toast({
        title: t("importSuccess"),
        description:
          res.message ||
          `Đã nhập thành công bảng '${selectedTable}' vào AutoML!`,
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 4000,
      });

      resetForm();
      onOpenChange(false);
      onSuccess?.();
    } catch (err: unknown) {
      console.error("Import DB table error:", err);
      const errorMsg =
        (err as { data?: { detail?: string; message?: string } })?.data
          ?.detail ||
        (err as { data?: { detail?: string; message?: string } })?.data
          ?.message ||
        getApiErrorMessage(err, t("importFailed"));

      toast({
        title: t("importFailed"),
        description: String(errorMsg),
        variant: "destructive",
        duration: 6000,
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogChange}>
      <DialogContent className="automl-dialog-content max-w-2xl">
        <DialogHeader className="automl-dialog-header">
          <div className="flex items-center gap-2">
            <div className="automl-dialog-kicker">
              <Database className="h-5 w-5" />
            </div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider">
              <span
                className={`rounded-full px-2.5 py-0.5 transition-colors ${
                  step === 1
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {t("step1")}
              </span>
              <span className="text-muted-foreground">/</span>
              <span
                className={`rounded-full px-2.5 py-0.5 transition-colors ${
                  step === 2
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {t("step2")}
              </span>
            </div>
          </div>
          <DialogTitle className="automl-dialog-title mt-2">
            {t("title")}
          </DialogTitle>
          <DialogDescription className="automl-dialog-description">
            {step === 1 ? t("descStep1") : t("descStep2")}
          </DialogDescription>
        </DialogHeader>

        <div className="automl-dialog-body mt-2">
          {step === 1 ? (
            /* =================== BƯỚC 1: CẤU HÌNH KẾT NỐI =================== */
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="automl-dialog-field">
                  <Label>{t("databaseType")}</Label>
                  <select
                    value={form.db_type}
                    onChange={(e) =>
                      handleTypeChange(e.target.value as DatabaseType)
                    }
                    className="automl-dialog-input w-full"
                  >
                    {Object.entries(databaseConfigs).map(([key, config]) => (
                      <option key={key} value={key}>
                        {config.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="automl-dialog-field">
                  <Label>
                    {selectedConfig.isFilePath
                      ? t("databasePath")
                      : t("databaseName")}
                    <span className="text-destructive ml-1">*</span>
                  </Label>
                  <Input
                    className="automl-dialog-input"
                    value={form.database}
                    onChange={(e) => updateField("database", e.target.value)}
                    placeholder={selectedConfig.databasePlaceholder}
                  />
                </div>

                {!selectedConfig.isFilePath && (
                  <>
                    <div className="automl-dialog-field">
                      <Label>{t("host")}</Label>
                      <Input
                        className="automl-dialog-input"
                        value={form.host}
                        onChange={(e) => updateField("host", e.target.value)}
                        placeholder={
                          selectedConfig.hostPlaceholder || "localhost"
                        }
                      />
                    </div>

                    <div className="automl-dialog-field">
                      <Label>{t("port")}</Label>
                      <Input
                        className="automl-dialog-input"
                        value={form.port}
                        onChange={(e) => updateField("port", e.target.value)}
                        inputMode="numeric"
                        placeholder={selectedConfig.defaultPort || "Port"}
                      />
                    </div>

                    <div className="automl-dialog-field">
                      <Label>{t("username")}</Label>
                      <Input
                        className="automl-dialog-input"
                        value={form.user}
                        onChange={(e) => updateField("user", e.target.value)}
                        placeholder={
                          selectedConfig.userPlaceholder || "Username"
                        }
                      />
                    </div>

                    <div className="automl-dialog-field">
                      <Label>{t("password")}</Label>
                      <Input
                        className="automl-dialog-input"
                        type="password"
                        value={form.password}
                        onChange={(e) =>
                          updateField("password", e.target.value)
                        }
                        placeholder={t("passwordPlaceholder")}
                      />
                    </div>

                    {selectedConfig.hasSchema && (
                      <div className="automl-dialog-field md:col-span-2">
                        <Label>{t("schemaName")}</Label>
                        <Input
                          className="automl-dialog-input"
                          value={form.schema_name}
                          onChange={(e) =>
                            updateField("schema_name", e.target.value)
                          }
                          placeholder={
                            selectedConfig.defaultSchema || "public"
                          }
                        />
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="automl-dialog-note mt-3">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-automl-blue" />
                <p>{t("securityNote")}</p>
              </div>
            </div>
          ) : (
            /* =================== BƯỚC 2: CHỌN BẢNG & ĐẶT TÊN DATASET =================== */
            <div className="space-y-4">
              <div className="rounded-lg border border-border/70 bg-muted/40 p-3.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Server className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium">
                      {selectedConfig.label}:{" "}
                      <span className="font-semibold text-foreground">
                        {form.database}
                      </span>
                    </span>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {t("tablesFound", { count: tables.length })}
                  </span>
                </div>
              </div>

              {tables.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-amber-300 bg-amber-50/50 p-6 text-center dark:border-amber-900/60 dark:bg-amber-950/20">
                  <AlertCircle className="h-8 w-8 text-amber-500 mb-2" />
                  <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
                    {t("noTables")}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Vui lòng kiểm tra lại quyền truy cập hoặc quay lại bước trước để chọn schema/database khác.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="automl-dialog-field">
                    <Label htmlFor="select-table">
                      {t("selectTable")}
                    </Label>
                    <div className="relative">
                      <select
                        id="select-table"
                        value={selectedTable}
                        onChange={(e) => {
                          const table = e.target.value;
                          setSelectedTable(table);
                          // Gợi ý luôn tên dataset nếu chưa sửa hoặc đang trùng tên bảng cũ
                          if (!dataName || dataName === selectedTable) {
                            setDataName(table);
                          }
                        }}
                        className="automl-dialog-input w-full"
                      >
                        {tables.map((tbl) => (
                          <option key={tbl} value={tbl}>
                            {tbl}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="automl-dialog-field">
                    <Label htmlFor="dataset-name">
                      {t("datasetName")}
                    </Label>
                    <Input
                      id="dataset-name"
                      className="automl-dialog-input"
                      value={dataName}
                      onChange={(e) => setDataName(e.target.value)}
                      placeholder={t("datasetNamePlaceholder")}
                    />
                    <p className="automl-dialog-helper text-xs text-muted-foreground mt-1">
                      Tên tập dữ liệu sẽ hiển thị trong danh sách "Bộ dữ liệu của tôi" sau khi nhập.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="automl-dialog-footer mt-4">
          {step === 1 ? (
            <>
              <Button
                variant="outline"
                className="automl-dialog-button-muted"
                onClick={resetForm}
                disabled={isConnecting}
              >
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                {t("clearForm")}
              </Button>
              <Button
                className="automl-action-primary"
                onClick={handleConnect}
                disabled={isConnecting || !form.database.trim()}
              >
                {isConnecting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t("connecting")}
                  </>
                ) : (
                  <>
                    {t("connectBtn")}
                    <ArrowRight className="ml-1.5 h-4 w-4" />
                  </>
                )}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                className="automl-dialog-button-muted"
                onClick={() => setStep(1)}
                disabled={isImporting}
              >
                <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
                {t("back")}
              </Button>
              <Button
                className="automl-action-primary"
                onClick={handleImport}
                disabled={
                  isImporting ||
                  tables.length === 0 ||
                  !selectedTable ||
                  !dataName.trim()
                }
              >
                {isImporting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t("importing")}
                  </>
                ) : (
                  <>
                    <Table2 className="mr-1.5 h-4 w-4" />
                    {t("importBtn")}
                  </>
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
