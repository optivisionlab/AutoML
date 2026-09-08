"use client";

import React from "react";
import Link from "next/link";
import { cn } from "@/shared/lib/utils";

import { useTranslations } from "next-intl";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbNavProps {
  items: BreadcrumbItem[];
  className?: string;
}

export default function BreadcrumbNav({ items, className }: BreadcrumbNavProps) {
  const common = useTranslations("Common");

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn(
        "flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400 select-none",
        className
      )}
    >
      <Link
        href="/"
        className="transition-colors hover:text-blue-600 dark:hover:text-cyan-400 font-medium"
      >
        {common("home")}
      </Link>

      {items.map((item, index) => {
        const isLast = index === items.length - 1;

        return (
          <span key={`${item.label}-${index}`} className="flex items-center gap-2">
            <span className="text-slate-400 dark:text-slate-600">/</span>
            {isLast || !item.href ? (
              <span className="font-bold text-blue-600 dark:text-cyan-400 truncate">
                {item.label}
              </span>
            ) : (
              <Link
                href={item.href}
                className="transition-colors hover:text-blue-600 dark:hover:text-cyan-400 font-medium truncate"
              >
                {item.label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
