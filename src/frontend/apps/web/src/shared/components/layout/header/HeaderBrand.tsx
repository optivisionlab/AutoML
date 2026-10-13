"use client";

import Image from "next/image";
import Link from "next/link";
import { useTranslations } from "next-intl";

interface HeaderBrandProps {
  onNavigate?: () => void;
}

export default function HeaderBrand({ onNavigate }: HeaderBrandProps) {
  const t = useTranslations("Header");

  return (
    <Link
      href="/"
      className="group flex shrink-0 items-center gap-2.5 transition-opacity hover:opacity-90 sm:gap-3"
      prefetch={false}
      onClick={onNavigate}
    >
      <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 p-1.5 ring-1 ring-white/15 backdrop-blur transition-all duration-200 group-hover:scale-105 group-hover:bg-white/15 group-hover:ring-blue-400/30">
        <Image
          src="/logoHautoMLNotext.png"
          alt="HAutoML"
          width={30}
          height={30}
          className="h-7 w-7 object-contain drop-shadow-[0_2px_8px_rgba(37,99,255,0.4)]"
          priority
        />
      </span>
      <span className="flex flex-col">
        <span className="block text-base font-black leading-tight tracking-tight text-white transition-colors group-hover:text-blue-200">
          HAutoML
        </span>
        <span className="text-[11px] font-semibold leading-none text-slate-400">
          {t("brandSubtitle")}
        </span>
      </span>
    </Link>
  );
}
