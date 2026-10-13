"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import HeaderDropdownCard from "./HeaderDropdownCard";
import {
  headerDropdownCategories,
  headerDirectLinks,
} from "./header-config";

export default function HeaderNav() {
  const t = useTranslations("Header");
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <nav className="hidden items-center gap-1 lg:flex xl:gap-1.5">
      {headerDropdownCategories.map((category) => {
        const isOpen = openId === category.id;

        return (
          <DropdownMenu
            key={category.id}
            open={isOpen}
            onOpenChange={(open) => setOpenId(open ? category.id : null)}
          >
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="group flex items-center gap-1 rounded-xl px-3 py-1.5 text-xs font-bold text-white/90 transition-all duration-150 hover:bg-white/10 hover:text-white focus:outline-none data-[state=open]:bg-white/15 data-[state=open]:text-white xl:text-sm"
              >
                <span>{t(category.labelKey)}</span>
                <ChevronDown
                  className={`h-3.5 w-3.5 text-slate-400 transition-transform duration-200 group-hover:text-white ${
                    isOpen ? "rotate-180 text-white" : ""
                  }`}
                />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="center"
              sideOffset={14}
              className="z-50 overflow-hidden rounded-2xl border border-white/10 bg-[#0B0F19]/95 p-0 text-white shadow-[0_24px_50px_rgba(0,0,0,0.65)] backdrop-blur-2xl animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95"
            >
              <HeaderDropdownCard
                category={category}
                onItemClick={() => setOpenId(null)}
              />
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}

      {headerDirectLinks.map((link) => (
        <Link
          key={link.key}
          href={link.href}
          className="rounded-xl px-3 py-1.5 text-xs font-bold text-white/90 transition-all duration-150 hover:bg-white/10 hover:text-white xl:text-sm"
        >
          {t(link.labelKey)}
        </Link>
      ))}
    </nav>
  );
}
