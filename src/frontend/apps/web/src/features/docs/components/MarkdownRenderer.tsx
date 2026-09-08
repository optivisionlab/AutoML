"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy, ExternalLink, Terminal, AlertTriangle, Lightbulb, Info, AlertCircle } from "lucide-react";

import { useTranslations } from "next-intl";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

// Helper to generate slug for headings
function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// Component to render code blocks with copy functionality
function CodeBlock({
  language,
  children,
}: {
  language?: string;
  children: React.ReactNode;
}) {
  const t = useTranslations("Docs");
  const [copied, setCopied] = useState(false);
  const rawCode = String(children).replace(/\n$/, "");

  const handleCopy = () => {
    navigator.clipboard.writeText(rawCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const displayLang = (language || "TEXT").toUpperCase();

  return (
    <div className="group relative my-4 overflow-hidden rounded-2xl border border-slate-800 bg-[#060D1A] font-mono text-xs shadow-md transition">
      {/* Code Header Bar */}
      <div className="flex items-center justify-between border-b border-slate-800/80 bg-[#0B1528] px-4 py-2.5 text-[11px] text-slate-400">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-blue-400" />
          <span className="font-bold tracking-wider text-slate-300">
            {displayLang}
          </span>
        </div>

        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded-lg bg-white/10 px-2.5 py-1 text-[11px] font-medium text-slate-300 transition hover:bg-white/20 hover:text-white"
          title={t("copyCodeSnippet")}
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-semibold">{t("copiedCode")}</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span>{t("copyCode")}</span>
            </>
          )}
        </button>
      </div>

      {/* Code content */}
      <pre className="overflow-x-auto p-4 leading-relaxed text-cyan-300 scrollbar-thin scrollbar-thumb-slate-700">
        <code>{children}</code>
      </pre>
    </div>
  );
}

