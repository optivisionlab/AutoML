"use client";

import { ReactNode, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import Header from "@/shared/components/layout/header/Header";
import Footer from "@/shared/components/layout/footer/Footer";
import SideNav from "@/shared/components/layout/side-nav/SideNav";
import DashboardTopbar from "@/shared/components/layout/DashboardTopbar";
import { Toaster } from "@/shared/components/ui/toaster";
import AppLoading from "@/shared/components/common/AppLoading";
import { cn } from "@/shared/lib/utils";
import { useTranslations } from "next-intl";
import { useNotificationSocket } from "@/features/notifications/hooks/useNotificationSocket";

const authRoutes = new Set([
  "/login",
  "/register",
  "/forgot-pw",
  "/change-pw",
  "/verify-otp",
  "/verify-email",
  "/google",
]);

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
  // Kích hoạt kết nối MQTT WebSocket toàn cục khi người dùng đăng nhập
  useNotificationSocket();

  const t = useTranslations("Common");
  const pathname = usePathname();
  const currentPathname = pathname ?? "";
  const { data: session, status } = useSession();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const isAuthRoute = authRoutes.has(currentPathname);
  const isLandingRoute = currentPathname === "/";
  const isDocsRoute = currentPathname.startsWith("/docs");
  const isMarketingRoute =
    isLandingRoute ||
    currentPathname.startsWith("/team") ||
    currentPathname.startsWith("/community");

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

  if (isDocsRoute) {
    return (
      <div className="min-h-svh bg-white dark:bg-slate-950">
        {children}
        <Toaster />
      </div>
    );
  }

  if (isAuthRoute) {
    return (
      <div className="min-h-svh bg-slate-50 text-automl-ink dark:bg-[#070A13] dark:text-white">
        {children}
        <Toaster />
      </div>
    );
  }

  if (isMarketingRoute) {
    return (
      <div className="flex min-h-svh flex-col justify-between bg-white text-automl-ink dark:bg-[#070A13] dark:text-white">
        <div className="flex flex-1 flex-col">
          <Header />
          <div className="flex-1">{children}</div>
        </div>
        <Footer />
        <Toaster />
      </div>
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
      <div className="flex min-h-svh flex-col justify-between bg-white text-automl-ink dark:bg-[#070A13] dark:text-white">
        <div className="flex flex-1 flex-col">
          <Header />
          <div className="flex-1">{children}</div>
        </div>
        <Footer />
        <Toaster />
      </div>
    );
  }

  return (
    <div className="min-h-svh bg-slate-50 text-automl-ink dark:bg-[#020617] dark:text-white">
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
