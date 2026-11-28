"use client";

import { FormEvent, useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertCircle, Cable, Loader2, ShieldCheck } from "lucide-react";
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
import { Textarea } from "@/shared/components/ui/textarea";
import { getApiErrorMessage } from "@/core/api/baseApi";
import {
  type DatabaseConnection,
  useCreateDatabaseConnectionMutation,
  useUpdateDatabaseConnectionMutation,
} from "@/core/api/databaseConnectionApi";
import {
  CONNECTION_TYPE_ORDER,
  CONNECTION_TYPES,
  LIMITS,
  buildCreatePayload,
  buildUpdatePayload,
  changeType,
  emptyForm,
  isConnectionType,
  validateForm,
  type ConnectionFormState,
  type FieldErrors,
} from "../lib/connectionForm";

export type ConnectionSavedEvent = {
  connection: DatabaseConnection;
  created: boolean;
  /** Có đổi host / port / database / tài khoản / mật khẩu: nên kiểm tra lại kết nối. */
  connectionChanged: boolean;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Có = sửa kết nối này; không có = tạo mới. */
  connection?: DatabaseConnection | null;
  onSaved: (event: ConnectionSavedEvent) => void;
};

/** Form ban đầu: sửa thì để trống mọi trường kết nối (backend không trả giá trị cũ), kể cả port. */
const initialForm = (connection?: DatabaseConnection | null): ConnectionFormState => {
  if (!connection) return emptyForm("postgres");
  const dbType = isConnectionType(connection.db_type) ? connection.db_type : "postgres";
  return {
    ...emptyForm(dbType),
    port: "",
    name: connection.name,
    description: connection.description ?? "",
  };
};

// Không để trình duyệt / trình quản lý mật khẩu điền tài khoản HAutoML vào ô của database.
const secretInputProps = {
  autoComplete: "off",
  autoCapitalize: "none",
  autoCorrect: "off",
  spellCheck: false,
} as const;