export default function MarkdownRenderer({
  content,
  className = "",
}: MarkdownRendererProps) {
  return (
    <div className={`prose-docs space-y-4 text-slate-700 dark:text-slate-300 leading-relaxed text-sm ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Headings with clean anchors
          h1: ({ children }) => {
            const text = String(children);
            const id = slugify(text);
            return (
              <h1
                id={id}
                className="group mt-8 mb-4 border-b border-slate-200/80 pb-3 text-2xl sm:text-3xl font-black tracking-tight text-slate-900 dark:border-white/10 dark:text-white first:mt-0"
              >
                <a href={`#${id}`} className="hover:text-blue-600 dark:hover:text-cyan-400 transition">
                  {children}
                </a>
              </h1>
            );
          },
          h2: ({ children }) => {
            const text = String(children);
            const id = slugify(text);
            return (
              <h2
                id={id}
                className="group mt-8 mb-3 text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white"
              >
                <a href={`#${id}`} className="hover:text-blue-600 dark:hover:text-cyan-400 transition">
                  {children}
                </a>
              </h2>
            );
          },
          h3: ({ children }) => {
            const text = String(children);
            const id = slugify(text);
            return (
              <h3
                id={id}
                className="group mt-6 mb-2 text-lg font-bold text-slate-900 dark:text-white"
              >
                <a href={`#${id}`} className="hover:text-blue-600 dark:hover:text-cyan-400 transition">
                  {children}
                </a>
              </h3>
            );
          },
          h4: ({ children }) => (
            <h4 className="mt-4 mb-2 text-sm font-bold text-slate-800 dark:text-slate-200">
              {children}
            </h4>
          ),

          // Paragraph
          p: ({ children }) => (
            <p className="my-3 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
              {children}
            </p>
          ),

          // Unordered list
          ul: ({ children }) => (
            <ul className="my-3 ml-2 list-inside list-disc space-y-1.5 text-sm text-slate-700 dark:text-slate-300">
              {children}
            </ul>
          ),

          // Ordered list
          ol: ({ children }) => (
            <ol className="my-3 ml-2 list-inside list-decimal space-y-1.5 text-sm text-slate-700 dark:text-slate-300">
              {children}
            </ol>
          ),

          li: ({ children }) => (
            <li className="leading-relaxed">
              {children}
            </li>
          ),

          // Blockquotes with alert callout styling
          blockquote: ({ children }) => {
            const text = String(
              React.Children.toArray(children)
                .map((child) =>
                  React.isValidElement(child)
                    ? (child.props as { children?: React.ReactNode })?.children
                    : child
                )
                .flat()
                .join(" ")
            );

            const isWarning = text.includes("⚠️") || text.toLowerCase().includes("chú ý") || text.includes("[!WARNING]");
            const isTip = text.includes("💡") || text.toLowerCase().includes("mẹo") || text.includes("[!TIP]");
            const isImportant = text.includes("📌") || text.toLowerCase().includes("lưu ý") || text.includes("[!IMPORTANT]");

            if (isWarning) {
              return (
                <div className="my-4 rounded-2xl border border-amber-300/70 bg-amber-50/70 p-4 text-xs text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-200 flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
                  <div className="flex-1 space-y-1">{children}</div>
                </div>
              );
            }

            if (isTip) {
              return (
                <div className="my-4 rounded-2xl border border-emerald-300/70 bg-emerald-50/70 p-4 text-xs text-emerald-950 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-200 flex items-start gap-3">
                  <Lightbulb className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
                  <div className="flex-1 space-y-1">{children}</div>
                </div>
              );
            }

            if (isImportant) {
              return (
                <div className="my-4 rounded-2xl border border-blue-300/70 bg-blue-50/70 p-4 text-xs text-blue-950 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-200 flex items-start gap-3">
                  <Info className="h-5 w-5 shrink-0 text-blue-600 dark:text-cyan-400 mt-0.5" />
                  <div className="flex-1 space-y-1">{children}</div>
                </div>
              );
            }

            return (
              <div className="my-4 rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4 text-xs text-slate-800 dark:border-white/10 dark:bg-[#061021]/60 dark:text-slate-300 flex items-start gap-3">
                <AlertCircle className="h-5 w-5 shrink-0 text-slate-500 mt-0.5" />
                <div className="flex-1 space-y-1">{children}</div>
              </div>
            );
          },

          // Code blocks & inline code
          pre: ({ children }) => {
            if (React.isValidElement(children)) {
              const codeProps = children.props as { className?: string; children?: React.ReactNode };
              const match = /language-(\w+)/.exec(codeProps?.className || "");
              const language = match ? match[1] : undefined;
              return <CodeBlock language={language}>{codeProps?.children}</CodeBlock>;
            }
            return <CodeBlock>{children}</CodeBlock>;
          },

          code: ({ className, children }) => {
            const isLanguageBlock = /language-(\w+)/.test(className || "");
            if (isLanguageBlock) {
              return <code>{children}</code>;
            }
            return (
              <code className="rounded-md border border-slate-200/60 bg-slate-100/90 px-1.5 py-0.5 font-mono text-xs font-semibold text-blue-600 dark:border-white/10 dark:bg-white/10 dark:text-cyan-300">
                {children}
              </code>
            );
          },

          // Tables
          table: ({ children }) => (
            <div className="my-6 overflow-x-auto rounded-2xl border border-slate-200/80 bg-white/70 shadow-sm dark:border-white/10 dark:bg-[#0B0F19]/60">
              <table className="w-full text-left text-xs border-collapse">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-bold uppercase tracking-wider text-slate-700 dark:border-white/10 dark:bg-[#061021] dark:text-slate-300">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-slate-200/60 dark:divide-white/5">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="transition hover:bg-slate-50/50 dark:hover:bg-white/[0.02]">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="px-4 py-3 font-bold text-slate-900 dark:text-white">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-3 text-slate-600 dark:text-slate-300 align-top">
              {children}
            </td>
          ),

          // Links
          a: ({ href, children }) => {
            const isExternal = href?.startsWith("http://") || href?.startsWith("https://");
            return (
              <a
                href={href}
                target={isExternal ? "_blank" : undefined}
                rel={isExternal ? "noreferrer" : undefined}
                className="inline-flex items-center gap-1 font-semibold text-blue-600 underline decoration-blue-300 underline-offset-2 hover:text-blue-700 dark:text-cyan-400 dark:decoration-cyan-600 dark:hover:text-cyan-300 transition"
              >
                <span>{children}</span>
                {isExternal && <ExternalLink className="inline h-3 w-3 shrink-0" />}
              </a>
            );
          },

          // Horizontal rule
          hr: () => (
            <hr className="my-8 border-slate-200/80 dark:border-white/10" />
          ),

          // Strong & Emphasis
          strong: ({ children }) => (
            <strong className="font-bold text-slate-900 dark:text-white">
              {children}
            </strong>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
