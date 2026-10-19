"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { useTheme } from "next-themes";
import {
  Bell,
  Database,
  Moon,
  Palette,
  ShieldCheck,
  Sun,
  Monitor,
  Zap,
  Edit3,
  User,
  Table2,
  LayoutGrid,
  Info,
  ArrowUpRight,
} from "lucide-react";
import { Switch } from "@/shared/components/ui/switch";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/shared/components/ui/dialog";
import { cn } from "@/shared/lib/utils";
import { useAppSettings } from "@/shared/hooks/useAppSettings";

type SettingsTab = "tables" | "appearance" | "notifications" | "account";

const PAGE_SIZE_OPTIONS = [5, 10, 15, 20, 50];

const themeOptions = [
  {
    value: "light",
    label: "Sáng",
    description: "Giao diện sáng rõ, độ tương phản cao cho môi trường làm việc ban ngày.",
    icon: Sun,
  },
  {
    value: "dark",
    label: "Tối",
    description: "Giao diện tối giúp dịu mắt, tiết kiệm năng lượng và tập trung cao độ.",
    icon: Moon,
  },
  {
    value: "system",
    label: "Theo hệ thống",
    description: "Tự động đồng bộ theo giao diện của hệ điều hành trên thiết bị của bạn.",
    icon: Monitor,
  },
];