export default function ConnectionFormDialog({ open, onOpenChange, connection, onSaved }: Props) {
  const t = useTranslations("DatabaseConnections");
  const uid = useId();
  const mode = connection ? "edit" : "create";
  const [form, setForm] = useState<ConnectionFormState>(() => initialForm(connection));
  const [submitted, setSubmitted] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const [createConnection, createState] = useCreateDatabaseConnectionMutation();
  const [updateConnection, updateState] = useUpdateDatabaseConnectionMutation();
  const saving = createState.isLoading || updateState.isLoading;

  // Hook mutation giữ tham số (có mật khẩu) tới khi reset. Reset SAU khi request kết thúc, bằng hàm
  // reset của lần render mới nhất (hàm cũ không biết request vừa gửi nên không xoá được gì).
  const { reset: resetCreate, isUninitialized: createIdle, isLoading: creating } = createState;
  const { reset: resetUpdate, isUninitialized: updateIdle, isLoading: updating } = updateState;
  useEffect(() => {
    if (!createIdle && !creating) resetCreate();
  }, [createIdle, creating, resetCreate]);
  useEffect(() => {
    if (!updateIdle && !updating) resetUpdate();
  }, [updateIdle, updating, resetUpdate]);

  // Mở lại dialog (hoặc đổi kết nối đang sửa) = form mới; đóng dialog = xoá mật khẩu khỏi state.
  // Theo id chứ không theo object: danh sách tải lại nền không được xoá thứ người dùng đang gõ.
  const connectionRef = useRef(connection);
  connectionRef.current = connection;
  const connectionId = connection?.id;
  useEffect(() => {
    setForm(open ? initialForm(connectionRef.current) : emptyForm("postgres"));
    setSubmitted(false);
    setServerError(null);
  }, [open, connectionId]);

  const config = CONNECTION_TYPES[form.db_type];
  const errors: FieldErrors = submitted ? validateForm(form, mode) : {};
  const fieldId = (name: string) => `${uid}-${name}`;

  const update = <K extends keyof ConnectionFormState>(key: K, value: ConnectionFormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setServerError(null);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (saving) return;
    setSubmitted(true);
    if (Object.keys(validateForm(form, mode)).length > 0) return;

    try {
      if (connection) {
        const payload = buildUpdatePayload(form, connection.description);
        const saved = await updateConnection({ id: connection.id, payload }).unwrap();
        const connectionChanged = ["database", "host", "port", "username", "password", "schema_name"].some(
          (key) => key in payload,
        );
        onSaved({ connection: saved, created: false, connectionChanged });
      } else {
        const saved = await createConnection(buildCreatePayload(form)).unwrap();
        onSaved({ connection: saved, created: true, connectionChanged: true });
      }
      onOpenChange(false);
    } catch (error) {
      setServerError(getApiErrorMessage(error, t("toast.unknownError")));
    }
  };

  const fieldError = (key: keyof ConnectionFormState) =>
    errors[key] ? (
      <p id={fieldId(`${key}-error`)} className="text-xs font-semibold text-destructive">
        {t(`errors.${errors[key]}`)}
      </p>
    ) : null;

  const describedBy = (key: keyof ConnectionFormState) =>
    errors[key] ? fieldId(`${key}-error`) : undefined;

  const keepHint = mode === "edit" ? t("form.keepCurrent") : undefined;

  return (
    <Dialog open={open} onOpenChange={(next) => !saving && onOpenChange(next)}>
      <DialogContent className="automl-dialog-content flex max-h-[calc(100dvh-2rem)] max-w-2xl flex-col gap-0">
        <form onSubmit={handleSubmit} noValidate autoComplete="off" className="flex min-h-0 flex-1 flex-col">
          <DialogHeader className="automl-dialog-header shrink-0">
            <div className="automl-dialog-kicker">
              <Cable className="h-5 w-5" />
            </div>
            <DialogTitle className="automl-dialog-title mt-2">
              {mode === "edit" ? t("form.editTitle") : t("form.createTitle")}
            </DialogTitle>
            <DialogDescription className="automl-dialog-description">
              {mode === "edit" ? t("form.editDescription") : t("form.createDescription")}
            </DialogDescription>
          </DialogHeader>

          <div className="automl-dialog-body min-h-0 flex-1 space-y-4 overflow-y-auto">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="automl-dialog-field">
                <Label htmlFor={fieldId("type")}>{t("form.type")}</Label>
                <select
                  id={fieldId("type")}
                  value={form.db_type}
                  disabled={mode === "edit"}
                  onChange={(e) => {
                    const next = e.target.value;
                    if (isConnectionType(next)) setForm((prev) => changeType(prev, next));
                  }}
                  className="automl-dialog-input w-full disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {CONNECTION_TYPE_ORDER.map((type) => (
                    <option key={type} value={type}>
                      {CONNECTION_TYPES[type].label}
                    </option>
                  ))}
                </select>
                {mode === "edit" && <p className="automl-dialog-helper text-xs">{t("form.typeLocked")}</p>}
              </div>

              <div className="automl-dialog-field">
                <Label htmlFor={fieldId("name")}>
                  {t("form.name")}
                  <span className="ml-1 text-destructive">*</span>
                </Label>
                <Input
                  id={fieldId("name")}
                  className="automl-dialog-input"
                  value={form.name}
                  maxLength={LIMITS.name}
                  placeholder={t("form.namePlaceholder")}
                  aria-invalid={!!errors.name}
                  aria-describedby={describedBy("name")}
                  onChange={(e) => update("name", e.target.value)}
                />
                {fieldError("name")}
              </div>

              {config.kind !== "file" && (
                <>
                  <div className="automl-dialog-field">
                    <Label htmlFor={fieldId("host")}>
                      {t("form.host")}
                      {mode === "create" && <span className="ml-1 text-destructive">*</span>}
                    </Label>
                    <Input
                      id={fieldId("host")}
                      name={`db-host-${uid}`}
                      className="automl-dialog-input"
                      value={form.host}
                      maxLength={LIMITS.host}
                      placeholder={keepHint ?? config.hostPlaceholder}
                      aria-invalid={!!errors.host}
                      aria-describedby={describedBy("host")}
                      onChange={(e) => update("host", e.target.value)}
                      {...secretInputProps}
                    />
                    {fieldError("host")}
                  </div>

                  <div className="automl-dialog-field">
                    <Label htmlFor={fieldId("port")}>{t("form.port")}</Label>
                    <Input
                      id={fieldId("port")}
                      name={`db-port-${uid}`}
                      className="automl-dialog-input"
                      value={form.port}
                      inputMode="numeric"
                      placeholder={keepHint ?? String(config.defaultPort ?? "")}
                      aria-invalid={!!errors.port}
                      aria-describedby={describedBy("port")}
                      onChange={(e) => update("port", e.target.value)}
                      {...secretInputProps}
                    />
                    {fieldError("port")}
                  </div>
                </>
              )}

              <div className={config.kind === "file" ? "automl-dialog-field md:col-span-2" : "automl-dialog-field"}>
                <Label htmlFor={fieldId("database")}>
                  {config.kind === "file" ? t("form.databaseFile") : t("form.database")}
                  {mode === "create" && <span className="ml-1 text-destructive">*</span>}
                </Label>
                <Input
                  id={fieldId("database")}
                  name={`db-database-${uid}`}
                  className="automl-dialog-input"
                  value={form.database}
                  maxLength={LIMITS.database}
                  placeholder={
                    connection ? t("form.currentDatabase", { label: connection.database_label }) : config.databasePlaceholder
                  }
                  aria-invalid={!!errors.database}
                  aria-describedby={describedBy("database")}
                  onChange={(e) => update("database", e.target.value)}
                  {...secretInputProps}
                />
                {fieldError("database")}
                {config.kind === "file" && <p className="automl-dialog-helper text-xs">{t("form.fileHint")}</p>}
              </div>

              {config.kind !== "file" && (
                <>
                  <div className="automl-dialog-field">
                    <Label htmlFor={fieldId("username")}>
                      {t("form.username")}
                      {mode === "create" && config.usernameRequired && <span className="ml-1 text-destructive">*</span>}
                    </Label>
                    <Input
                      id={fieldId("username")}
                      name={`db-user-${uid}`}
                      className="automl-dialog-input"
                      value={form.username}
                      maxLength={LIMITS.username}
                      placeholder={keepHint ?? config.usernamePlaceholder}
                      aria-invalid={!!errors.username}
                      aria-describedby={describedBy("username")}
                      onChange={(e) => update("username", e.target.value)}
                      {...secretInputProps}
                    />
                    {fieldError("username")}
                  </div>

                  <div className="automl-dialog-field">
                    <Label htmlFor={fieldId("password")}>{t("form.password")}</Label>
                    <Input
                      id={fieldId("password")}
                      name={`db-secret-${uid}`}
                      type="password"
                      className="automl-dialog-input"
                      value={form.password}
                      placeholder={mode === "edit" ? t("form.passwordKeep") : ""}
                      onChange={(e) => update("password", e.target.value)}
                      {...secretInputProps}
                      autoComplete="new-password"
                    />
                  </div>

                  {config.hasSchema && (
                    <div className="automl-dialog-field">
                      <Label htmlFor={fieldId("schema")}>{t("form.schema")}</Label>
                      <Input
                        id={fieldId("schema")}
                        name={`db-schema-${uid}`}
                        className="automl-dialog-input"
                        value={form.schema_name}
                        placeholder={keepHint ?? t("form.schemaPlaceholder")}
                        aria-invalid={!!errors.schema_name}
                        aria-describedby={describedBy("schema_name")}
                        onChange={(e) => update("schema_name", e.target.value)}
                        {...secretInputProps}
                      />
                      {fieldError("schema_name")}
                    </div>
                  )}

                  <p className="automl-dialog-helper text-xs md:col-span-2">{t("form.dockerHint")}</p>
                </>
              )}

              <div className="automl-dialog-field md:col-span-2">
                <Label htmlFor={fieldId("description")}>{t("form.description")}</Label>
                <Textarea
                  id={fieldId("description")}
                  className="automl-dialog-textarea"
                  rows={2}
                  value={form.description}
                  maxLength={LIMITS.description}
                  placeholder={t("form.descriptionPlaceholder")}
                  onChange={(e) => update("description", e.target.value)}
                />
                {fieldError("description")}
              </div>
            </div>

            <div className="automl-dialog-note">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-automl-blue" />
              <div className="space-y-1 text-sm">
                <p className="font-bold">{t("form.securityTitle")}</p>
                <ul className="list-disc space-y-0.5 pl-4">
                  <li>{t("form.security1")}</li>
                  <li>{t("form.security2")}</li>
                  <li>{t("form.security3")}</li>
                </ul>
              </div>
            </div>

            {serverError && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <p className="font-bold">{t("form.saveFailed")}</p>
                  <p className="break-words">{serverError}</p>
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="automl-dialog-footer shrink-0">
            <Button
              type="button"
              variant="outline"
              className="automl-dialog-button-muted"
              disabled={saving}
              onClick={() => onOpenChange(false)}
            >
              {t("form.cancel")}
            </Button>
            <Button type="submit" className="automl-action-primary" disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("form.saving")}
                </>
              ) : mode === "edit" ? (
                t("form.save")
              ) : (
                t("form.create")
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
