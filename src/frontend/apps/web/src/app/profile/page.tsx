"use client";

import React, { useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  AlertDialogTitle,
  AlertDialogContent,
} from "@/shared/components/ui/alert-dialog";
import { Avatar, AvatarFallback, AvatarImage } from "@/shared/components/ui/avatar";
import { Button } from "@/shared/components/ui/button";
import { Label } from "@/shared/components/ui/label";
import {
  Calendar,
  Database,
  Mail,
  Pencil,
  Phone,
  Rocket,
  ShieldCheck,
  SquarePen,
  UserIcon,
} from "lucide-react";
import { z } from "zod";
import { useSession } from "next-auth/react";
import { useToast } from "@/shared/hooks/use-toast";
import {
  UpdateUserPayload,
  useGetUserQuery,
  useUpdateAvatarMutation,
  useUpdateUserMutation,
} from "@/core/api/userApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import AppLoading from "@/shared/components/common/AppLoading";
import { useTranslations } from "next-intl";

type EditUser = UpdateUserPayload;

type FormErrors = {
  fullName?: string;
  email?: string;
  date?: string;
  gender?: string;
  number?: string;
};

const accountStats = [
  { labelKey: "stats.datasets", value: "12", icon: Database },
  { labelKey: "stats.runs", value: "34", icon: ShieldCheck },
  { labelKey: "stats.deployments", value: "4", icon: Rocket },
];

const recentActivities = [
  ["activities.uploaded", "activities.twoMinutesAgo", "bg-emerald-50 ring-1 ring-emerald-200 text-emerald-600 dark:bg-emerald-500/10 dark:ring-emerald-500/20"],
  ["activities.training", "activities.twelveMinutesAgo", "bg-amber-50 ring-1 ring-amber-200 text-amber-600 dark:bg-amber-500/10 dark:ring-amber-500/20"],
  ["activities.deployed", "activities.oneHourAgo", "bg-blue-50 ring-1 ring-blue-200 text-blue-600 dark:bg-blue-500/10 dark:ring-blue-500/20"],
  ["activities.viewedModelStore", "activities.yesterday", "bg-indigo-50 ring-1 ring-indigo-200 text-indigo-600 dark:bg-indigo-500/10 dark:ring-indigo-500/20"],
];

const profileTabs = ["tabs.profile", "tabs.security", "tabs.apiKey", "tabs.preferences"];

const inputClass =
  "mt-2 h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm font-bold text-automl-ink outline-none transition focus:border-automl-blue focus:ring-4 focus:ring-automl-blue/10 dark:border-white/10 dark:bg-white/10 dark:text-white";

