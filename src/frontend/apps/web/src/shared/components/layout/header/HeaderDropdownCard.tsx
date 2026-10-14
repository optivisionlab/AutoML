"use client";

import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";
import { useTranslations } from "next-intl";
import { NavDropdownCategory } from "./header-config";

interface HeaderDropdownCardProps {
  category: NavDropdownCategory;
  onItemClick?: () => void;
}

export default function HeaderDropdownCard({
  category,
  onItemClick,
}: HeaderDropdownCardProps) {
  const t = useTranslations("Header");

  return (
    <div className="grid w-[680px] grid-cols-[1.55fr_1fr] gap-4 p-4 lg:w-[740px] lg:gap-5 lg:p-5">
      {/* List of items */}
      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 sm:gap-2">
        {category.items.map((item) => {
          const Icon = item.icon;
          const isExternal = item.external;

          const content = (
            <div className="group flex items-start gap-3 rounded-xl p-2.5 transition-all duration-200 hover:bg-white/[0.08] hover:ring-1 hover:ring-white/15">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-blue-400 transition-all duration-200 group-hover:border-blue-400/40 group-hover:bg-blue-500/20 group-hover:text-blue-300">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-xs font-bold text-white transition-colors group-hover:text-blue-300">
                    {t(item.titleKey)}
                  </span>
                  {item.badge && (
                    <span className="shrink-0 rounded-full border border-blue-400/30 bg-blue-500/15 px-1.5 py-0.2 text-[9px] font-black uppercase tracking-wider text-blue-300">
                      {item.badge}
                    </span>
                  )}
                  {isExternal && (
                    <ExternalLink className="h-3 w-3 text-slate-400 opacity-60 group-hover:opacity-100" />
                  )}
                </div>
                <p className="mt-1 line-clamp-2 text-[11px] font-medium leading-normal text-slate-400 transition-colors group-hover:text-slate-300">
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
                onClick={onItemClick}
                className="block outline-none"
              >
                {content}
              </a>
            );
          }

          return (
            <Link
              key={item.key}
              href={item.href}
              onClick={onItemClick}
              className="block outline-none"
            >
              {content}
            </Link>
          );
        })}
      </div>

      {/* Featured Callout Card (Roboflow Style) */}
      <div
        className={`relative flex flex-col justify-between overflow-hidden rounded-xl border border-white/10 bg-gradient-to-br ${category.callout.gradient} p-4.5 backdrop-blur-sm`}
      >
        <div className="relative z-10">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider text-white/90">
            <span>Featured</span>
          </div>
          <h4 className="mt-3 text-sm font-black leading-snug text-white">
            {t(category.callout.titleKey)}
          </h4>
          <p className="mt-2 text-xs font-medium leading-relaxed text-slate-300">
            {t(category.callout.descKey)}
          </p>
        </div>

        <div className="relative z-10 mt-5 pt-3 border-t border-white/10">
          {category.callout.external ? (
            <a
              href={category.callout.href}
              target="_blank"
              rel="noopener noreferrer"
              onClick={onItemClick}
              className="group inline-flex items-center gap-1.5 text-xs font-bold text-white transition-colors hover:text-blue-300"
            >
              <span>{t(category.callout.btnKey)}</span>
              <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-1" />
            </a>
          ) : (
            <Link
              href={category.callout.href}
              onClick={onItemClick}
              className="group inline-flex items-center gap-1.5 text-xs font-bold text-white transition-colors hover:text-blue-300"
            >
              <span>{t(category.callout.btnKey)}</span>
              <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-1" />
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
