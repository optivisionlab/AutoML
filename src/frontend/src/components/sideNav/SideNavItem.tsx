import Link from "next/link";
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export const SideNavItem = ({
  label,
  icon,
  path,
  active,
  collapsed = false,
  onNavigate,
}: {
  label: string;
  icon: ReactNode;
  path: string;
  active: boolean;
  collapsed?: boolean;
  onNavigate?: () => void;
}) => {
  return (
    <Link
      href={path}
      onClick={onNavigate}
      title={collapsed ? label : undefined}
      className={cn(
        "group flex items-center rounded-2xl text-sm font-bold transition",
        collapsed ? "justify-center px-2 py-3" : "gap-3 px-4 py-3",
        active
          ? "bg-automl-blue-soft text-automl-blue shadow-sm"
          : "text-slate-500 hover:bg-slate-100 hover:text-automl-ink dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white",
      )}
    >
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border transition",
          active
            ? "border-automl-blue/20 bg-white text-automl-blue"
            : "border-slate-200 bg-white text-slate-400 group-hover:text-automl-blue dark:border-white/10 dark:bg-white/10",
        )}
      >
        {icon}
      </span>
      {!collapsed && <span className="truncate">{label}</span>}
    </Link>
  );
};
