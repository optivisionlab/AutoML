"use client";

import { MoreVertical } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { cn } from "@/shared/lib/utils";
import { useTranslations } from "next-intl";

export type RowActionItem = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  destructive?: boolean;
};

type RowActionMenuProps = {
  items: RowActionItem[];
  label?: string;
  align?: "start" | "center" | "end";
};

export default function RowActionMenu({
  items,
  label,
  align = "end",
}: RowActionMenuProps) {
  const t = useTranslations("Common");
  const menuLabel = label ?? t("openActionMenu");

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="h-9 w-9 rounded-xl border-[var(--automl-data-card-border)] bg-[var(--automl-table-row-bg)] text-[var(--automl-data-muted)] shadow-none hover:bg-[var(--automl-table-row-hover)] hover:text-[var(--automl-data-text)]"
          aria-label={menuLabel}
        >
          <MoreVertical className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={align}
        className="w-48 rounded-2xl border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-2 text-[var(--automl-data-text)] shadow-xl"
      >
        {items.map((item) => (
          <DropdownMenuItem
            key={item.label}
            disabled={item.disabled}
            onClick={item.onClick}
            className={cn(
              "cursor-pointer rounded-xl px-3 py-2 text-sm font-bold focus:bg-[var(--automl-table-row-hover)]",
              item.destructive && "text-red-600 focus:text-red-600",
            )}
          >
            {item.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
