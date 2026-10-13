"use client";

import { type ReactNode, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useLanguage } from "@/core/i18n/LanguageProvider";
import {
  ArrowLeft,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronRight,
  Database,
  FileSpreadsheet,
  Gauge,
  Layers3,
  Lightbulb,
  PanelRightClose,
  PanelRightOpen,
  Rocket,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  Wand2,
  type LucideIcon,
} from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/components/ui/alert-dialog";
import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/shared/components/ui/radio-group";
import { Switch } from "@/shared/components/ui/switch";
import { useGetFeaturesQuery, useGetMetricsQuery } from "@/core/api/automlApi";
import { cn } from "@/shared/lib/utils";
import toTitleLabel from "@/shared/utils/toTitleLable";

type TrainingWizardProps = {
  datasetID?: string;
  datasetName: string;
  backHref: string;
  resultHref: string;
  initialChoose?: string;
  featureErrorMessage?: string;
};

type ChoiceCardProps = {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  selected: boolean;
  disabled?: boolean;
  badge?: string;
  tone: string;
  children?: ReactNode;
};

type SummaryConfig = {
  icon: LucideIcon;
  title: string;
  value: string;
  detail: string;
};

type StepDef = {
  id: number;
  labelKey: "data" | "mode" | "problem" | "parameters" | "confirm";
  icon: LucideIcon;
};

const steps: StepDef[] = [
  { id: 1, labelKey: "data", icon: Database },
  { id: 2, labelKey: "mode", icon: Wand2 },
  { id: 3, labelKey: "problem", icon: Target },
  { id: 4, labelKey: "parameters", icon: SlidersHorizontal },
  { id: 5, labelKey: "confirm", icon: CheckCircle2 },
];


const setStorage = (key: string, value: string) => {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(key, value);
};

