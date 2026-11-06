"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { BarChart3, BrainCircuit, ListChecks, TableProperties } from "lucide-react";

const SUGGESTIONS = [
  { key: "train", icon: BrainCircuit },
  { key: "analyze", icon: TableProperties },
  { key: "jobs", icon: ListChecks },
  { key: "metrics", icon: BarChart3 },
] as const;

/** Gợi ý nhanh: mỗi chip gửi một câu hỏi thật tới agent. */
export function PromptSuggestions({ busy, onSend }: { busy: boolean; onSend: (text: string) => void }) {
  const t = useTranslations("Agent.suggestions");
  return (
    <ul className="flex flex-wrap justify-center gap-2">
      {SUGGESTIONS.map(({ key, icon: Icon }) => (
        <li key={key}>
          <button
            type="button"
            onClick={() => onSend(t(`${key}.prompt`))}
            disabled={busy}
            className="agent-focus inline-flex items-center gap-1.5 rounded-full border border-automl-line bg-automl-surface px-3.5 py-2 text-[13px] font-medium text-automl-muted-strong transition-colors duration-200 hover:border-agent-primary/50 hover:text-agent-primary-strong disabled:opacity-50"
          >
            <Icon className="h-4 w-4" aria-hidden />
            {t(`${key}.label`)}
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Màn bắt đầu kiểu prompt-first: ô nhập là trọng tâm, không có số liệu giả. */
export default function AgentWelcome({
  composer,
  busy,
  onSend,
}: {
  composer: ReactNode;
  busy: boolean;
  onSend: (text: string) => void;
}) {
  const t = useTranslations("Agent.welcome");
  return (
    <div className="mx-auto flex w-full max-w-[820px] flex-col items-center px-4 py-10 sm:py-16">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-agent-primary-strong">{t("eyebrow")}</p>
      <h2 className="mt-3 text-center text-3xl font-black tracking-tight text-automl-ink sm:text-4xl">{t("heading")}</h2>
      <p className="mt-3 max-w-xl text-center text-sm text-automl-muted sm:text-base">{t("subheading")}</p>

      <div className="mt-8 w-full">{composer}</div>

      <div className="mt-5">
        <PromptSuggestions busy={busy} onSend={onSend} />
      </div>

      <p className="mt-8 max-w-xl text-center text-xs text-automl-muted">{t("note")}</p>
    </div>
  );
}
