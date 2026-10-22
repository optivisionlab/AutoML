"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Markdown của câu trả lời agent. react-markdown không render HTML thô (không
 * bật rehype-raw) và tự lọc URL nguy hiểm (javascript:), nên nội dung từ LLM
 * không chèn được script.
 */
const components: Components = {
  p: ({ children }) => <p className="my-1.5 leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="my-1.5 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-1.5 list-decimal space-y-1 pl-5">{children}</ol>,
  h1: ({ children }) => <p className="mb-1 mt-3 text-base font-bold">{children}</p>,
  h2: ({ children }) => <p className="mb-1 mt-3 text-[15px] font-bold">{children}</p>,
  h3: ({ children }) => <p className="mb-1 mt-2.5 font-semibold">{children}</p>,
  h4: ({ children }) => <p className="mb-1 mt-2 font-semibold">{children}</p>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="agent-focus rounded font-medium text-agent-primary-strong underline underline-offset-2">
      {children}
    </a>
  ),
  hr: () => <hr className="my-3 border-automl-line" />,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-agent-primary/50 pl-3 text-automl-muted-strong">{children}</blockquote>
  ),
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-xl bg-slate-950 p-3 font-mono text-[12px] leading-relaxed text-slate-100">{children}</pre>
  ),
  // Khối ``` không ghi ngôn ngữ cũng không có className: nằm trong <pre> thì bỏ kiểu inline.
  code: ({ className, children }) =>
    className ? (
      <code className={className}>{children}</code>
    ) : (
      <code className="rounded bg-automl-surface-muted px-1 py-0.5 font-mono text-[12.5px] [pre_&]:bg-transparent [pre_&]:p-0 [pre_&]:text-[12px]">{children}</code>
    ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto rounded-xl border border-automl-line">
      <table className="w-full border-collapse text-left text-[13px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-automl-surface-muted">{children}</thead>,
  th: ({ children }) => <th className="whitespace-nowrap px-3 py-2 font-semibold">{children}</th>,
  td: ({ children }) => <td className="border-t border-automl-line px-3 py-1.5">{children}</td>,
};

export default function AgentMarkdown({ text }: { text: string }) {
  return (
    <div className="break-words text-[14.5px] text-automl-ink">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