export default function SettingsPage() {
  const { data: session } = useSession();
  const { theme, setTheme } = useTheme();
  const { settings, updateSettings, isLoaded } = useAppSettings();

  const [mounted, setMounted] = useState(false);
  const [activeTab, setActiveTab] = useState<SettingsTab>("tables");
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [tempWorkspaceName, setTempWorkspaceName] = useState("");
  const [customPageSize, setCustomPageSize] = useState("");

  useEffect(() => {
    setMounted(true);
  }, []);

  const currentTheme = mounted ? theme ?? "system" : "system";
  const userRole = session?.user?.role === "admin" ? "Quản trị viên (Admin)" : "Người dùng (User)";
  const username = session?.user?.username || "Người dùng";
  const workspaceName = settings.workspaceName || `${username}'s Workspace`;

  const handleOpenRename = () => {
    setTempWorkspaceName(workspaceName);
    setIsRenameDialogOpen(true);
  };

  const handleSaveWorkspaceName = () => {
    if (tempWorkspaceName.trim()) {
      updateSettings({ workspaceName: tempWorkspaceName.trim() });
    }
    setIsRenameDialogOpen(false);
  };

  const handlePageSizeSelect = (size: number) => {
    updateSettings({ tablePageSize: size });
  };

  const handleApplyCustomPageSize = () => {
    const parsed = parseInt(customPageSize, 10);
    if (!isNaN(parsed) && parsed >= 1 && parsed <= 100) {
      updateSettings({ tablePageSize: parsed });
      setCustomPageSize("");
    }
  };

  return (
    <div className="min-h-[calc(100vh-5rem)]">
      {/* Top Header & Breadcrumbs theo phong cách ảnh mẫu */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200/80 pb-4 dark:border-white/10">
        <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <span className="font-semibold text-slate-800 dark:text-slate-200">
            {workspaceName}
          </span>
          <span>/</span>
          <span className="font-medium text-slate-500 dark:text-slate-400">Cài đặt</span>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={handleOpenRename}
          className="h-9 gap-1.5 rounded-xl border-slate-200/90 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:text-slate-200 dark:hover:bg-white/10 w-fit"
        >
          <Edit3 className="h-3.5 w-3.5" />
          Đổi tên Workspace
        </Button>
      </div>

      {/* Main Layout: Sidebar Sub-Nav bên trái & Khu vực nội dung bên phải */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[260px_1fr]">
        {/* Left Sub-Navigation Sidebar */}
        <aside className="space-y-6">
          {/* USER ACCOUNT Section */}
          <div>
            <p className="px-3 text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              Tài khoản người dùng
            </p>
            <div className="mt-2 space-y-1">
              <button
                type="button"
                onClick={() => setActiveTab("account")}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-semibold transition-all",
                  activeTab === "account"
                    ? "bg-blue-50/80 text-blue-700 shadow-xs dark:bg-blue-950/40 dark:text-blue-300"
                    : "text-slate-600 hover:bg-slate-100/70 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white"
                )}
              >
                <ShieldCheck className="h-4 w-4" />
                Tài khoản & Bảo mật
              </button>
            </div>
          </div>

          {/* WORKSPACE Section */}
          <div>
            <p className="px-3 text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              Không gian làm việc
            </p>

            {/* Workspace Info Card in Sidebar */}
            <div className="mx-1 mt-2 mb-3 rounded-xl border border-slate-200/80 bg-slate-50/80 p-3 dark:border-white/10 dark:bg-white/5">
              <p className="truncate text-xs font-bold text-slate-900 dark:text-white">
                {workspaceName}
              </p>
              <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                <User className="h-3 w-3" />
                <span>{userRole}</span>
              </div>
            </div>

            {/* Sub-nav items */}
            <div className="space-y-1">
              <button
                type="button"
                onClick={() => setActiveTab("tables")}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-semibold transition-all",
                  activeTab === "tables"
                    ? "bg-blue-50/80 text-blue-700 shadow-xs dark:bg-blue-950/40 dark:text-blue-300"
                    : "text-slate-600 hover:bg-slate-100/70 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white"
                )}
              >
                <Table2 className="h-4 w-4" />
                Bảng & Phân trang
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("appearance")}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-semibold transition-all",
                  activeTab === "appearance"
                    ? "bg-blue-50/80 text-blue-700 shadow-xs dark:bg-blue-950/40 dark:text-blue-300"
                    : "text-slate-600 hover:bg-slate-100/70 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white"
                )}
              >
                <Palette className="h-4 w-4" />
                Giao diện & Theme
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("notifications")}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-semibold transition-all",
                  activeTab === "notifications"
                    ? "bg-blue-50/80 text-blue-700 shadow-xs dark:bg-blue-950/40 dark:text-blue-300"
                    : "text-slate-600 hover:bg-slate-100/70 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white"
                )}
              >
                <Bell className="h-4 w-4" />
                Thông báo & Hệ thống
              </button>
            </div>
          </div>
        </aside>

        {/* Right Main Content Area */}
        <main className="space-y-6">
          {/* TAB 1: BẢNG & PHÂN TRANG (TABLE PAGE SIZE) */}
          {activeTab === "tables" && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                  Cài đặt hiển thị & Phân trang bảng
                </h1>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Tùy chỉnh chế độ hiển thị thẻ/bảng và số lượng bản ghi hiển thị trên mỗi trang trong toàn hệ thống.
                </p>
              </div>

              {/* Card: Cấu hình chế độ xem danh sách Dataset (Lưới / Bảng) */}
              <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-slate-900/60">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-3.5">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-purple-50 text-purple-600 dark:bg-purple-950/50 dark:text-purple-400">
                      <LayoutGrid className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                        Chế độ hiển thị danh sách bộ dữ liệu mặc định
                      </h3>
                      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400 max-w-xl leading-relaxed">
                        Lựa chọn hiển thị danh sách tập dữ liệu theo dạng Lưới thẻ trực quan (Roboflow AI Models) hoặc dạng Bảng dữ liệu chi tiết. Nút chuyển đổi nhanh cũng được đặt ở phía phải bộ lọc của mỗi trang.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center rounded-2xl border border-slate-200 bg-slate-100/80 p-1 dark:border-white/10 dark:bg-slate-900 shrink-0">
                    <button
                      type="button"
                      onClick={() => updateSettings({ datasetViewMode: "grid" })}
                      className={cn(
                        "flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-bold transition",
                        (settings.datasetViewMode || "table") === "grid"
                          ? "bg-white text-purple-600 shadow-xs dark:bg-slate-800 dark:text-white"
                          : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                      )}
                    >
                      <LayoutGrid className="h-4 w-4" />
                      <span>Dạng lưới (Thẻ)</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => updateSettings({ datasetViewMode: "table" })}
                      className={cn(
                        "flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-bold transition",
                        (settings.datasetViewMode || "table") === "table"
                          ? "bg-white text-purple-600 shadow-xs dark:bg-slate-800 dark:text-white"
                          : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                      )}
                    >
                      <Table2 className="h-4 w-4" />
                      <span>Dạng bảng</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Main Card: Cấu hình số lượng bản ghi hiển thị (Thiết kế phong cách thẻ như ảnh mẫu) */}
              <div className="rounded-2xl border border-blue-500/40 bg-white p-6 shadow-sm dark:border-blue-500/30 dark:bg-slate-900/60">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex items-start gap-3.5">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400">
                      <Table2 className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                        Số lượng bản ghi / model hiển thị mỗi trang (Page Size)
                      </h3>
                      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400 max-w-xl leading-relaxed">
                        Quyết định số lượng mục hiển thị trong bảng Lịch sử huấn luyện, Dự án AutoML và các danh sách dữ liệu.
                      </p>
                    </div>
                  </div>

                  <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-black text-blue-700 dark:bg-blue-950 dark:text-blue-300 w-fit">
                    Hiện tại: {isLoaded ? settings.tablePageSize : 10} / trang
                  </span>
                </div>

                {/* Các ô chọn số lượng nhanh (Tương tự thẻ credits trong ảnh mẫu) */}
                <div className="mt-6">
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-3">
                    Chọn nhanh số lượng hiển thị:
                  </p>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                    {PAGE_SIZE_OPTIONS.map((size) => {
                      const isSelected = settings.tablePageSize === size;
                      return (
                        <button
                          key={size}
                          type="button"
                          onClick={() => handlePageSizeSelect(size)}
                          className={cn(
                            "flex flex-col items-center justify-center rounded-xl border p-4 text-center transition-all",
                            isSelected
                              ? "border-blue-600 bg-blue-50/50 shadow-sm ring-2 ring-blue-600/20 dark:border-blue-500 dark:bg-blue-950/30"
                              : "border-slate-200 bg-slate-50/60 hover:border-slate-300 hover:bg-white dark:border-white/10 dark:bg-white/5 dark:hover:border-white/20"
                          )}
                        >
                          <span
                            className={cn(
                              "text-xl font-black",
                              isSelected
                                ? "text-blue-600 dark:text-blue-400"
                                : "text-slate-800 dark:text-slate-200"
                            )}
                          >
                            {size}
                          </span>
                          <span className="mt-1 text-[11px] font-medium text-slate-500 dark:text-slate-400">
                            mục / trang
                          </span>
                          {size === 10 && (
                            <span className="mt-1.5 rounded-full bg-emerald-100 px-2 py-0.5 text-[9px] font-bold text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                              Khuyên dùng
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Nhập số lượng tùy chỉnh */}
                <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center">
                  <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                    Hoặc nhập số tùy chọn (1 - 100):
                  </span>
                  <div className="flex items-center gap-2 max-w-xs">
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      placeholder="VD: 8, 25..."
                      value={customPageSize}
                      onChange={(e) => setCustomPageSize(e.target.value)}
                      className="h-9 rounded-xl border-slate-200 dark:border-white/10 text-xs"
                    />
                    <Button
                      size="sm"
                      onClick={handleApplyCustomPageSize}
                      disabled={!customPageSize}
                      className="h-9 rounded-xl bg-blue-600 px-3 text-xs font-bold text-white hover:bg-blue-500 shrink-0"
                    >
                      Áp dụng
                    </Button>
                  </div>
                </div>

                {/* Hộp giải thích cơ chế phân trang (Tương tự alert box trong ảnh mẫu) */}
                <div className="mt-6 flex items-start gap-3 rounded-xl border border-blue-200/70 bg-blue-50/60 p-4 text-xs text-blue-900 dark:border-blue-900/40 dark:bg-blue-950/20 dark:text-blue-200">
                  <Info className="h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400 mt-0.5" />
                  <div className="leading-relaxed">
                    <p className="font-bold">Cơ chế đồng bộ cục bộ & API:</p>
                    <p className="mt-1 text-slate-700 dark:text-slate-300">
                      • Toàn bộ cấu hình được lưu gọn trong biến duy nhất{" "}
                      <code className="rounded bg-blue-100 px-1 py-0.5 font-mono text-[11px] text-blue-800 dark:bg-blue-900/40 dark:text-blue-300">
                        hautoml_app_settings
                      </code>{" "}
                      để tránh trùng lặp với các hệ thống khác chạy chung origin.
                    </p>
                    <p className="mt-0.5 text-slate-700 dark:text-slate-300">
                      • Với các bảng có API phân trang (hỗ trợ <code className="font-mono">limit</code> hoặc{" "}
                      <code className="font-mono">page</code>), hệ thống tự động truyền giá trị này vào API.
                    </p>
                    <p className="mt-0.5 text-slate-700 dark:text-slate-300">
                      • Nếu API không hỗ trợ phân trang, frontend sẽ tự động cắt mảng dữ liệu (slice) theo đúng
                      số lượng đã thiết lập.
                    </p>
                  </div>
                </div>

                {/* Khối xem trước trực quan (Live Preview) */}
                <div className="mt-6 border-t border-slate-100 pt-5 dark:border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Mô phỏng hiển thị trên các bảng (Live Preview):
                    </p>
                    <span className="text-[11px] text-slate-400">
                      Hiển thị 1 - {Math.min(settings.tablePageSize, 100)} / 100 model (Tổng{" "}
                      {Math.max(1, Math.ceil(100 / settings.tablePageSize))} trang)
                    </span>
                  </div>

                  <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3 dark:border-white/10 dark:bg-white/5">
                    <div className="flex items-center justify-between py-1 text-[11px] font-bold text-slate-400 border-b border-slate-200/60 dark:border-white/5">
                      <span># MÔ HÌNH (MODEL)</span>
                      <span>THUẬT TOÁN</span>
                      <span>ĐIỂM SỐ (ACCURACY)</span>
                    </div>
                    {Array.from({
                      length: Math.min(Math.min(settings.tablePageSize, 5), 5),
                    }).map((_, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between py-1.5 text-xs text-slate-600 dark:text-slate-300 border-b border-slate-100 last:border-0 dark:border-white/5"
                      >
                        <span className="font-medium">Model_{idx + 1}</span>
                        <span className="text-slate-500">
                          {idx % 2 === 0 ? "XGBoost Classifier" : "Random Forest"}
                        </span>
                        <span className="font-bold text-emerald-600 dark:text-emerald-400">
                          {(0.95 - idx * 0.01).toFixed(3)}
                        </span>
                      </div>
                    ))}
                    {settings.tablePageSize > 5 && (
                      <p className="pt-2 text-center text-[10px] text-slate-400 italic">
                        ... và {settings.tablePageSize - 5} model khác trên trang này.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: GIAO DIỆN & THEME */}
          {activeTab === "appearance" && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                  Giao diện & Chủ đề
                </h1>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Tùy chỉnh chủ đề sáng, tối và hiển thị màu sắc theo sở thích của bạn.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-slate-900/60">
                <div className="grid gap-4 md:grid-cols-3">
                  {themeOptions.map((option) => {
                    const Icon = option.icon;
                    const active = currentTheme === option.value;

                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setTheme(option.value)}
                        className={cn(
                          "rounded-2xl border p-5 text-left transition-all",
                          active
                            ? "border-blue-600 bg-blue-50/60 shadow-xs ring-2 ring-blue-600/20 dark:border-blue-500 dark:bg-blue-950/30"
                            : "border-slate-200 bg-slate-50/60 hover:border-slate-300 hover:bg-white dark:border-white/10 dark:bg-white/5 dark:hover:border-white/20"
                        )}
                      >
                        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-blue-600 shadow-xs dark:bg-white/10 dark:text-blue-400">
                          <Icon className="h-5 w-5" />
                        </div>
                        <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">
                          {option.label}
                        </h3>
                        <p className="mt-1 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                          {option.description}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: THÔNG BÁO & HỆ THỐNG */}
          {activeTab === "notifications" && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                  Tùy chọn hệ thống & Thông báo
                </h1>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Quản lý cách hệ thống gửi thông báo và tự động hóa thao tác trong workspace.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-slate-900/60 space-y-4">
                {/* 1. Thông báo huấn luyện */}
                <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-white/10 dark:bg-white/5">
                  <div className="flex items-center gap-3.5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
                      <Bell className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-900 dark:text-white">
                        Thông báo huấn luyện thời gian thực (MQTT WebSocket)
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Nhận thông báo đẩy tức thời khi mô hình học máy huấn luyện thành công hoặc gặp sự cố.
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={settings.trainingNotifications}
                    onCheckedChange={(checked) =>
                      updateSettings({ trainingNotifications: checked })
                    }
                  />
                </div>

                {/* 2. Lưu nháp dataset */}
                <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-white/10 dark:bg-white/5">
                  <div className="flex items-center gap-3.5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400">
                      <Database className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-900 dark:text-white">
                        Tự động lưu nháp cấu hình Dataset
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Ghi nhớ thiết lập tiền xử lý và đặc trưng khi tạo tác vụ huấn luyện mới.
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={settings.datasetDraft}
                    onCheckedChange={(checked) =>
                      updateSettings({ datasetDraft: checked })
                    }
                  />
                </div>

                {/* 3. Xác nhận khi deploy */}
                <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-white/10 dark:bg-white/5">
                  <div className="flex items-center gap-3.5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400">
                      <ShieldCheck className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-900 dark:text-white">
                        Xác nhận khi triển khai mô hình (Deploy Confirmation)
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Hiển thị hộp thoại cảnh báo trước khi xuất bản API phục vụ dự đoán.
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={settings.deployConfirm}
                    onCheckedChange={(checked) =>
                      updateSettings({ deployConfirm: checked })
                    }
                  />
                </div>

                {/* 4. Tính năng thử nghiệm */}
                <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-white/10 dark:bg-white/5">
                  <div className="flex items-center gap-3.5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-purple-50 text-purple-600 dark:bg-purple-950/40 dark:text-purple-400">
                      <Zap className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-900 dark:text-white">
                        Các tính năng thử nghiệm (Experimental Features)
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Trải nghiệm sớm các thuật toán AutoML mới nhất đang trong giai đoạn beta.
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={settings.experimental}
                    onCheckedChange={(checked) =>
                      updateSettings({ experimental: checked })
                    }
                  />
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: TÀI KHOẢN & BẢO MẬT */}
          {activeTab === "account" && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                  Tài khoản & Bảo mật
                </h1>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Xem thông tin tài khoản đăng nhập và quản lý mật khẩu của bạn.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-slate-900/60 space-y-6">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div className="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3.5 dark:border-white/10 dark:bg-white/5">
                    <span className="text-[11px] font-semibold text-slate-400">Tên đăng nhập</span>
                    <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">
                      {session?.user?.username || "Chưa cập nhật"}
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3.5 dark:border-white/10 dark:bg-white/5">
                    <span className="text-[11px] font-semibold text-slate-400">Email</span>
                    <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white truncate">
                      {session?.user?.email || "Chưa cập nhật"}
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3.5 dark:border-white/10 dark:bg-white/5">
                    <span className="text-[11px] font-semibold text-slate-400">Vai trò</span>
                    <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">
                      {userRole}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-5 dark:border-white/10">
                  <Button asChild className="h-9 rounded-xl bg-blue-600 px-4 text-xs font-bold text-white hover:bg-blue-500">
                    <Link href="/change-pw">
                      Đổi mật khẩu
                      <ArrowUpRight className="ml-1 h-3.5 w-3.5" />
                    </Link>
                  </Button>

                  <Button asChild variant="outline" className="h-9 rounded-xl border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:text-slate-200 dark:hover:bg-white/10">
                    <Link href="/profile">
                      Chỉnh sửa hồ sơ cá nhân
                      <ArrowUpRight className="ml-1 h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Dialog Đổi tên Workspace */}
      <Dialog open={isRenameDialogOpen} onOpenChange={setIsRenameDialogOpen}>
        <DialogContent className="rounded-2xl sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold text-slate-900 dark:text-white">
              Đổi tên không gian làm việc
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-500 dark:text-slate-400">
              Nhập tên mới cho không gian làm việc của bạn. Tên này sẽ hiển thị trên thanh tiêu đề.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-3">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Tên Workspace
            </label>
            <Input
              value={tempWorkspaceName}
              onChange={(e) => setTempWorkspaceName(e.target.value)}
              placeholder="VD: Viets Workspace"
              className="mt-1.5 h-10 rounded-xl border-slate-200 dark:border-white/10 text-sm"
            />
          </div>

          <DialogFooter className="mt-4 flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsRenameDialogOpen(false)}
              className="h-9 rounded-xl border-slate-200 text-xs"
            >
              Hủy
            </Button>
            <Button
              size="sm"
              onClick={handleSaveWorkspaceName}
              className="h-9 rounded-xl bg-blue-600 text-xs font-bold text-white hover:bg-blue-500"
            >
              Lưu thay đổi
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
