"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowDown } from "lucide-react";
import type { ChatItem } from "../hooks/useAgentSession";
import type { JobView, TurnTrace } from "../lib/eventAdapter";
import AgentActivityTimeline from "./AgentActivityTimeline";
import ChatMessage, { AgentAvatar, TraceArtifacts, type JobActions } from "./ChatMessage";

interface Props {
  items: ChatItem[];
  liveTrace: TurnTrace | null;
  jobs: Record<string, JobView>;
  actions: JobActions;
}

/** Khoảng cách tới đáy (px) vẫn coi là "đang ở cuối" để tự cuộn theo nội dung mới. */
const STICK_THRESHOLD = 120;

export default function ConversationThread({ items, liveTrace, jobs, actions }: Props) {
  const t = useTranslations("Agent.thread");
  const scrollRef = useRef<HTMLDivElement>(null);
  const [atBottom, setAtBottom] = useState(true);
  const atBottomRef = useRef(true);
  const lastCount = useRef(items.length);

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    const el = scrollRef.current;
    if (!el) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : behavior });
  };

  // Chỉ tự cuộn khi người dùng đang ở cuối, hoặc vừa gửi tin - không giật màn
  // hình khi họ đang kéo lên đọc tin cũ.
  useLayoutEffect(() => {
    const newItems = items.slice(lastCount.current);
    lastCount.current = items.length;
    if (atBottomRef.current || newItems.some((item) => item.kind === "user")) scrollToBottom();
  }, [items, liveTrace, jobs]);

  useEffect(() => {
    scrollToBottom("auto");
  }, []);

  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={scrollRef}
        onScroll={(event) => {
          const el = event.currentTarget;
          const bottom = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_THRESHOLD;
          atBottomRef.current = bottom;
          setAtBottom(bottom);
        }}
        className="h-full overflow-y-auto"
        // Vùng cuộn phải tới được bằng bàn phím để đọc lại tin cũ.
        tabIndex={0}
        aria-label={t("agentName")}
      >
        <div className="mx-auto w-full max-w-[820px] space-y-5 px-4 py-6 sm:px-6">
          {items.map((item) => (
            <ChatMessage key={item.id} item={item} jobs={jobs} actions={actions} />
          ))}

          {liveTrace && (
            <article className="flex gap-3" aria-busy="true">
              <AgentAvatar />
              <div className="min-w-0 flex-1 space-y-2.5">
                <p className="text-xs font-semibold text-automl-muted-strong">{t("agentName")}</p>
                <AgentActivityTimeline trace={liveTrace} live />
                <TraceArtifacts trace={liveTrace} jobs={jobs} actions={actions} />
              </div>
            </article>
          )}
        </div>
      </div>

      {!atBottom && (
        <button
          type="button"
          onClick={() => scrollToBottom()}
          aria-label={t("scrollToLatest")}
          className="agent-focus absolute bottom-3 left-1/2 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-automl-line bg-automl-surface text-automl-muted-strong shadow-md transition-colors hover:text-agent-primary-strong"
        >
          <ArrowDown className="h-4 w-4" aria-hidden />
        </button>
      )}
    </div>
  );
}
