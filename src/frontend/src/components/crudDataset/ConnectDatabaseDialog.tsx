"use client";

import { useState } from "react";
import { Database, ShieldCheck } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { useTranslations } from "next-intl";

type ConnectDatabaseDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

type DatabaseType = "postgres" | "mysql" | "mongodb";

type DatabaseConnectionForm = {
  type: DatabaseType;
  host: string;
  port: string;
  database: string;
  namespace: string;
  username: string;
  password: string;
  sslMode: "prefer" | "require" | "disable";
  previewQuery: string;
};

const databaseOptions: Record<
  DatabaseType,
  {
    label: string;
    defaultPort: string;
    namespaceLabel: string;
    namespacePlaceholder: string;
    queryLabelKey: "sqlPreview" | "filterPreview";
    defaultQuery: string;
    hostPlaceholder: string;
    usernamePlaceholder: string;
  }
> = {
  postgres: {
    label: "PostgreSQL",
    defaultPort: "5432",
    namespaceLabel: "Schema",
    namespacePlaceholder: "public",
    queryLabelKey: "sqlPreview",
    defaultQuery: "select * from public.my_table limit 20;",
    hostPlaceholder: "db.company.com",
    usernamePlaceholder: "readonly_user",
  },
  mysql: {
    label: "MySQL",
    defaultPort: "3306",
    namespaceLabel: "Table",
    namespacePlaceholder: "orders",
    queryLabelKey: "sqlPreview",
    defaultQuery: "select * from orders limit 20;",
    hostPlaceholder: "mysql.company.com",
    usernamePlaceholder: "readonly_user",
  },
  mongodb: {
    label: "MongoDB",
    defaultPort: "27017",
    namespaceLabel: "Collection",
    namespacePlaceholder: "customers",
    queryLabelKey: "filterPreview",
    defaultQuery: '{ "status": "active" }',
    hostPlaceholder: "mongo.company.com",
    usernamePlaceholder: "readonly_user",
  },
};

const initialForm: DatabaseConnectionForm = {
  type: "postgres",
  host: "",
  port: "5432",
  database: "",
  namespace: "public",
  username: "",
  password: "",
  sslMode: "prefer",
  previewQuery: "select * from public.my_table limit 20;",
};

export default function ConnectDatabaseDialog({
  open,
  onOpenChange,
}: ConnectDatabaseDialogProps) {
  const t = useTranslations("DatasetDialogs.database");
  const { toast } = useToast();
  const [form, setForm] = useState<DatabaseConnectionForm>(initialForm);

  const updateField = <Key extends keyof DatabaseConnectionForm>(
    key: Key,
    value: DatabaseConnectionForm[Key],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const resetForm = () => {
    setForm(initialForm);
  };

  const handleTypeChange = (type: DatabaseType) => {
    const option = databaseOptions[type];

    setForm((current) => ({
      ...current,
      type,
      port: option.defaultPort,
      namespace: type === "postgres" ? "public" : "",
      previewQuery: option.defaultQuery,
    }));
  };

  const handleSubmit = () => {
    if (!form.host || !form.database || !form.username) {
      toast({
        title: t("missingTitle"),
        description: t("missingDescription"),
        variant: "destructive",
      });
      return;
    }

    const requestPayload = {
      ...form,
      port: Number(form.port || databaseOptions[form.type].defaultPort),
      password: form.password ? "[hidden]" : "",
      hasPassword: Boolean(form.password),
      requestedAt: new Date().toISOString(),
    };

    console.group(`HAutoML ${databaseOptions[form.type].label} connection request`);
    console.log(requestPayload);
    console.info(
      t("consoleInfo"),
    );
    console.groupEnd();

    toast({
      title: t("successTitle"),
      description: t("successDescription", { database: databaseOptions[form.type].label }),
      duration: 3500,
    });
  };

  const selectedDatabase = databaseOptions[form.type];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="automl-dialog-content max-w-2xl">
        <DialogHeader className="automl-dialog-header">
          <div className="automl-dialog-kicker mb-3">
            <Database className="h-5 w-5" />
          </div>
          <DialogTitle className="automl-dialog-title">
            {t("title")}
          </DialogTitle>
          <DialogDescription className="automl-dialog-description">
            {t("description")}
          </DialogDescription>
        </DialogHeader>

        <div className="automl-dialog-body">
          <div className="grid gap-4 md:grid-cols-2">
          <div className="automl-dialog-field">
            <Label>{t("databaseType")}</Label>
            <select
              value={form.type}
              onChange={(event) => handleTypeChange(event.target.value as DatabaseType)}
              className="automl-dialog-input w-full"
            >
              {Object.entries(databaseOptions).map(([value, option]) => (
                <option key={value} value={value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="automl-dialog-field">
            <Label>SSL mode</Label>
            <select
              value={form.sslMode}
              onChange={(event) =>
                updateField(
                  "sslMode",
                  event.target.value as DatabaseConnectionForm["sslMode"],
                )
              }
              className="automl-dialog-input w-full"
            >
              <option value="prefer">Prefer</option>
              <option value="require">Require</option>
              <option value="disable">Disable</option>
            </select>
          </div>

          <div className="automl-dialog-field">
            <Label>Host</Label>
            <Input
              className="automl-dialog-input"
              value={form.host}
              onChange={(event) => updateField("host", event.target.value)}
              placeholder={selectedDatabase.hostPlaceholder}
            />
          </div>

          <div className="automl-dialog-field">
            <Label>Port</Label>
            <Input
              className="automl-dialog-input"
              value={form.port}
              onChange={(event) => updateField("port", event.target.value)}
              inputMode="numeric"
              placeholder={selectedDatabase.defaultPort}
            />
          </div>

          <div className="automl-dialog-field">
            <Label>Database</Label>
            <Input
              className="automl-dialog-input"
              value={form.database}
              onChange={(event) => updateField("database", event.target.value)}
              placeholder={form.type === "mongodb" ? "hautoml" : "analytics"}
            />
          </div>

          <div className="automl-dialog-field">
            <Label>{selectedDatabase.namespaceLabel}</Label>
            <Input
              className="automl-dialog-input"
              value={form.namespace}
              onChange={(event) => updateField("namespace", event.target.value)}
              placeholder={selectedDatabase.namespacePlaceholder}
            />
          </div>

          <div className="automl-dialog-field">
            <Label>Username</Label>
            <Input
              className="automl-dialog-input"
              value={form.username}
              onChange={(event) => updateField("username", event.target.value)}
              placeholder={selectedDatabase.usernamePlaceholder}
            />
          </div>

          <div className="automl-dialog-field">
            <Label>Password</Label>
            <Input
              className="automl-dialog-input"
              value={form.password}
              onChange={(event) => updateField("password", event.target.value)}
              type="password"
              placeholder={t("passwordPlaceholder")}
            />
          </div>

          <div className="automl-dialog-field md:col-span-2">
            <Label>{t(`queryLabels.${selectedDatabase.queryLabelKey}`)}</Label>
            <Textarea
              value={form.previewQuery}
              onChange={(event) => updateField("previewQuery", event.target.value)}
              className="automl-dialog-input automl-dialog-textarea font-mono"
            />
          </div>
          </div>

        <div className="automl-dialog-note mt-4">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-automl-blue" />
          <p>
            {t("securityNote")}
          </p>
        </div>
        </div>

        <DialogFooter className="automl-dialog-footer">
          <Button
            variant="outline"
            className="automl-dialog-button-muted"
            onClick={resetForm}
          >
            {t("clearForm")}
          </Button>
          <Button className="automl-action-primary" onClick={handleSubmit}>
            {t("submit")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
