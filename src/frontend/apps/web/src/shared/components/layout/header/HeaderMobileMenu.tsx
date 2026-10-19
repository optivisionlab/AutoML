"use client";

import { useState } from "react";
import Link from "next/link";
import { signIn, useSession } from "next-auth/react";
import { ChevronDown, ExternalLink } from "lucide-react";
import { useTranslations } from "next-intl";
import { FaGithub } from "react-icons/fa";
import { Button } from "@/shared/components/ui/button";
import {
  headerDropdownCategories,
  headerDirectLinks,
} from "./header-config";

interface HeaderMobileMenuProps {
  onClose: () => void;
}

export default function HeaderMobileMenu({ onClose }: HeaderMobileMenuProps) {
  const t = useTranslations("Header");
  const { data: session } = useSession();
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);

  const toggleCategory = (id: string) => {
    setExpandedCategory((prev) => (prev === id ? null : id));
  };

  return (
    <div className="absolute left-3 right-3 top-[66px] z-40 max-h-[82vh] overflow-y-auto rounded-2xl border border-white/10 bg-[#0B0F19]/95 p-4 text-white shadow-[0_20px_50px_rgba(0,0,0,0.8)] backdrop-blur-2xl animate-in fade-in-0 zoom-in-95 lg:hidden">
      <div className="flex flex-col gap-2">
        {/* Categories with expandable accordion */}
        {headerDropdownCategories.map((category) => {
          const isExpanded = expandedCategory === category.id;

          return (
            <div
              key={category.id}
              className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]"
            >
              <button
                type="button"
                onClick={() => toggleCategory(category.id)}
                className="flex w-full items-center justify-between px-3.5 py-3 text-left text-sm font-bold text-white transition hover:bg-white/5"
              >
                <span>{t(category.labelKey)}</span>
                <ChevronDown
                  className={`h-4 w-4 text-slate-400 transition-transform duration-200 ${
                    isExpanded ? "rotate-180 text-white" : ""
                  }`}
                />
              </button>

              {isExpanded && (
                <div className="flex flex-col gap-1 border-t border-white/10 px-2 py-2">
                  {category.items.map((item) => {
                    const Icon = item.icon;
                    const isExternal = item.external;

                    const inner = (
                      <div className="flex items-start gap-3 rounded-lg p-2 transition hover:bg-white/10">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/5 text-blue-400">
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-bold text-white">
                              {t(item.titleKey)}
                            </span>
                            {item.badge && (
                              <span className="rounded-full bg-blue-500/20 px-1.5 py-0.2 text-[9px] font-extrabold text-blue-300">
                                {item.badge}
                              </span>
                            )}
                            {isExternal && (
                              <ExternalLink className="h-3 w-3 text-slate-400" />
                            )}
                          </div>
                          <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-400">
                            {t(item.descKey)}
                          </p>
                        </div>
                      </div>
                    );

                    if (isExternal) {
                      return (
                        <a
                          key={item.key}
                          href={item.href}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={onClose}
                        >
                          {inner}
                        </a>
                      );
                    }

                    return (
                      <Link
                        key={item.key}
                        href={item.href}
                        onClick={onClose}
                      >
                        {inner}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {/* Direct Links */}
        {headerDirectLinks.map((link) => (
          <Link
            key={link.key}
            href={link.href}
            onClick={onClose}
            className="rounded-xl px-3.5 py-2.5 text-sm font-bold text-slate-200 transition hover:bg-white/10 hover:text-white"
          >
            {t(link.labelKey)}
          </Link>
        ))}

        {/* Mobile GitHub link */}
        <Link
          href="https://github.com/optivisionlab/AutoML"
          target="_blank"
          rel="noopener noreferrer"
          onClick={onClose}
          className="flex items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-sm font-bold text-slate-200 transition hover:bg-white/10 hover:text-white"
        >
          <FaGithub className="h-4 w-4" />
          <span>GitHub Repository</span>
        </Link>

        {/* Auth / CTA Buttons */}
        <div className="mt-2 flex flex-col gap-2 border-t border-white/10 pt-3">
          {session ? (
            <Button
              asChild
              className="w-full rounded-xl bg-blue-600 font-bold text-white hover:bg-blue-500"
            >
              <Link href="/dashboard" onClick={onClose}>
                {t("dashboard")}
              </Link>
            </Button>
          ) : (
            <>
              <Button
                onClick={() => {
                  onClose();
                  signIn();
                }}
                className="w-full rounded-xl border border-white/10 bg-white/10 font-bold text-white hover:bg-white/15"
              >
                {t("login")}
              </Button>
              <Button
                asChild
                className="w-full rounded-xl bg-blue-600 font-bold text-white hover:bg-blue-500"
              >
                <Link href="/register" onClick={onClose}>
                  {t("trial")}
                </Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
