"use client";

import { KeyboardEvent, forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertCircle, ArrowUp, Database, FileSpreadsheet, Loader2, Paperclip, UploadCloud, X } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { ACCEPT_ATTR, MAX_UPLOAD_MB, defaultDatasetName, formatSize, validateFile, type FileProblem } from "../lib/agentApi";
import { input, pillButton } from "../lib/ui";
import type { ActiveDataset, AgentError, PendingUpload, ProblemType } from "../hooks/useAgentSession";
import DatasetPicker from "./DatasetPicker";

export type ComposerError = { kind: "file"; problem: FileProblem } | { kind: "upload"; error: AgentError };

export function pickFile(file: File | undefined): { pending: PendingUpload | null; error: ComposerError | null } {
  if (!file) return { pending: null, error: null };
  const problem = validateFile(file);
  if (problem) return { pending: null, error: { kind: "file", problem } };
  return { pending: { file, name: defaultDatasetName(file.name), dataType: "classification" }, error: null };
}

export interface PromptComposerHandle {
  focus: () => void;
}

interface Props {
  variant: "hero" | "docked";
  busy: boolean;
  sending: boolean;
  /** Câu ngắn "agent đang làm gì" khi đang chạy. */
  activityText?: string | null;
  uploadProgress: number | null;
  pending: PendingUpload | null;
  onPendingChange: (pending: PendingUpload | null) => void;
  onSend: (text: string) => void;
  onUpload: (pending: PendingUpload) => Promise<AgentError | null>;
  error: ComposerError | null;
  onError: (error: ComposerError | null) => void;
  activeDataset: ActiveDataset | null;
  activeDatasetName?: string;
  onClearDataset: () => void;
  onPickDataset: (dataset: { id: string; name: string }) => void;
}

