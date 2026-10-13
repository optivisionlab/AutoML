"use client";

import { useState, useEffect, useCallback } from "react";

export interface HAutoMLAppSettings {
  tablePageSize: number;
  workspaceName: string;
  trainingNotifications: boolean;
  datasetDraft: boolean;
  deployConfirm: boolean;
  experimental: boolean;
  datasetViewMode: "table" | "grid";
}

export const HAUTOML_SETTINGS_KEY = "hautoml_app_settings";

export const DEFAULT_APP_SETTINGS: HAutoMLAppSettings = {
  tablePageSize: 10,
  workspaceName: "HAutoML Workspace",
  trainingNotifications: true,
  datasetDraft: true,
  deployConfirm: true,
  experimental: false,
  datasetViewMode: "table",
};

/**
 * Đọc cài đặt an toàn từ localStorage (chỉ gói trong một object duy nhất)
 */
export const getStoredAppSettings = (): HAutoMLAppSettings => {
  if (typeof window === "undefined") {
    return DEFAULT_APP_SETTINGS;
  }

  try {
    const raw = localStorage.getItem(HAUTOML_SETTINGS_KEY);
    if (!raw) return DEFAULT_APP_SETTINGS;
    const parsed = JSON.parse(raw);
    return {
      ...DEFAULT_APP_SETTINGS,
      ...parsed,
    };
  } catch (err) {
    console.warn("[AppSettings] Không thể đọc cấu hình từ localStorage:", err);
    return DEFAULT_APP_SETTINGS;
  }
};

/**
 * Lưu toàn bộ cài đặt vào một biến duy nhất trong localStorage
 */
export const saveStoredAppSettings = (settings: HAutoMLAppSettings): void => {
  if (typeof window === "undefined") return;

  try {
    localStorage.setItem(HAUTOML_SETTINGS_KEY, JSON.stringify(settings));
    window.dispatchEvent(
      new CustomEvent("hautoml_settings_updated", { detail: settings })
    );
  } catch (err) {
    console.error("[AppSettings] Không thể ghi cấu hình vào localStorage:", err);
  }
};

export function useAppSettings() {
  const [settings, setSettingsState] = useState<HAutoMLAppSettings>(DEFAULT_APP_SETTINGS);
  const [isLoaded, setIsLoaded] = useState<boolean>(false);

  useEffect(() => {
    // Đọc cài đặt khi mount trên client
    const current = getStoredAppSettings();
    setSettingsState(current);
    setIsLoaded(true);

    const handleSettingsUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<HAutoMLAppSettings>;
      if (customEvent.detail) {
        setSettingsState(customEvent.detail);
      } else {
        setSettingsState(getStoredAppSettings());
      }
    };

    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === HAUTOML_SETTINGS_KEY && event.newValue) {
        try {
          const updated = JSON.parse(event.newValue);
          setSettingsState({ ...DEFAULT_APP_SETTINGS, ...updated });
        } catch {
          // ignore
        }
      }
    };

    window.addEventListener("hautoml_settings_updated", handleSettingsUpdate);
    window.addEventListener("storage", handleStorageChange);

    return () => {
      window.removeEventListener("hautoml_settings_updated", handleSettingsUpdate);
      window.removeEventListener("storage", handleStorageChange);
    };
  }, []);

  const updateSettings = useCallback((partial: Partial<HAutoMLAppSettings>) => {
    setSettingsState((prev) => {
      const updated = { ...prev, ...partial };
      saveStoredAppSettings(updated);
      return updated;
    });
  }, []);

  return {
    settings,
    updateSettings,
    isLoaded,
  };
}
