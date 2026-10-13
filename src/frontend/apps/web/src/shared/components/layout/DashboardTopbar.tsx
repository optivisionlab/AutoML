"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect } from "react";
import { signOut, useSession } from "next-auth/react";
import {
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  User2,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/shared/components/ui/avatar";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import ModeToggle from "@/shared/components/mode-toggle";
import { useGetUserQuery } from "@/core/api/userApi";
import LanguageToggle from "@/shared/components/language-toggle";
import NotificationBell from "@/features/notifications/components/NotificationBell";
import { useTranslations } from "next-intl";

const getAvatarSrc = (avatar?: string | null) => {
  if (!avatar) return undefined;

  if (
    avatar.startsWith("http://") ||
    avatar.startsWith("https://") ||
    avatar.startsWith("/") ||
    avatar.startsWith("data:image")
  ) {
    return avatar;
  }

  return `data:image/png;base64,${avatar}`;
};

export default function DashboardTopbar({
  sidebarCollapsed,
  onDesktopSidebarToggle,
  onMobileSidebarOpen,
}: {
  sidebarCollapsed: boolean;
  onDesktopSidebarToggle: () => void;
  onMobileSidebarOpen: () => void;
}) {
  const t = useTranslations("Topbar");
  const { data: session } = useSession();
  const username = session?.user?.username;
  const roleLabel =
    session?.user?.role === "admin" ? t("adminRole") : t("userRole");
  const { data: userResponse, refetch: refetchUser } = useGetUserQuery(
    username ?? "",
    { skip: !username },
  );
  const userData = userResponse?.data;
  const avatarUrl = getAvatarSrc(userData?.avatar ?? userData?.image);

  useEffect(() => {
    if (!username) return;

    const handleAvatarUpdate = () => refetchUser();
    window.addEventListener("avatar-updated", handleAvatarUpdate);
    return () =>
      window.removeEventListener("avatar-updated", handleAvatarUpdate);
  }, [refetchUser, username]);

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl dark:border-white/10 dark:bg-automl-navy/90 transition-colors">
      <div className="flex h-14 items-center justify-between gap-3 px-3 sm:px-4 lg:px-6">
        {/* Khối bên trái: Nút đóng/mở sidebar (nhỏ gọn, đồng đều h-10 w-10 ngang bằng với logo) */}
        <div className="flex items-center gap-2">
          {/* Mobile Sidebar Toggle Button */}
          <Button
            variant="outline"
            size="icon"
            onClick={onMobileSidebarOpen}
            className="h-10 w-10 rounded-xl border-slate-200/80 bg-white text-slate-600 shadow-none hover:bg-slate-50 hover:text-slate-900 dark:border-white/10 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/15 dark:hover:text-white transition-all active:scale-95 lg:hidden"
            aria-label={t("openSidebar")}
          >
            <Menu className="h-4.5 w-4.5" />
          </Button>

          {/* Desktop Sidebar Toggle Button (h-10 w-10, bo góc rounded-xl đồng bộ chuẩn xác với logo h-10) */}
          <Button
            variant="outline"
            size="icon"
            onClick={onDesktopSidebarToggle}
            className="hidden h-10 w-10 rounded-xl border-slate-200/80 bg-white text-slate-600 shadow-none hover:bg-slate-50 hover:text-slate-900 dark:border-white/10 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/15 dark:hover:text-white transition-all active:scale-95 lg:inline-flex"
            aria-label={sidebarCollapsed ? t("openSidebar") : t("collapseSidebar")}
            title={sidebarCollapsed ? t("openSidebar") : t("collapseSidebar")}
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen className="h-4.5 w-4.5" />
            ) : (
              <PanelLeftClose className="h-4.5 w-4.5" />
            )}
          </Button>

          {/* Logo rút gọn trên mobile */}
          <div className="flex items-center gap-2 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white p-1 ring-1 ring-slate-200/80 dark:bg-white/10 dark:ring-white/10 shadow-xs">
              <Image
                src="/logoHautoMLNotext.png"
                alt="HAutoML"
                width={24}
                height={24}
                className="h-6 w-6 object-contain"
              />
            </span>
            <span className="text-xs font-black text-automl-ink dark:text-white">
              HAutoML
            </span>
          </div>
        </div>

        {/* Khối bên phải: Theme, Ngôn ngữ (kèm cờ VN/EN), Thông báo, Profile - Tất cả đồng đều h-10 rounded-xl */}
        <div className="flex items-center gap-2">
          {/* Theme Toggle */}
          <ModeToggle className="h-10 w-10 rounded-xl border-slate-200/80 bg-white dark:border-white/10 dark:bg-white/10" />

          {/* Language Toggle với Cờ Việt Nam & English */}
          <LanguageToggle className="h-10 px-3 rounded-xl border-slate-200/80 bg-white dark:border-white/10 dark:bg-white/10" />

          {/* Chuông thông báo Real-time & Mô phỏng MQTT */}
          <NotificationBell />

          {/* Dropdown User Profile (chiều cao h-10 đồng đều tuyệt đối) */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex h-10 items-center gap-2 rounded-xl border border-slate-200/80 bg-white px-2 text-slate-700 shadow-none transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 dark:text-white dark:hover:bg-white/15 active:scale-95">
                <Avatar className="h-6 w-6 ring-1 ring-slate-200/80 dark:ring-white/10">
                  <AvatarImage src={avatarUrl} alt="avatar" />
                  <AvatarFallback className="bg-automl-blue-soft text-[9px] font-black text-automl-blue">
                    {username?.slice(0, 2).toUpperCase() ?? <User2 className="h-3 w-3" />}
                  </AvatarFallback>
                </Avatar>
                <span className="hidden text-left leading-tight sm:block">
                  <span className="block text-xs font-black text-automl-ink dark:text-white">
                    {session?.user?.username ?? "HAutoML"}
                  </span>
                  <span className="text-[10px] font-semibold text-automl-muted dark:text-white/55">
                    {roleLabel}
                  </span>
                </span>
                <ChevronDown className="hidden h-3 w-3 text-slate-400 sm:block opacity-60 ml-0.5" />
              </button>
            </DropdownMenuTrigger>

            <DropdownMenuContent
              align="end"
              className="w-64 rounded-2xl border-slate-200/80 bg-white p-1.5 shadow-xl dark:border-white/10 dark:bg-slate-950 backdrop-blur-xl"
            >
              <DropdownMenuLabel className="p-0">
                <div className="flex items-center gap-2.5 rounded-xl bg-slate-50 p-2.5 dark:bg-white/10">
                  <Avatar className="h-9 w-9">
                    <AvatarImage src={avatarUrl} alt="avatar" />
                    <AvatarFallback className="bg-automl-blue-soft text-xs font-black text-automl-blue">
                      {username?.slice(0, 2).toUpperCase() ?? "HA"}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-black text-automl-ink dark:text-white">
                      {session?.user?.username ?? "HAutoML"}
                    </p>
                    <p className="truncate text-[10px] font-semibold text-automl-muted dark:text-white/55">
                      {roleLabel}
                    </p>
                  </div>
                </div>
              </DropdownMenuLabel>

              <DropdownMenuSeparator className="my-1.5" />

              <DropdownMenuItem asChild className="cursor-pointer rounded-xl px-2.5 py-2 text-xs font-bold">
                <Link href="/profile" className="flex items-center gap-2.5">
                  <User2 className="h-4 w-4 text-automl-blue" />
                  <span>{t("profile")}</span>
                </Link>
              </DropdownMenuItem>

              <DropdownMenuItem asChild className="cursor-pointer rounded-xl px-2.5 py-2 text-xs font-bold">
                <Link href="/dashboard" className="flex items-center gap-2.5">
                  <LayoutDashboard className="h-4 w-4 text-automl-blue" />
                  <span>{t("dashboard")}</span>
                </Link>
              </DropdownMenuItem>

              <DropdownMenuItem asChild className="cursor-pointer rounded-xl px-2.5 py-2 text-xs font-bold">
                <Link href="/settings" className="flex items-center gap-2.5">
                  <Settings className="h-4 w-4 text-automl-blue" />
                  <span>{t("settings")}</span>
                </Link>
              </DropdownMenuItem>

              <DropdownMenuSeparator className="my-1.5" />

              <DropdownMenuItem
                onClick={() => signOut()}
                className="cursor-pointer rounded-xl px-2.5 py-2 text-xs font-bold text-red-600 focus:text-red-600 focus:bg-red-50 dark:focus:bg-red-950/20"
              >
                <LogOut className="mr-2 h-4 w-4" />
                <span>{t("logout")}</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