const PromptComposer = forwardRef<PromptComposerHandle, Props>(function PromptComposer(
  {
    variant,
    busy,
    sending,
    activityText,
    uploadProgress,
    pending,
    onPendingChange,
    onSend,
    onUpload,
    error,
    onError,
    activeDataset,
    activeDatasetName,
    onClearDataset,
    onPickDataset,
  },
  ref,
) {
  const t = useTranslations("Agent.composer");
  const tFile = useTranslations("Agent.file");
  const tErrors = useTranslations("Agent.errors");
  const tTypes = useTranslations("Agent.problemTypes");
  const tDataset = useTranslations("Agent.dataset");
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploading = uploadProgress !== null;
  const hero = variant === "hero";

  useImperativeHandle(ref, () => ({ focus: () => textareaRef.current?.focus() }), []);

  // Ô nhập tự giãn theo nội dung, có trần để không đẩy hội thoại ra khỏi màn hình.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, hero ? 260 : 200)}px`;
  }, [text, hero]);

  const submit = () => {
    if (busy || !text.trim()) return;
    onSend(text);
    setText("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter gửi, Shift+Enter xuống dòng. Bỏ qua khi đang gõ tiếng Việt (IME).
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  const startUpload = async () => {
    if (!pending) return;
    onError(null);
    const failure = await onUpload(pending);
    if (failure) onError({ kind: "upload", error: failure });
    else onPendingChange(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const errorText = !error
    ? null
    : error.kind === "file"
      ? tFile(error.problem.code, error.problem.values)
      : error.error.code === "server"
        ? error.error.detail
          ? tErrors("server", { detail: error.error.detail })
          : tErrors("serverNoDetail")
        : tErrors(error.error.code);

  return (
    <div className="w-full">
      {errorText && (
        <div role="alert" className="mb-2 flex items-start gap-2 rounded-xl bg-agent-error-soft px-3 py-2 text-xs text-agent-error">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="flex-1 break-words">{errorText}</span>
          <button type="button" onClick={() => onError(null)} aria-label={t("dismiss")} className="agent-focus shrink-0 rounded opacity-70 hover:opacity-100">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {sending && activityText && !hero && (
        <p className="mb-2 flex items-center gap-1.5 truncate text-xs text-agent-primary-strong">
          <Loader2 className="h-3 w-3 shrink-0 animate-spin motion-reduce:animate-none" aria-hidden />
          <span className="truncate">{activityText}</span>
          <span className="hidden shrink-0 text-automl-muted sm:inline">· {t("busyHint")}</span>
        </p>
      )}

      <div
        className={cn(
          "rounded-[20px] border border-automl-line bg-automl-surface transition-shadow duration-200",
          "focus-within:border-agent-primary/60 focus-within:shadow-[0_8px_30px_-12px_hsl(var(--agent-primary)/0.45)]",
          hero && "shadow-sm",
        )}
      >
        {pending && (
          <div className="m-2 mb-0 rounded-2xl border border-agent-primary/30 bg-agent-primary-soft p-3">
            <div className="flex items-center gap-2.5">
              <FileSpreadsheet className="h-8 w-8 shrink-0 text-agent-primary-strong" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-automl-ink">{pending.file.name}</p>
                <p className="text-xs text-automl-muted">{formatSize(pending.file.size)}</p>
              </div>
              {!uploading && (
                <button
                  type="button"
                  onClick={() => onPendingChange(null)}
                  aria-label={t("removeFile")}
                  className="agent-focus rounded-md p-1 text-automl-muted hover:bg-automl-surface hover:text-automl-ink"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {uploading ? (
              <div className="mt-3" aria-live="polite">
                <div className="mb-1 flex justify-between text-xs text-agent-primary-strong">
                  <span className="flex items-center gap-1.5">
                    <Loader2 className="h-3 w-3 animate-spin motion-reduce:animate-none" aria-hidden />
                    {uploadProgress! < 100 ? t("uploading") : t("processing")}
                  </span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-automl-surface">
                  <div className="h-full rounded-full bg-agent-primary transition-all" style={{ width: `${uploadProgress}%` }} />
                </div>
              </div>
            ) : (
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <label className="sr-only" htmlFor={`agent-dataset-name-${variant}`}>{t("datasetName")}</label>
                <input
                  id={`agent-dataset-name-${variant}`}
                  value={pending.name}
                  onChange={(event) => onPendingChange({ ...pending, name: event.target.value })}
                  placeholder={t("datasetName")}
                  maxLength={100}
                  className={cn(input, "flex-1")}
                />
                <label className="sr-only" htmlFor={`agent-dataset-type-${variant}`}>{t("problemType")}</label>
                <select
                  id={`agent-dataset-type-${variant}`}
                  value={pending.dataType}
                  onChange={(event) => onPendingChange({ ...pending, dataType: event.target.value as ProblemType })}
                  className={input}
                >
                  <option value="classification">{tTypes("classification")}</option>
                  <option value="regression">{tTypes("regression")}</option>
                </select>
                <button
                  type="button"
                  onClick={startUpload}
                  disabled={busy}
                  className="agent-focus inline-flex items-center justify-center gap-1.5 rounded-lg bg-agent-primary px-3 py-1.5 text-sm font-semibold text-agent-primary-fg transition-colors hover:bg-agent-primary/90 disabled:opacity-50"
                >
                  <UploadCloud className="h-4 w-4" aria-hidden />
                  {t("addToStore")}
                </button>
              </div>
            )}
          </div>
        )}

        <label htmlFor={`agent-prompt-${variant}`} className="sr-only">{t("label")}</label>
        <textarea
          id={`agent-prompt-${variant}`}
          ref={textareaRef}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          rows={hero ? 3 : 1}
          placeholder={hero ? t("placeholderHero") : t("placeholderDocked")}
          aria-describedby={`agent-shortcut-${variant}`}
          className={cn(
            "block w-full resize-none bg-transparent px-4 text-[15px] text-automl-ink outline-none placeholder:text-automl-muted",
            hero ? "min-h-[92px] pt-4" : "min-h-[44px] pt-3",
          )}
        />

        <div className="flex flex-wrap items-center justify-between gap-2 px-2.5 pb-2.5 pt-1">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT_ATTR}
              className="hidden"
              onChange={(event) => {
                const picked = pickFile(event.target.files?.[0]);
                onError(picked.error);
                onPendingChange(picked.pending);
              }}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={busy}
              title={t("datasetHint", { mb: MAX_UPLOAD_MB })}
              aria-label={t("datasetHint", { mb: MAX_UPLOAD_MB })}
              className={pillButton}
            >
              <Paperclip className="h-3.5 w-3.5" aria-hidden />
              {t("dataset")}
            </button>

            {activeDataset ? (
              <span className="inline-flex min-w-0 max-w-[260px] items-center gap-1 rounded-full bg-agent-primary-soft py-1 pl-2.5 pr-1 text-xs font-medium text-agent-primary-strong">
                <Database className="h-3.5 w-3.5 shrink-0" aria-hidden />
                <DatasetPicker
                  disabled={busy}
                  onPick={onPickDataset}
                  trigger={() => (
                    <button type="button" disabled={busy} title={tDataset("change")} className="agent-focus min-w-0 truncate rounded text-left">
                      {t("activeDataset", { name: activeDatasetName ?? activeDataset.name ?? activeDataset.id.slice(0, 8) })}
                    </button>
                  )}
                />
                <button
                  type="button"
                  onClick={onClearDataset}
                  aria-label={t("clearDataset")}
                  className="agent-focus shrink-0 rounded-full p-0.5 hover:bg-automl-surface"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </span>
            ) : (
              <DatasetPicker
                disabled={busy}
                onPick={onPickDataset}
                trigger={() => (
                  <button type="button" disabled={busy} className={pillButton}>
                    <Database className="h-3.5 w-3.5" aria-hidden />
                    {tDataset("choose")}
                  </button>
                )}
              />
            )}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <span id={`agent-shortcut-${variant}`} className="hidden text-[11px] text-automl-muted md:inline">{t("shortcut")}</span>
            <button
              type="button"
              onClick={submit}
              disabled={busy || !text.trim()}
              aria-label={sending ? t("sending") : t("send")}
              className="agent-focus flex h-9 w-9 items-center justify-center rounded-full bg-agent-primary text-agent-primary-fg transition-colors hover:bg-agent-primary/90 disabled:opacity-30"
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden /> : <ArrowUp className="h-4 w-4" aria-hidden />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
});

export default PromptComposer;