export default function TrainingWizard({
  datasetID,
  datasetName,
  backHref,
  resultHref,
  initialChoose = "",
  featureErrorMessage = "Không thể tải dữ liệu huấn luyện.",
}: TrainingWizardProps) {
  const router = useRouter();
  const t = useTranslations("TrainingWizard");
  const { locale } = useLanguage();
  const isEn = locale === "en";

  const modeOptions = [
    {
      value: "new_model",
      title: t("modeOptions.newModel.title"),
      description: t("modeOptions.newModel.description"),
      icon: BrainCircuit,
      badge: t("modeOptions.newModel.badge"),
      tone: "bg-blue-50 text-blue-600",
    },
    {
      value: "new_version",
      title: t("modeOptions.newVersion.title"),
      description: t("modeOptions.newVersion.description"),
      icon: Layers3,
      badge: t("modeOptions.newVersion.badge"),
      tone: "bg-slate-100 text-slate-500",
      disabled: true,
    },
  ];

  const strategyOptions = [
    {
      value: "auto",
      title: t("strategyOptions.auto.title"),
      description: t("strategyOptions.auto.description"),
      icon: Sparkles,
      badge: t("strategyOptions.auto.badge"),
      tone: "bg-violet-50 text-violet-600",
    },
    {
      value: "custom",
      title: t("strategyOptions.custom.title"),
      description: t("strategyOptions.custom.description"),
      icon: Settings2,
      badge: t("strategyOptions.custom.badge"),
      tone: "bg-slate-100 text-slate-500",
      disabled: true,
    },
  ];

  const problemOptions = [
    {
      value: "classification",
      title: t("problemOptions.classification.title"),
      description: t("problemOptions.classification.description"),
      icon: Target,
      badge: t("problemOptions.classification.badge"),
      tone: "bg-emerald-50 text-emerald-600",
    },
    {
      value: "regression",
      title: t("problemOptions.regression.title"),
      description: t("problemOptions.regression.description"),
      icon: Gauge,
      badge: t("problemOptions.regression.badge"),
      tone: "bg-amber-50 text-amber-600",
    },
  ];
  const [step, setStep] = useState(1);
  const [selectedOption, setSelectedOption] = useState(initialChoose);
  const [method, setMethod] = useState("");
  const [problemType, setProblemType] = useState("");
  const [selectedTarget, setSelectedTarget] = useState("");
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [metricSort, setMetricSort] = useState("");
  const [summaryCollapsed, setSummaryCollapsed] = useState(false);

  const shouldFetchTrainingMeta =
    step === 4 && Boolean(datasetID) && Boolean(problemType);
  const {
    data: featuresData,
    isError: isFeaturesError,
    isFetching: isFeaturesFetching,
  } = useGetFeaturesQuery(
    { datasetId: datasetID ?? "", problemType },
    { skip: !shouldFetchTrainingMeta },
  );
  const { data: metricsData, isFetching: isMetricsFetching } =
    useGetMetricsQuery(problemType, {
      skip: !shouldFetchTrainingMeta,
    });

  const listFeature = featuresData?.features ?? {};
  const metrics = metricsData?.metrics ?? {};
  const featureNames = Object.keys(listFeature);
  const selectableFeatures = featureNames.filter((name) => name !== selectedTarget);
  const isAllSelected =
    selectableFeatures.length > 0 &&
    selectableFeatures.every((name) => selectedFeatures.includes(name));
  const canStart =
    Boolean(selectedTarget) && selectedFeatures.length > 0 && Boolean(metricSort);
  const displayedStep = step === 4 && canStart ? 5 : step;
  const summaryItems: SummaryConfig[] = [
    {
      icon: Database,
      title: t("summary.dataset"),
      value: datasetName,
      detail: datasetID ? `ID: ${datasetID}` : "Chưa xác định",
    },
    {
      icon: BrainCircuit,
      title: t("summary.mode"),
      value:
        selectedOption === "new_version"
          ? "Phiên bản mới"
          : selectedOption
            ? "Mô hình mới"
            : "Chưa chọn",
      detail:
        method === "auto"
          ? "AutoML tự động tối ưu"
          : method
            ? "Tùy chỉnh"
            : "Chưa chọn chiến lược",
    },
    {
      icon: Target,
      title: t("summary.problem"),
      value:
        problemType === "classification"
          ? "Phân loại"
          : problemType === "regression"
            ? "Hồi quy"
            : "Chưa chọn",
      detail: selectedTarget ? `${t("summary.target")}: ${selectedTarget}` : "-",
    },
    {
      icon: SlidersHorizontal,
      title: t("summary.params"),
      value: metricSort ? toTitleLabel(metricSort) : "Chưa chọn metric",
      detail: t("summary.featuresCount", { count: selectedFeatures.length }),
    },
    {
      icon: Rocket,
      title: isEn ? "Resources" : "Tài nguyên",
      value: "Auto",
      detail: isEn ? "GPU preferred if available" : "Ưu tiên GPU nếu khả dụng",
    },
  ];

  const stepDescription = useMemo(() => {
    if (step === 1) return t("stepDescriptions.data");
    if (step === 2) return t("stepDescriptions.mode");
    if (step === 3) return t("stepDescriptions.problem");
    return t("stepDescriptions.parameters");
  }, [step, t]);

  const handleBack = () => {
    if (step === 1) {
      router.push(backHref);
      return;
    }

    setStep((value) => value - 1);
  };

  const handleNext = () => {
    if (step === 1 && selectedOption) {
      setStorage("choose", selectedOption);
      setStep(2);
      return;
    }

    if (step === 2 && method) {
      setStorage("method", method);
      setStep(3);
      return;
    }

    if (step === 3 && problemType) {
      setStorage("problem_type", problemType);
      setStep(4);
    }
  };

  const handleTargetChange = (value: string) => {
    setSelectedTarget(value);
    setStorage("target", value);

    const nextFeatures = selectedFeatures.filter((feature) => feature !== value);
    setSelectedFeatures(nextFeatures);
    setStorage("list_feature", JSON.stringify(nextFeatures));
  };

  const handleFeatureToggle = (feature: string, checked: boolean) => {
    const nextFeatures = checked
      ? [...selectedFeatures, feature]
      : selectedFeatures.filter((item) => item !== feature);

    setSelectedFeatures(nextFeatures);
    setStorage("list_feature", JSON.stringify(nextFeatures));
  };

  const handleSelectAllFeatures = () => {
    const nextFeatures = isAllSelected ? [] : selectableFeatures;
    setSelectedFeatures(nextFeatures);
    setStorage("list_feature", JSON.stringify(nextFeatures));
  };

  const handleMetricChange = (value: string) => {
    setMetricSort(value);
    setStorage("metric_sort", value);
  };

  const handleStartTraining = () => {
    if (!selectedTarget) return alert("Vui lòng chọn một thuộc tính mục tiêu!");
    if (selectedFeatures.length === 0) {
      return alert("Vui lòng chọn ít nhất một thuộc tính huấn luyện!");
    }
    if (!metricSort) return alert("Vui lòng chọn một chỉ số đánh giá!");

    router.push(resultHref);
  };

  return (
    <div className="h-full overflow-hidden rounded-[2rem] bg-gradient-to-br from-slate-50 via-white to-slate-100/50 p-3 shadow-sm ring-1 ring-slate-200 dark:from-white/5 dark:via-white/5 dark:to-blue-950/20 dark:ring-white/10 lg:p-4">
      <div
        className={cn(
          "grid h-full min-h-0 gap-4 transition-[grid-template-columns] duration-300",
          summaryCollapsed ? "xl:grid-cols-[1fr_88px]" : "xl:grid-cols-[1fr_340px]",
        )}
      >
        <main className="relative flex min-h-0 flex-col overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white/90 p-4 shadow-sm backdrop-blur dark:border-white/10 dark:bg-white/10 lg:p-5">
          <div className="pointer-events-none absolute -left-16 top-16 h-44 w-44 rounded-full bg-blue-100/25 blur-3xl dark:bg-blue-500/10" />
          <div className="pointer-events-none absolute bottom-10 right-10 h-32 w-32 rounded-full bg-cyan-100/20 blur-3xl dark:bg-cyan-500/10" />

          <div className="relative z-10 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="max-w-3xl text-sm font-semibold leading-6 text-automl-muted dark:text-white/60">
                {stepDescription}
              </p>
            </div>
            <Button
              variant="outline"
              className="h-10 rounded-2xl border-slate-200 bg-white px-4 font-bold shadow-none dark:border-white/10 dark:bg-white/10"
              type="button"
            >
              <Lightbulb className="mr-2 h-4 w-4 text-automl-blue" />
              {t("suggestConfig")}
            </Button>
          </div>

          <div className="relative z-10 mt-4 min-h-0 flex-1 overflow-hidden pr-1 pt-16">
            <StepBubbleDeck currentStep={displayedStep} />
            <div
              key={step}
              className="relative z-20 h-full overflow-y-auto rounded-[1.4rem] border border-white/80 bg-white/95 p-3 sm:p-4 shadow-2xl shadow-blue-950/10 ring-1 ring-blue-100/80 backdrop-blur transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 dark:border-white/10 dark:bg-slate-950/70 dark:ring-white/10 scrollbar-thin"
            >
            {step === 1 && (
              <RadioGroup
                value={selectedOption}
                onValueChange={(value) => {
                  setSelectedOption(value);
                  setStorage("choose", value);
                }}
                className="grid gap-3 md:grid-cols-2"
              >
                {modeOptions.map((option) => (
                  <ChoiceCard
                    key={option.value}
                    id={option.value}
                    title={option.title}
                    description={option.description}
                    icon={option.icon}
                    selected={selectedOption === option.value}
                    disabled={option.disabled}
                    badge={option.badge}
                    tone={option.tone}
                  />
                ))}
              </RadioGroup>
            )}

            {step === 2 && (
              <div className="h-full min-h-0 space-y-3 overflow-hidden">
                <RadioGroup
                  value={method}
                  onValueChange={(value) => {
                    setMethod(value);
                    setStorage("method", value);
                  }}
                  className="grid gap-3 md:grid-cols-2"
                >
                  {strategyOptions.map((option) => (
                    <ChoiceCard
                      key={option.value}
                      id={option.value}
                      title={option.title}
                      description={option.description}
                      icon={option.icon}
                      selected={method === option.value}
                      disabled={option.disabled}
                      badge={option.badge}
                      tone={option.tone}
                    >
                      <div className="mt-3 space-y-2.5">
                        <ProgressLine label={t("strategyOptions.auto.setupTime")} value={option.value === "auto" ? 92 : 42} />
                        <ProgressLine label={t("strategyOptions.auto.automationLevel")} value={option.value === "auto" ? 96 : 35} />
                      </div>
                    </ChoiceCard>
                  ))}
                </RadioGroup>

                <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 p-3 dark:border-white/10 dark:bg-white/5">
                  <div className="flex gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-violet-100 text-violet-600">
                      <Sparkles className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-black text-automl-ink dark:text-white">
                        {t("strategyOptions.autoSwitchTitle")}
                      </p>
                      <p className="mt-1 text-xs font-semibold leading-5 text-automl-muted dark:text-white/60">
                        {t("strategyOptions.autoSwitchDesc")}
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={method === "auto"}
                    onCheckedChange={(checked) => {
                      const nextMethod = checked ? "auto" : "";
                      setMethod(nextMethod);
                      setStorage("method", nextMethod);
                    }}
                  />
                </div>
              </div>
            )}

            {step === 3 && (
              <RadioGroup
                value={problemType}
                onValueChange={(value) => {
                  setProblemType(value);
                  setStorage("problem_type", value);
                }}
                className="grid gap-3 md:grid-cols-2"
              >
                {problemOptions.map((option) => (
                  <ChoiceCard
                    key={option.value}
                    id={option.value}
                    title={option.title}
                    description={option.description}
                    icon={option.icon}
                    selected={problemType === option.value}
                    badge={option.badge}
                    tone={option.tone}
                  />
                ))}
              </RadioGroup>
            )}

            {step === 4 && (
              <div className="space-y-5">
                {isFeaturesError ? (
                  <div className="rounded-3xl border border-red-200 bg-red-50 p-8 text-center font-semibold text-red-600">
                    <p className="text-lg font-black">{featureErrorMessage}</p>
                    <p className="mt-2 text-sm text-red-500">
                      Vui lòng quay lại chọn bộ dữ liệu khác hoặc thử lại sau.
                    </p>
                  </div>
                ) : (
                  <>
                    {(isFeaturesFetching || isMetricsFetching) && (
                      <div className="rounded-2xl bg-slate-50 p-4 text-center text-sm font-bold text-slate-500 dark:bg-white/5 dark:text-white/60">
                        {t("step4.loading")}
                      </div>
                    )}

                    {/* 3 Lựa chọn xếp từ trên xuống dưới (Stacked Vertically) */}
                    <div className="space-y-4">
                      {/* Lựa chọn 1: {t("step4.targetTitle")} */}
                      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs dark:border-white/10 dark:bg-white/5">
                        <div className="flex items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-white/5">
                          <div className="flex items-center gap-2.5">
                            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-automl-blue-soft text-xs font-black text-automl-blue">
                              1
                            </span>
                            <div>
                              <h3 className="text-sm font-black text-automl-ink dark:text-white flex items-center gap-2">
                                <Target className="h-4 w-4 text-automl-blue" />
                                Thuộc tính mục tiêu (Target)
                              </h3>
                              <p className="text-xs font-medium text-automl-muted dark:text-white/60">
                                {t("step4.targetDesc")}
                              </p>
                            </div>
                          </div>
                          {selectedTarget && (
                            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-black text-blue-600 dark:bg-blue-950/40 dark:text-blue-300">
                              {t("step4.selectedTarget")} <strong>{selectedTarget}</strong>
                            </span>
                          )}
                        </div>

                        <div className="mt-3 max-h-56 overflow-y-auto pr-1.5 scrollbar-thin">
                          <RadioGroup
                            value={selectedTarget}
                            onValueChange={handleTargetChange}
                            className="grid gap-2.5 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4"
                          >
                            {Object.entries(listFeature).map(([feature, recommended]) => (
                              <label
                                key={feature}
                                htmlFor={`target-${feature}`}
                                className={cn(
                                  "flex cursor-pointer items-center justify-between gap-2.5 rounded-xl border p-2.5 sm:p-3 text-xs sm:text-sm font-bold transition",
                                  selectedTarget === feature
                                    ? "border-automl-blue bg-automl-blue-soft text-automl-blue shadow-xs"
                                    : recommended
                                      ? "border-emerald-200 bg-emerald-50/70 text-emerald-700 hover:border-emerald-300"
                                      : "border-slate-200 bg-white text-slate-700 hover:border-automl-blue/40 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white/80 dark:hover:bg-white/10",
                                )}
                              >
                                <div className="min-w-0 flex items-center gap-1.5">
                                  <span className="truncate">{feature}</span>
                                  {recommended && (
                                    <span className="shrink-0 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-black text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                                      {t("step4.recommended")}
                                    </span>
                                  )}
                                </div>
                                <RadioGroupItem id={`target-${feature}`} value={feature} />
                              </label>
                            ))}
                          </RadioGroup>
                        </div>
                      </section>

                      {/* Lựa chọn 2: {t("step4.featuresTitle")} */}
                      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs dark:border-white/10 dark:bg-white/5">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-slate-100 dark:border-white/5">
                          <div className="flex items-center gap-2.5">
                            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-automl-blue-soft text-xs font-black text-automl-blue">
                              2
                            </span>
                            <div>
                              <h3 className="text-sm font-black text-automl-ink dark:text-white flex items-center gap-2">
                                <FileSpreadsheet className="h-4 w-4 text-automl-blue" />
                                Thuộc tính đưa vào huấn luyện (Features)
                              </h3>
                              <p className="text-xs font-medium text-automl-muted dark:text-white/60">
                                {t("step4.featuresDesc", { count: selectedFeatures.length, total: selectableFeatures.length })}
                              </p>
                            </div>
                          </div>

                          <Button
                            variant="outline"
                            size="sm"
                            className="h-8 rounded-xl border-slate-200 bg-white px-3 text-xs font-bold shadow-none hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 shrink-0"
                            onClick={handleSelectAllFeatures}
                            type="button"
                          >
                            {isAllSelected ? t("step4.deselectAll") : t("step4.selectAll")}
                          </Button>
                        </div>

                        <div className="mt-3 max-h-60 overflow-y-auto pr-1.5 scrollbar-thin">
                          <div className="grid gap-2.5 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
                            {featureNames.map((feature) => {
                              const disabled = feature === selectedTarget;
                              const checked = selectedFeatures.includes(feature);

                              return (
                                <label
                                  key={feature}
                                  htmlFor={`feature-${feature}`}
                                  className={cn(
                                    "flex cursor-pointer items-center gap-2.5 rounded-xl border p-2.5 sm:p-3 text-xs sm:text-sm font-bold transition",
                                    checked
                                      ? "border-automl-blue bg-automl-blue-soft text-automl-blue shadow-xs"
                                      : "border-slate-200 bg-white text-slate-700 hover:border-automl-blue/40 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white/80 dark:hover:bg-white/10",
                                    disabled && "cursor-not-allowed opacity-45 bg-slate-50 dark:bg-white/5",
                                  )}
                                >
                                  <Checkbox
                                    id={`feature-${feature}`}
                                    checked={checked}
                                    disabled={disabled}
                                    onCheckedChange={(checkedValue) =>
                                      handleFeatureToggle(feature, !!checkedValue)
                                    }
                                  />
                                  <span className="min-w-0 truncate">{feature}</span>
                                  {disabled && (
                                    <span className="ml-auto shrink-0 text-[10px] font-semibold text-slate-400">
                                      (Target)
                                    </span>
                                  )}
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      </section>

                      {/* Lựa chọn 3: Chỉ số đánh giá mô hình (Metric) */}
                      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs dark:border-white/10 dark:bg-white/5">
                        <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100 dark:border-white/5">
                          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-automl-blue-soft text-xs font-black text-automl-blue">
                            3
                          </span>
                          <div>
                            <h3 className="text-sm font-black text-automl-ink dark:text-white flex items-center gap-2">
                              <Gauge className="h-4 w-4 text-automl-blue" />
                              {t("step4.metricTitle")}
                            </h3>
                            <p className="text-xs font-medium text-automl-muted dark:text-white/60">
                              {t("step4.metricDesc")}
                            </p>
                          </div>
                        </div>

                        <div className="mt-3">
                          <RadioGroup
                            value={metricSort}
                            onValueChange={handleMetricChange}
                            className="grid gap-2.5 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4"
                          >
                            {Object.entries(metrics).map(([metric, value]) => (
                              <label
                                key={metric}
                                htmlFor={`metric-${value}`}
                                className={cn(
                                  "flex cursor-pointer items-center justify-between gap-3 rounded-xl border p-3 text-xs sm:text-sm font-bold transition",
                                  metricSort === value
                                    ? "border-automl-blue bg-automl-blue-soft text-automl-blue shadow-xs"
                                    : "border-slate-200 bg-white text-slate-700 hover:border-automl-blue/40 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white/80 dark:hover:bg-white/10",
                                )}
                              >
                                <span>{toTitleLabel(value)}</span>
                                <RadioGroupItem id={`metric-${value}`} value={value} />
                              </label>
                            ))}
                          </RadioGroup>
                        </div>
                      </section>
                    </div>
                  </>
                )}
              </div>
            )}
            </div>
          </div>

          <div className="relative z-20 mt-3 shrink-0 border-t border-slate-100 bg-white/70 pt-3 backdrop-blur dark:border-white/10 dark:bg-slate-950/30">
            <div className="grid gap-3 lg:grid-cols-[160px_1fr_160px] lg:items-end">
              <div className="flex justify-start">
              <Button
                variant="outline"
                onClick={handleBack}
                className="h-11 rounded-2xl border-slate-200 bg-white px-5 font-bold shadow-sm dark:border-white/10 dark:bg-white/10"
                type="button"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                {t("actions.back")}
              </Button>
              </div>
              <StepProgress currentStep={displayedStep} />
              <div className="flex justify-start lg:justify-end">
              {step < 4 ? (
                <Button
                  onClick={handleNext}
                  disabled={
                    (step === 1 && !selectedOption) ||
                    (step === 2 && !method) ||
                    (step === 3 && !problemType)
                  }
                  className="h-11 rounded-2xl bg-automl-blue px-5 font-black text-white shadow-sm disabled:opacity-50"
                  type="button"
                >
                  {t("actions.continue")}
                  <ChevronRight className="ml-2 h-4 w-4" />
                </Button>
              ) : (
                !isFeaturesError && (
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        disabled={!canStart}
                        className="h-11 rounded-2xl bg-automl-blue px-5 font-black text-white shadow-sm disabled:opacity-50"
                        type="button"
                      >
                        {t("actions.confirmStart")}
                        <Rocket className="ml-2 h-4 w-4" />
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent className="rounded-3xl">
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t("confirmDialog.title")}</AlertDialogTitle>
                        <AlertDialogDescription>
                          {t("confirmDialog.description")}
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{t("confirmDialog.cancel")}</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={handleStartTraining}
                          className="bg-automl-blue text-white"
                        >
                          {t("confirmDialog.confirm")}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                )
              )}
              </div>
            </div>
          </div>
        </main>

        <aside
          className={cn(
            "min-h-0 overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white shadow-sm transition-all duration-300 dark:border-white/10 dark:bg-white/10",
            summaryCollapsed ? "p-3" : "p-4",
          )}
        >
          <div
            className={cn(
              "flex items-center justify-between gap-3",
              summaryCollapsed && "flex-col",
            )}
          >
            <div className={cn("flex items-center gap-3", summaryCollapsed && "flex-col")}>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-automl-blue-soft text-automl-blue">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <h2
                className={cn(
                  "text-xl font-black text-automl-ink dark:text-white",
                  summaryCollapsed && "sr-only",
                )}
              >
                {t("summary.title")}
              </h2>
            </div>
            <Button
              variant="outline"
              size="icon"
              className="h-10 w-10 rounded-2xl border-slate-200 bg-white shadow-none dark:border-white/10 dark:bg-white/10"
              onClick={() => setSummaryCollapsed((value) => !value)}
              title={summaryCollapsed ? t("summary.open") : t("summary.close")}
              type="button"
            >
              {summaryCollapsed ? (
                <PanelRightOpen className="h-4 w-4" />
              ) : (
                <PanelRightClose className="h-4 w-4" />
              )}
            </Button>
          </div>

          {summaryCollapsed ? (
            <CollapsedSummary items={summaryItems} currentStep={displayedStep} />
          ) : (
            <>
              <div className="mt-4 grid grid-cols-2 rounded-2xl bg-slate-50 p-1 text-sm font-black dark:bg-white/5">
                <span className="rounded-xl bg-white px-3 py-2 text-center text-automl-blue shadow-sm dark:bg-white/10">
                  {t("summary.tabSummary")}
                </span>
                <span className="px-3 py-2 text-center text-slate-500 dark:text-white/55">
                  {t("summary.tabParams")}
                </span>
              </div>

              <div className="mt-4 space-y-4">
                {summaryItems.map((item) => (
                  <SummaryItem
                    key={item.title}
                    icon={item.icon}
                    title={item.title}
                    value={item.value}
                    detail={item.detail}
                  />
                ))}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

const ChoiceCard = ({
  id,
  title,
  description,
  icon: Icon,
  selected,
  disabled,
  badge,
  tone,
  children,
}: ChoiceCardProps) => (
  <label
    htmlFor={id}
    className={cn(
      "relative flex min-h-0 cursor-pointer flex-col rounded-2xl border bg-white p-3 transition dark:bg-white/5",
      selected
        ? "border-automl-blue shadow-lg shadow-blue-500/10 ring-4 ring-automl-blue/10"
        : "border-slate-200 hover:border-automl-blue/40 hover:shadow-md dark:border-white/10",
      disabled && "cursor-not-allowed opacity-50",
    )}
  >
    <RadioGroupItem id={id} value={id} disabled={disabled} className="sr-only" />
    {selected && (
      <span className="absolute right-3 top-3 flex h-7 w-7 items-center justify-center rounded-full bg-automl-blue text-white">
        <Check className="h-4 w-4" />
      </span>
    )}
    <div className={cn("flex h-12 w-12 items-center justify-center rounded-full", tone)}>
      <Icon className="h-6 w-6" />
    </div>
    <div className="mt-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-black text-automl-ink dark:text-white">
          {title}
        </h3>
        {badge && (
          <span className="rounded-full bg-automl-blue-soft px-2.5 py-1 text-xs font-black text-automl-blue">
            {badge}
          </span>
        )}
      </div>
      <p className="mt-1.5 text-xs font-semibold leading-5 text-automl-muted dark:text-white/60">
        {description}
      </p>
    </div>
    {children}
  </label>
);

const ProgressLine = ({ label, value }: { label: string; value: number }) => (
  <div>
    <div className="mb-1.5 flex justify-between text-xs font-black text-slate-500 dark:text-white/55">
      <span>{label}</span>
      <span>{value}%</span>
    </div>
    <div className="h-1.5 rounded-full bg-slate-100 dark:bg-white/10">
      <div
        className="h-1.5 rounded-full bg-automl-blue"
        style={{ width: `${value}%` }}
      />
    </div>
  </div>
);

const StepBubbleDeck = ({ currentStep }: { currentStep: number }) => {
  const t = useTranslations("TrainingWizard.steps");
  return (
  <div className="pointer-events-none absolute inset-x-4 top-1 z-0 hidden h-14 overflow-visible md:block">
    {steps.map((stepItem) => {
      const Icon = stepItem.icon;
      const distance = stepItem.id - currentStep;
      const isCurrent = stepItem.id === currentStep;
      const isPast = stepItem.id < currentStep;
      const translateX = distance * 172;
      const translateY = Math.abs(distance) * 4;
      const scale = isCurrent ? 1 : Math.max(0.78, 0.94 - Math.abs(distance) * 0.05);

      return (
        <div
          key={stepItem.id}
          className={cn(
            "absolute left-1/2 top-0 flex h-12 w-44 items-center gap-2.5 rounded-2xl border px-3 shadow-xl backdrop-blur transition-all duration-500",
            isCurrent
              ? "border-automl-blue/40 bg-white/90 text-automl-blue shadow-blue-500/15"
              : isPast
                ? "border-emerald-200 bg-emerald-50/80 text-emerald-600"
                : "border-slate-200 bg-white/70 text-slate-400 dark:border-white/10 dark:bg-white/10",
          )}
          style={{
            opacity: isCurrent ? 0.92 : Math.max(0.22, 0.68 - Math.abs(distance) * 0.12),
            transform: `translateX(calc(-50% + ${translateX}px)) translateY(${translateY}px) scale(${scale})`,
            zIndex: 20 - Math.abs(distance),
          }}
        >
          <span
            className={cn(
              "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-black",
              isCurrent
                ? "bg-automl-blue text-white"
                : isPast
                  ? "bg-emerald-100 text-emerald-600"
                  : "bg-slate-100 text-slate-400",
            )}
          >
            {isPast ? <Check className="h-4 w-4" /> : stepItem.id}
          </span>
          <div className="min-w-0">
            <Icon className="mb-0.5 h-3.5 w-3.5" />
            <p className="truncate text-xs font-black">{t(stepItem.labelKey)}</p>
          </div>
        </div>
      );
    })}
  </div>
  );
};



const SummaryItem = ({
  icon: Icon,
  title,
  value,
  detail,
}: {
  icon: LucideIcon;
  title: string;
  value: string;
  detail: string;
}) => (
  <div className="border-b border-slate-100 pb-4 last:border-0 last:pb-0 dark:border-white/10">
    <div className="flex gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-50 text-automl-blue dark:bg-white/5">
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-black uppercase tracking-wide text-automl-blue">
          {title}
        </p>
        <p className="mt-1 truncate font-black text-automl-ink dark:text-white">
          {value}
        </p>
        <p className="mt-0.5 text-sm font-semibold text-automl-muted dark:text-white/60">
          {detail}
        </p>
      </div>
    </div>
  </div>
);

const CollapsedSummary = ({
  items,
  currentStep,
}: {
  items: SummaryConfig[];
  currentStep: number;
}) => (
  <div className="mt-5 flex flex-col items-center gap-3">
    {items.map((item, index) => {
      const Icon = item.icon;
      const active = index + 1 <= currentStep;

      return (
        <div
          key={item.title}
          title={`${item.title}: ${item.value}`}
          className={cn(
            "relative flex h-12 w-12 items-center justify-center rounded-2xl border transition",
            active
              ? "border-automl-blue/30 bg-automl-blue-soft text-automl-blue"
              : "border-slate-200 bg-slate-50 text-slate-400 dark:border-white/10 dark:bg-white/5",
          )}
        >
          <Icon className="h-5 w-5" />
          {active && (
            <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-automl-blue ring-2 ring-white dark:ring-slate-950" />
          )}
        </div>
      );
    })}
  </div>
);

const StepProgress = ({ currentStep }: { currentStep: number }) => {
  const t = useTranslations("TrainingWizard.steps");
  return (
  <div className="flex h-16 min-w-0 flex-1 items-center justify-center overflow-hidden px-2 pb-1">
    {steps.map((stepItem, index) => {
      const done = stepItem.id < currentStep;
      const active = stepItem.id === currentStep;

      return (
        <div key={stepItem.id} className="flex items-center">
          <div className="relative flex min-w-[68px] flex-col items-center">
            <span
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-black shadow-sm transition",
                done
                  ? "border-emerald-300 bg-emerald-50 text-emerald-600"
                  : active
                    ? "border-automl-blue bg-automl-blue text-white ring-4 ring-blue-100"
                    : "border-slate-200 bg-white text-slate-400 dark:border-white/10 dark:bg-white/10",
              )}
            >
              {done ? <Check className="h-4 w-4" /> : stepItem.id}
            </span>
            <p
              className={cn(
                "mt-1 whitespace-nowrap text-[11px] font-black leading-none",
                active
                  ? "text-automl-blue"
                  : done
                    ? "text-emerald-600"
                    : "text-slate-400 dark:text-white/45",
              )}
            >
              {t(stepItem.labelKey)}
            </p>
          </div>
          {index < steps.length - 1 && (
            <span
              className={cn(
                "mb-5 h-0.5 w-10 rounded-full",
                done ? "bg-emerald-300" : "bg-slate-200 dark:bg-white/10",
              )}
            />
          )}
        </div>
      );
    })}
  </div>
  );
};