const getAvatarSrc = (avatar?: string | null) => {
  if (!avatar) return "";

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

const Profile = () => {
  const t = useTranslations("Profile");
  const { data: session, status } = useSession();
  const username = session?.user?.username;
  const {
    data: user,
    isLoading,
    refetch,
  } = useGetUserQuery(username ?? "", {
    skip: !username,
  });
  const [updateUser] = useUpdateUserMutation();
  const [updateAvatar] = useUpdateAvatarMutation();
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editFormData, setEditFormData] = useState<EditUser | null>(null);
  const [isAlertDialogOpen, setIsAlertDialogOpen] = useState<boolean>(false);
  const [file, setFile] = useState<File | null>(null);
  const [originalAvatar, setOriginalAvatar] = useState<string | null>(null);
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const { toast } = useToast();
  const formSchema = useMemo(
    () =>
      z.object({
        fullName: z.string().min(5, t("validation.fullNameMin")),
        email: z.string().email(t("validation.email")),
        date: z
          .string()
          .refine((val) => !isNaN(Date.parse(val)), t("validation.date")),
        gender: z.enum(["male", "female"], {
          errorMap: () => ({ message: t("validation.gender") }),
        }),
        number: z.string().regex(/^0(3|5|7|8|9)[0-9]{8}$/, {
          message: t("validation.phone"),
        }),
      }),
    [t],
  );

  useEffect(() => {
    if (!user) return;

    setEditFormData({
      email: user.email,
      gender: user.gender,
      date: user.date,
      fullName: user.fullName,
      number: user.number,
    });

    const avatar = getAvatarSrc(user.avatar ?? user.image);
    setAvatarUrl(avatar);
    setOriginalAvatar(avatar);
  }, [user]);

  const handleAvatarChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) return;

    const allowedTypes = ["image/jpeg", "image/png"];

    if (!allowedTypes.includes(selectedFile.type)) {
      toast({
        title: t("toast.invalidImage"),
        description: t("toast.invalidImageDescription"),
        variant: "destructive",
        duration: 3000,
      });
      return;
    }

    if (selectedFile && isEditing) {
      setFile(selectedFile);
      setAvatarUrl(URL.createObjectURL(selectedFile));
    }
  };

  useEffect(() => {
    if (!isEditing) {
      setFile(null);
      setAvatarUrl(originalAvatar);
    }
  }, [isEditing, originalAvatar]);

  const handleConfirmUpdate = async () => {
    if (!editFormData || !session?.user?.username) return;

    try {
      const username = session.user.username;

      if (file) {
        await updateAvatar({ username, avatar: file }).unwrap();
        window.dispatchEvent(new Event("avatar-updated"));
      }

      await updateUser({ username, data: editFormData }).unwrap();

      toast({
        title: t("toast.updateSuccess"),
        description: t("toast.updateSuccessDescription"),
        className:
          "bg-green-50 border border-green-300 text-green-700 [&>div>h3]:text-lg [&>div>h3]:font-semibold",
        duration: 3000,
      });

      await refetch();
      setIsEditing(false);
      setIsAlertDialogOpen(false);
    } catch (error) {
      console.error("Profile update error:", error);
      toast({
        title: t("toast.updateFailed"),
        description: getApiErrorMessage(error, t("toast.updateFailedDescription")),
        variant: "destructive",
        duration: 3000,
      });
    }
  };

  const handleEditClick = () => {
    if (user) {
      const { email, gender, date, fullName, number } = user;

      const editUserData: EditUser = {
        email,
        gender,
        date,
        fullName,
        number,
      };

      setEditFormData(editUserData);
      setIsEditing(true);
    }
  };

  const handleValidateAndOpenDialog = () => {
    const result = formSchema.safeParse(editFormData);

    if (!result.success) {
      const formattedErrors = result.error.format();
      setFormErrors({
        fullName: formattedErrors.fullName?._errors[0],
        email: formattedErrors.email?._errors[0],
        date: formattedErrors.date?._errors[0],
        gender: formattedErrors.gender?._errors[0],
        number: formattedErrors.number?._errors[0],
      });
      setIsAlertDialogOpen(false);
      return;
    }

    setFormErrors({});
    setIsAlertDialogOpen(true);
  };

  if (status === "loading" || isLoading) {
    return <AppLoading label={t("loading")} />;
  }

  const initials = (user?.username || username || "HA").slice(0, 2).toUpperCase();
  const displayName = user?.fullName || user?.username || t("fallbackUser");
  const roleLabel =
    session?.user?.role === "admin" ? t("roles.admin") : t("roles.user");

  return (
    <div className="space-y-7">
      <section className="grid gap-7 xl:grid-cols-[0.8fr_1.7fr]">
        <aside className="rounded-[2rem] border border-slate-200 bg-white p-7 shadow-sm dark:border-white/10 dark:bg-white/10">
          <div className="relative h-32 w-32 overflow-hidden rounded-[2rem] bg-automl-blue-soft">
            <Avatar className="h-full w-full rounded-[2rem]">
              <AvatarImage
                key={avatarUrl}
                src={avatarUrl || ""}
                alt="avatar"
                className="object-cover"
              />
              <AvatarFallback className="rounded-[2rem] bg-automl-blue-soft text-4xl font-black text-automl-blue">
                {initials}
              </AvatarFallback>
            </Avatar>

            {isEditing && (
              <label className="absolute bottom-3 right-3 flex h-10 w-10 cursor-pointer items-center justify-center rounded-2xl bg-white text-automl-blue shadow-md">
                <input
                  type="file"
                  accept="image/png, image/jpeg"
                  onChange={handleAvatarChange}
                  className="hidden"
                />
                <SquarePen className="h-5 w-5" />
              </label>
            )}
          </div>

          <h2 className="mt-6 text-3xl font-black tracking-tight text-automl-ink dark:text-white">
            {displayName}
          </h2>
          <p className="mt-3 text-base font-bold text-automl-muted dark:text-white/60">
            @{user?.username || username} · {roleLabel}
          </p>
          <span className="mt-4 inline-flex rounded-full bg-automl-cyan-soft px-4 py-2 text-sm font-black text-cyan-700">
            {t("openedFromMenu")}
          </span>

          <div className="mt-7 grid grid-cols-3 gap-3">
            {accountStats.map((stat) => {
              const Icon = stat.icon;
              return (
                <div
                  key={stat.labelKey}
                  className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-center dark:border-white/10 dark:bg-white/5"
                >
                  <Icon className="mx-auto mb-2 h-4 w-4 text-automl-blue" />
                  <p className="text-2xl font-black text-automl-ink dark:text-white">
                    {stat.value}
                  </p>
                  <p className="text-xs font-bold text-automl-muted dark:text-white/55">
                    {t(stat.labelKey)}
                  </p>
                </div>
              );
            })}
          </div>

          {!isEditing && (
            <Button
              onClick={handleEditClick}
              className="mt-6 h-12 rounded-2xl bg-gradient-to-r from-automl-blue to-cyan-500 px-8 font-black text-white shadow-none hover:opacity-95"
            >
              <Pencil className="h-4 w-4" />
              {t("editProfile")}
            </Button>
          )}
        </aside>

        <main className="space-y-6">
          <div>
            <h1 className="text-4xl font-black tracking-tight text-automl-ink dark:text-white">
              {t("title")}
            </h1>
            <p className="mt-2 text-sm font-medium text-automl-muted dark:text-white/60">
              {t("subtitle")}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            {profileTabs.map((tab, index) => (
              <button
                key={tab}
                type="button"
                className={
                  index === 0
                    ? "h-12 rounded-2xl bg-gradient-to-r from-automl-blue to-cyan-500 px-8 text-sm font-black text-white shadow-sm"
                    : "h-12 rounded-2xl bg-automl-blue-soft px-8 text-sm font-black text-automl-blue transition hover:bg-automl-blue-soft/80"
                }
              >
                {t(tab)}
              </button>
            ))}
          </div>

          <section className="grid gap-6 xl:grid-cols-2">
            <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/10">
              {isEditing && editFormData ? (
                <EditForm
                  editFormData={editFormData}
                  setEditFormData={setEditFormData}
                  formErrors={formErrors}
                  setIsEditing={setIsEditing}
                  isAlertDialogOpen={isAlertDialogOpen}
                  setIsAlertDialogOpen={setIsAlertDialogOpen}
                  handleValidateAndOpenDialog={handleValidateAndOpenDialog}
                  handleConfirmUpdate={handleConfirmUpdate}
                />
              ) : (
                <div className="space-y-4">
                  <InfoRow icon={UserIcon} label={t("fields.username")} value={user?.username || ""} code="TK" />
                  <InfoRow icon={Mail} label={t("fields.email")} value={user?.email || ""} code="EM" />
                  <InfoRow icon={Phone} label={t("fields.phone")} value={user?.number || t("notUpdated")} code="SD" />
                  <InfoRow icon={Calendar} label={t("fields.birthDate")} value={user?.date || t("notUpdated")} code="NS" />
                </div>
              )}
            </div>

            <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/10">
              <h3 className="text-xl font-black text-automl-ink dark:text-white">
                {t("recentActivity")}
              </h3>
              <div className="mt-6 space-y-5">
                {recentActivities.map(([titleKey, timeKey, tone]) => (
                  <div key={titleKey} className="flex gap-4">
                    <span className={`mt-1 h-5 w-5 rounded-lg ${tone}`} />
                    <div>
                      <p className="font-black text-automl-ink dark:text-white">
                        {t(titleKey)}
                      </p>
                      <p className="text-sm font-medium text-automl-muted dark:text-white/55">
                        {t(timeKey)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </main>
      </section>
    </div>
  );
};

const InfoRow = ({
  icon: Icon,
  label,
  value,
  code,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  code: string;
}) => (
  <div className="flex items-center gap-4 rounded-3xl border border-slate-200 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/5">
    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-automl-blue-soft text-xs font-black text-automl-blue">
      {code}
    </div>
    <Icon className="hidden h-4 w-4 text-automl-blue sm:block" />
    <div className="min-w-0">
      <Label className="text-sm font-bold text-automl-muted dark:text-white/55">
        {label}
      </Label>
      <p className="truncate text-base font-black text-automl-ink dark:text-white">
        {value}
      </p>
    </div>
  </div>
);

const EditForm = ({
  editFormData,
  setEditFormData,
  formErrors,
  setIsEditing,
  isAlertDialogOpen,
  setIsAlertDialogOpen,
  handleValidateAndOpenDialog,
  handleConfirmUpdate,
}: {
  editFormData: EditUser;
  setEditFormData: React.Dispatch<React.SetStateAction<EditUser | null>>;
  formErrors: FormErrors;
  setIsEditing: React.Dispatch<React.SetStateAction<boolean>>;
  isAlertDialogOpen: boolean;
  setIsAlertDialogOpen: React.Dispatch<React.SetStateAction<boolean>>;
  handleValidateAndOpenDialog: () => void;
  handleConfirmUpdate: () => Promise<void>;
}) => (
  <EditFormContent
    editFormData={editFormData}
    setEditFormData={setEditFormData}
    formErrors={formErrors}
    setIsEditing={setIsEditing}
    isAlertDialogOpen={isAlertDialogOpen}
    setIsAlertDialogOpen={setIsAlertDialogOpen}
    handleValidateAndOpenDialog={handleValidateAndOpenDialog}
    handleConfirmUpdate={handleConfirmUpdate}
  />
);

const EditFormContent = ({
  editFormData,
  setEditFormData,
  formErrors,
  setIsEditing,
  isAlertDialogOpen,
  setIsAlertDialogOpen,
  handleValidateAndOpenDialog,
  handleConfirmUpdate,
}: {
  editFormData: EditUser;
  setEditFormData: React.Dispatch<React.SetStateAction<EditUser | null>>;
  formErrors: FormErrors;
  setIsEditing: React.Dispatch<React.SetStateAction<boolean>>;
  isAlertDialogOpen: boolean;
  setIsAlertDialogOpen: React.Dispatch<React.SetStateAction<boolean>>;
  handleValidateAndOpenDialog: () => void;
  handleConfirmUpdate: () => Promise<void>;
}) => {
  const t = useTranslations("Profile");
  const common = useTranslations("Common");

  return (
  <div className="space-y-5">
    <div className="grid gap-4 md:grid-cols-2">
      <EditField
        label={t("fields.fullName")}
        value={editFormData.fullName}
        error={formErrors.fullName}
        onChange={(value) =>
          setEditFormData({ ...editFormData, fullName: value })
        }
      />
      <EditField
        label={t("fields.email")}
        type="email"
        value={editFormData.email}
        error={formErrors.email}
        onChange={(value) => setEditFormData({ ...editFormData, email: value })}
      />
      <EditField
        label={t("fields.birthDate")}
        type="date"
        value={editFormData.date}
        error={formErrors.date}
        onChange={(value) => setEditFormData({ ...editFormData, date: value })}
      />
      <div>
        <Label className="font-bold text-automl-ink dark:text-white">{t("fields.gender")}</Label>
        <select
          value={editFormData.gender}
          onChange={(e) =>
            setEditFormData({ ...editFormData, gender: e.target.value })
          }
          className={inputClass}
        >
          <option value="male">{t("gender.male")}</option>
          <option value="female">{t("gender.female")}</option>
        </select>
        {formErrors.gender && (
          <p className="mt-2 text-sm font-semibold text-red-500">
            {formErrors.gender}
          </p>
        )}
      </div>
      <div className="md:col-span-2">
        <EditField
          label={t("fields.phone")}
          value={editFormData.number}
          error={formErrors.number}
          onChange={(value) =>
            setEditFormData({ ...editFormData, number: value })
          }
        />
      </div>
    </div>

    <div className="flex justify-end gap-3">
      <Button
        variant="outline"
        onClick={() => setIsEditing(false)}
        className="rounded-2xl"
      >
        {common("cancel")}
      </Button>

      <AlertDialog open={isAlertDialogOpen} onOpenChange={setIsAlertDialogOpen}>
        <Button
          onClick={handleValidateAndOpenDialog}
          className="rounded-2xl bg-automl-blue text-white hover:bg-automl-blue-hover"
        >
          {t("saveChanges")}
        </Button>

        <AlertDialogOverlay className="fixed inset-0 z-40 bg-black/60" />
        <AlertDialogContent className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-3xl bg-white p-6 shadow-xl dark:bg-automl-navy">
          <AlertDialogHeader className="space-y-2 text-center">
            <AlertDialogTitle className="text-xl font-black text-automl-ink dark:text-white">
              {t("confirm.title")}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-automl-muted dark:text-white/60">
              {t("confirm.description")}
            </AlertDialogDescription>
          </AlertDialogHeader>

          <AlertDialogFooter className="mt-6 flex w-full justify-center gap-3">
            <AlertDialogCancel className="rounded-2xl px-5">
              {common("cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmUpdate}
              className="rounded-2xl bg-automl-blue px-5 text-white hover:bg-automl-blue-hover"
            >
              {common("confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  </div>
  );
};

const EditField = ({
  label,
  value,
  onChange,
  error,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type?: string;
}) => (
  <div>
    <Label className="font-bold text-automl-ink dark:text-white">{label}</Label>
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={inputClass}
    />
    {error && <p className="mt-2 text-sm font-semibold text-red-500">{error}</p>}
  </div>
);

export default Profile;
