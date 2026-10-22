"use client";

import { useTranslations } from "next-intl";
import { KNOWN_AGENTS, KNOWN_TOOLS } from "../lib/eventAdapter";

/** Tên hiển thị của agent/tool theo ngôn ngữ; tên lạ (tool mới) giữ nguyên. */
export function useAgentLabels() {
  const tAgents = useTranslations("Agent.agents");
  const tTools = useTranslations("Agent.tools");
  return {
    agentName: (agent: string) => (KNOWN_AGENTS.has(agent) ? tAgents(agent) : agent),
    toolName: (tool: string) => (KNOWN_TOOLS.has(tool) ? tTools(tool) : tool),
  };
}
