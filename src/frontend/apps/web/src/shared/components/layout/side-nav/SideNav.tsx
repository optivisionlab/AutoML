"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  BrainCircuit,
  HelpCircle,
  Sparkles,
} from "lucide-react";
import { NavItems } from "@/shared/constants/nav-items";
import { cn } from "@/shared/lib/utils";
import { SideNavItem } from "./SideNavItem";
import { useTranslations } from "next-intl";

const isActivePath = (pathname: string, href: string) => {
  if (href === "/dashboard") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
};

export default function SideNav({
  collapsed,
  mobileOpen,
  onMobileOpenChange,
}: {
  collapsed: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}) {
  const pathname = usePathname();
  const currentPathname = pathname ?? "";
  const t = useTranslations("Sidebar");
  const { data: session, status } = useSession();

  if (status === "loading" || !session) return null;

  const navItems = NavItems(session.user?.role || "");

  const sidebarContent = (isMobile = false) => (
    <div className="flex h-full flex-col">
      {/* Top Header Bar của Sidebar: Đúng chuẩn h-14 ngang bằng với DashboardTopbar, không có kẻ ngang */}
      <div
        className={cn(
          "flex h-14 shrink-0 items-center px-4",
          collapsed && !isMobile ? "justify-center px-0" : "justify-start",
        )}
      >
        <Link
          href="/"
          onClick={() => onMobileOpenChange(false)}
          className={cn(
            "flex items-center gap-3 transition-opacity hover:opacity-90",
            collapsed && !isMobile && "justify-center",
          )}
          title={collapsed && !isMobile ? "HAutoML" : undefined}
        >
          {/* Logo to, rõ nét, sang trọng, vẫn căn giữa chuẩn trục dọc với Header */}
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white p-1 shadow-sm ring-1 ring-slate-200/80 dark:bg-white/10 dark:ring-white/15">
            <Image
              src="/logoHautoMLNotext.png"
              alt="HAutoML"
              width={34}
              height={34}
              className="h-8 w-8 object-contain"
              priority
            />
          </span>
          {(!collapsed || isMobile) && (
            <span className="leading-tight">
              <span className="block text-base font-black text-automl-ink dark:text-white">
                HAutoML
              </span>
              <span className="text-[11px] font-semibold text-automl-muted dark:text-white/55">
                {t("subtitle")}
              </span>
            </span>
          )}
        </Link>
      </div>

      {/* Nav List: Cuộn mượt, không còn icon thừa dưới logo khi đóng sidebar */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1.5">
        {navItems.map((item) => (
          <SideNavItem
            key={item.href}
            label={t(item.labelKey)}
            icon={item.icon}
            path={item.href}
            active={isActivePath(currentPathname, item.href)}
            collapsed={collapsed && !isMobile}
            onNavigate={() => onMobileOpenChange(false)}
          />
        ))}
      </div>

      {/* Bottom Section: Card giới thiệu & Hướng dẫn docs */}
      <div className="mt-auto shrink-0 p-3 pt-0">
        {(!collapsed || isMobile) && (
          <div className="mb-3 overflow-hidden rounded-2xl border border-automl-line bg-gradient-to-b from-automl-blue-soft to-automl-cyan-soft p-4 dark:border-white/10 dark:from-white/10 dark:to-white/5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-automl-blue shadow-xs">
              <BrainCircuit className="h-4 w-4" />
            </div>
            <p className="mt-3 text-xs font-black text-automl-ink dark:text-white">
              {t("centerTitle")}
            </p>
            <p className="mt-1 text-[11px] leading-4 text-automl-muted-strong dark:text-white/60">
              {t("centerBody")}
            </p>
            <div className="mt-3 flex items-center gap-1.5 rounded-xl bg-white/80 px-2.5 py-1.5 text-[11px] font-bold text-automl-blue dark:bg-white/10 dark:text-white">
              <Sparkles className="h-3.5 w-3.5" />
              <span>{t("readyWorkflow")}</span>
            </div>
          </div>
        )}

        <Link
          href="/docs"
          onClick={() => onMobileOpenChange(false)}
          title={collapsed && !isMobile ? t("docs") : undefined}
          className={cn(
            "flex items-center rounded-xl text-xs font-bold text-slate-500 transition hover:bg-slate-100 hover:text-automl-ink dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white",
            collapsed && !isMobile ? "justify-center p-2.5" : "gap-2.5 px-3 py-2.5",
          )}
        >
          <HelpCircle className="h-4 w-4" />
          {(!collapsed || isMobile) && <span>{t("docs")}</span>}
        </Link>
      </div>
    </div>
  );

  return (
    <>
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden border-r border-slate-200/70 bg-white shadow-[18px_0_50px_rgba(15,23,42,0.05)] transition-all duration-300 dark:border-white/10 dark:bg-automl-navy lg:flex lg:flex-col",
          collapsed ? "w-24" : "w-72",
        )}
      >
        {sidebarContent(false)}
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label={t("closeSidebar")}
            className="absolute inset-0 bg-slate-950/40"
            onClick={() => onMobileOpenChange(false)}
          />
          <aside className="relative flex h-full w-80 max-w-[86vw] flex-col border-r border-slate-200 bg-white shadow-2xl dark:border-white/10 dark:bg-automl-navy">
            {sidebarContent(true)}
          </aside>
        </div>
      )}
    </>
  );
}
