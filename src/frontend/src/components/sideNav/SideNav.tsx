"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  BrainCircuit,
  HelpCircle,
  PanelLeftOpen,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { NavItems } from "@/config";
import { cn } from "@/lib/utils";
import { SideNavItem } from "./SideNavItem";
import { useTranslations } from "next-intl";

const isActivePath = (pathname: string, href: string) => {
  if (href === "/dashboard") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
};

export default function SideNav({
  collapsed,
  onCollapsedChange,
  mobileOpen,
  onMobileOpenChange,
}: {
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}) {
  const pathname = usePathname();
  const t = useTranslations("Sidebar");
  const { data: session, status } = useSession();

  if (status === "loading" || !session) return null;

  const navItems = NavItems(session.user?.role || "");

  const sidebarContent = (isMobile = false) => (
    <>
      <div
        className={cn(
          "flex items-center",
          collapsed && !isMobile ? "justify-center" : "justify-start",
        )}
      >
        <Link
          href="/"
          onClick={() => onMobileOpenChange(false)}
          className={cn(
            "flex items-center gap-3 rounded-2xl px-2 py-1",
            collapsed && !isMobile && "justify-center px-0",
          )}
          title={collapsed && !isMobile ? "HAutoML" : undefined}
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white p-2 shadow-sm ring-1 ring-slate-200 dark:bg-white/10 dark:ring-white/10">
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
              <span className="block text-lg font-black text-automl-ink dark:text-white">
                HAutoML
              </span>
              <span className="text-xs font-semibold text-automl-muted dark:text-white/55">
                {t("subtitle")}
              </span>
            </span>
          )}
        </Link>
      </div>

      {collapsed && !isMobile && (
        <Button
          variant="outline"
          size="icon"
          onClick={() => onCollapsedChange(false)}
          className="mx-auto mt-5 h-10 w-10 rounded-2xl border-slate-200 shadow-none dark:border-white/10 dark:bg-white/10"
          title={t("openSidebar")}
        >
          <PanelLeftOpen className="h-5 w-5" />
        </Button>
      )}

      <div className="mt-8 space-y-2">
        {navItems.map((item) => (
          <SideNavItem
            key={item.href}
            label={t(item.labelKey)}
            icon={item.icon}
            path={item.href}
            active={isActivePath(pathname, item.href)}
            collapsed={collapsed && !isMobile}
            onNavigate={() => onMobileOpenChange(false)}
          />
        ))}
      </div>

      {(!collapsed || isMobile) && (
        <div className="mt-auto overflow-hidden rounded-3xl border border-automl-line bg-gradient-to-b from-automl-blue-soft to-automl-cyan-soft p-5 dark:border-white/10 dark:from-white/10 dark:to-white/5">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-automl-blue shadow-sm">
            <BrainCircuit className="h-5 w-5" />
          </div>
          <p className="mt-4 text-sm font-black text-automl-ink dark:text-white">
            {t("centerTitle")}
          </p>
          <p className="mt-2 text-xs leading-5 text-automl-muted-strong dark:text-white/60">
            {t("centerBody")}
          </p>
          <div className="mt-4 flex items-center gap-2 rounded-2xl bg-white/80 px-3 py-2 text-xs font-bold text-automl-blue dark:bg-white/10 dark:text-white">
            <Sparkles className="h-4 w-4" />
            {t("readyWorkflow")}
          </div>
        </div>
      )}

      <Link
        href="/#introduction"
        onClick={() => onMobileOpenChange(false)}
        title={collapsed && !isMobile ? t("docs") : undefined}
        className={cn(
          "mt-4 flex items-center rounded-2xl text-sm font-bold text-slate-500 transition hover:bg-slate-100 hover:text-automl-ink dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white",
          collapsed && !isMobile ? "justify-center px-2 py-3" : "gap-3 px-4 py-3",
        )}
      >
        <HelpCircle className="h-5 w-5" />
        {(!collapsed || isMobile) && t("docs")}
      </Link>
    </>
  );

  return (
    <>
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden border-r border-slate-200/70 bg-white px-5 py-6 shadow-[18px_0_50px_rgba(15,23,42,0.05)] transition-all duration-300 dark:border-white/10 dark:bg-automl-navy lg:flex lg:flex-col",
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
          <aside className="relative flex h-full w-80 max-w-[86vw] flex-col border-r border-slate-200 bg-white px-5 py-6 shadow-2xl dark:border-white/10 dark:bg-automl-navy">
            {sidebarContent(true)}
          </aside>
        </div>
      )}
    </>
  );
}
