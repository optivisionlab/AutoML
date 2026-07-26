"use client";

import Link from "next/link";
import { useEffect } from "react";
import { signOut, useSession } from "next-auth/react";
import {
  Bell,
  ChevronDown,
  LayoutDashboard,
  Menu,
  LogOut,
  Settings,
  Search,
  User2,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import ModeToggle from "@/components/mode-toggle";
import { useGetUserQuery } from "@/redux/api/userApi";
import LanguageToggle from "@/components/language-toggle";
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
  const { data: user, refetch: refetchUser } = useGetUserQuery(
    username ?? "",
    { skip: !username },
  );
  const avatarUrl = getAvatarSrc(user?.avatar ?? user?.image);

  useEffect(() => {
    if (!username) return;

    const handleAvatarUpdate = () => refetchUser();
    window.addEventListener("avatar-updated", handleAvatarUpdate);
    return () =>
      window.removeEventListener("avatar-updated", handleAvatarUpdate);
  }, [refetchUser, username]);

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/85 backdrop-blur-xl dark:border-white/10 dark:bg-automl-navy/85">
      <div className="flex h-20 items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Button
          variant="outline"
          size="icon"
          onClick={onMobileSidebarOpen}
          className="h-11 w-11 rounded-2xl border-slate-200 bg-white shadow-none hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 lg:hidden"
          aria-label={t("openSidebar")}
        >
          <Menu className="h-5 w-5" />
        </Button>

        <Button
          variant="outline"
          size="icon"
          onClick={onDesktopSidebarToggle}
          className="hidden h-11 w-11 rounded-2xl border-slate-200 bg-white shadow-none hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 lg:inline-flex"
          aria-label={sidebarCollapsed ? t("openSidebar") : t("collapseSidebar")}
          title={sidebarCollapsed ? t("openSidebar") : t("collapseSidebar")}
        >
          <Menu className="h-5 w-5" />
        </Button>

        <div className="flex items-center gap-3 lg:hidden">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-automl-blue-soft font-black text-automl-blue">
            H
          </span>
          <span className="hidden text-sm font-black text-automl-ink dark:text-white sm:block">
            HAutoML
          </span>
        </div>

        <div className="hidden min-w-0 flex-1 md:block">
          <div className="relative max-w-xl">
            <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              placeholder={t("searchPlaceholder")}
              className="h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 pl-11 pr-4 text-sm font-medium outline-none transition placeholder:text-slate-400 focus:border-automl-blue focus:bg-white focus:ring-4 focus:ring-automl-blue/10 dark:border-white/10 dark:bg-white/10 dark:text-white"
            />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <ModeToggle />
          <LanguageToggle />

          <Button
            variant="outline"
            size="icon"
            className="relative h-11 w-11 rounded-2xl border-slate-200 bg-white shadow-none hover:bg-slate-50 dark:border-white/10 dark:bg-white/10"
          >
            <Bell className="h-5 w-5 text-slate-500 dark:text-white" />
            <span className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full bg-automl-blue ring-2 ring-white" />
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-2 py-1.5 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 dark:hover:bg-white/15">
                <Avatar className="h-10 w-10">
                  <AvatarImage src={avatarUrl} alt="avatar" />
                  <AvatarFallback className="bg-automl-blue-soft font-black text-automl-blue">
                    {username?.slice(0, 2).toUpperCase() ?? <User2 className="h-5 w-5" />}
                  </AvatarFallback>
                </Avatar>
                <span className="hidden text-left leading-tight sm:block">
                  <span className="block text-sm font-black text-automl-ink dark:text-white">
                    {session?.user?.username ?? "HAutoML"}
                  </span>
                  <span className="text-xs font-semibold text-automl-muted dark:text-white/55">
                    {roleLabel}
                  </span>
                </span>
                <ChevronDown className="hidden h-4 w-4 text-slate-400 sm:block" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-72 rounded-3xl border-slate-200 p-3 shadow-xl shadow-slate-900/10"
            >
              <DropdownMenuLabel className="p-0">
                <div className="flex items-center gap-3 rounded-2xl bg-slate-50 p-3 dark:bg-white/10">
                  <Avatar className="h-12 w-12">
                    <AvatarImage src={avatarUrl} alt="avatar" />
                    <AvatarFallback className="bg-automl-blue-soft font-black text-automl-blue">
                      {username?.slice(0, 2).toUpperCase() ?? "HA"}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black text-automl-ink dark:text-white">
                      {session?.user?.username ?? "HAutoML"}
                    </p>
                    <p className="text-xs font-semibold text-automl-muted dark:text-white/55">
                      {roleLabel}
                    </p>
                  </div>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="my-3" />
              <DropdownMenuItem asChild className="cursor-pointer rounded-2xl px-3 py-3 font-bold">
                <Link href="/profile" className="flex items-center gap-3">
                  <User2 className="h-4 w-4 text-automl-blue" />
                  {t("profile")}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild className="cursor-pointer rounded-2xl px-3 py-3 font-bold">
                <Link href="/dashboard" className="flex items-center gap-3">
                  <LayoutDashboard className="h-4 w-4 text-automl-blue" />
                  {t("dashboard")}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild className="cursor-pointer rounded-2xl px-3 py-3 font-bold">
                <Link href="/settings" className="flex items-center gap-3">
                  <Settings className="h-4 w-4 text-automl-blue" />
                  {t("settings")}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator className="my-3" />
              <DropdownMenuItem
                onClick={() => signOut()}
                className="cursor-pointer rounded-2xl px-3 py-3 font-bold text-red-600 focus:text-red-600"
              >
                <LogOut className="mr-3 h-4 w-4" />
                {t("logout")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
