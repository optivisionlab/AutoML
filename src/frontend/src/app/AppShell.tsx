"use client";

import { ReactNode, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import Header from "@/components/header/Header";
import SideNav from "@/components/sideNav/SideNav";
import DashboardTopbar from "@/components/appShell/DashboardTopbar";
import { Toaster } from "@/components/ui/toaster";
import AppLoading from "@/components/common/AppLoading";
import { cn } from "@/lib/utils";
import { useTranslations } from "next-intl";

const authRoutes = new Set(["/login", "/register"]);

const isChunkLoadError = (error: unknown) => {
  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "";

  return (
    message.includes("Loading chunk") ||
    message.includes("ChunkLoadError") ||
    message.includes("failed to fetch dynamically imported module")
  );
};

export default function AppShell({ children }: { children: ReactNode }) {
  const t = useTranslations("Common");
  const pathname = usePathname();
  const { data: session, status } = useSession();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const isAuthRoute = authRoutes.has(pathname);
  const isLandingRoute = pathname === "/";

  useEffect(() => {
    if (typeof window === "undefined") return;

    const retryKey = `hautoml:chunk-retry:${window.location.pathname}`;
    const clearRetry = window.setTimeout(() => {
      sessionStorage.removeItem(retryKey);
    }, 10000);

    const recoverFromChunkError = (error: unknown) => {
      if (!isChunkLoadError(error)) return;

      if (sessionStorage.getItem(retryKey) === "1") {
        console.error("Không thể tải chunk sau khi đã reload lại trang.", error);
        return;
      }

      sessionStorage.setItem(retryKey, "1");
      window.location.reload();
    };

    const handleWindowError = (event: ErrorEvent) => {
      recoverFromChunkError(event.error || event.message);
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      recoverFromChunkError(event.reason);
    };

    window.addEventListener("error", handleWindowError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      window.clearTimeout(clearRetry);
      window.removeEventListener("error", handleWindowError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, [pathname]);

  if (isAuthRoute) {
    return (
      <div className="min-h-svh bg-automl-canvas">
        {children}
        <Toaster />
      </div>
    );
  }

  if (isLandingRoute) {
    return (
      <>
        <Header />
        {children}
        <Toaster />
      </>
    );
  }

  if (status === "loading") {
    return (
      <div className="min-h-svh bg-white dark:bg-[#020617]">
        <AppLoading variant="page" label={t("checkingSession")} />
      </div>
    );
  }

  if (!session) {
    return (
      <>
        <Header />
        {children}
        <Toaster />
      </>
    );
  }

  return (
    <div className="min-h-svh bg-white text-automl-ink dark:bg-[#020617] dark:text-white">
      <SideNav
        collapsed={sidebarCollapsed}
        onCollapsedChange={setSidebarCollapsed}
        mobileOpen={mobileSidebarOpen}
        onMobileOpenChange={setMobileSidebarOpen}
      />
      <div
        className={cn(
          "min-h-svh transition-[padding] duration-300",
          sidebarCollapsed ? "lg:pl-24" : "lg:pl-72",
        )}
      >
        <DashboardTopbar
          sidebarCollapsed={sidebarCollapsed}
          onDesktopSidebarToggle={() => setSidebarCollapsed((value) => !value)}
          onMobileSidebarOpen={() => setMobileSidebarOpen(true)}
        />
        <main className="w-full px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
      <Toaster />
    </div>
  );
}
