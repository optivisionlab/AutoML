"use client";

import { type ReactNode, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronRight,
  Database,
  FileSpreadsheet,
  Gauge,
  Info,
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
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { useGetFeaturesQuery, useGetMetricsQuery } from "@/redux/api/automlApi";
import { cn } from "@/lib/utils";
import toTitleLabel from "@/utils/toTitleLable";

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

const steps = [
  { id: 1, label: "Dữ liệu", icon: Database },
  { id: 2, label: "Chế độ", icon: Wand2 },
  { id: 3, label: "Bài toán", icon: Target },
  { id: 4, label: "Tham số", icon: SlidersHorizontal },
  { id: 5, label: "Xác nhận", icon: CheckCircle2 },
];

const modeOptions = [
  {
    value: "new_model",
    title: "Mô hình mới",
    description: "Tạo pipeline huấn luyện độc lập cho bộ dữ liệu này.",
    icon: BrainCircuit,
    badge: "Khuyến nghị",
    tone: "bg-blue-50 text-blue-600",
  },
  {
    value: "new_version",
    title: "Phiên bản mới",
    description: "Huấn luyện tiếp từ một mô hình đã có.",
    icon: Layers3,
    badge: "Sắp có",
    tone: "bg-slate-100 text-slate-500",
    disabled: true,
  },
];

const strategyOptions = [
  {
    value: "auto",
    title: "AutoML tự động",
    description: "HAutoML tự chọn pipeline, thử nhiều cấu hình và tối ưu metric.",
    icon: Sparkles,
    badge: "Đề xuất",
    tone: "bg-violet-50 text-violet-600",
  },
  {
    value: "custom",
    title: "Tuỳ chỉnh thủ công",
    description: "Tự chọn thuật toán và tham số chi tiết.",
    icon: Settings2,
    badge: "Sắp có",
    tone: "bg-slate-100 text-slate-500",
    disabled: true,
  },
];

const problemOptions = [
  {
    value: "classification",
    title: "Phân loại",
    description: "Dự đoán nhãn rời rạc như churn, fraud, approved/rejected.",
    icon: Target,
    badge: "Classification",
    tone: "bg-emerald-50 text-emerald-600",
  },
  {
    value: "regression",
    title: "Hồi quy",
    description: "Dự đoán giá trị liên tục như doanh số, chi phí, điểm số.",
    icon: Gauge,
    badge: "Regression",
    tone: "bg-amber-50 text-amber-600",
  },
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
      title: "Dữ liệu",
      value: datasetName,
      detail: datasetID ? `ID: ${datasetID}` : "Chưa xác định",
    },
    {
      icon: BrainCircuit,
      title: "Kiểu huấn luyện",
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
      title: "Loại bài toán",
      value:
        problemType === "classification"
          ? "Phân loại"
          : problemType === "regression"
            ? "Hồi quy"
            : "Chưa chọn",
      detail: selectedTarget ? `Dự đoán: ${selectedTarget}` : "Chưa chọn target",
    },
    {
      icon: SlidersHorizontal,
      title: "Tham số chính",
      value: metricSort ? toTitleLabel(metricSort) : "Chưa chọn metric",
      detail: `${selectedFeatures.length} feature đầu vào`,
    },
    {
      icon: Rocket,
      title: "Tài nguyên",
      value: "Auto",
      detail: "Ưu tiên GPU nếu khả dụng",
    },
  ];

  const stepTitle = useMemo(() => {
    if (step === 1) return "Chọn kiểu huấn luyện";
    if (step === 2) return "Chọn chiến lược AutoML";
    if (step === 3) return "Chọn loại bài toán";
    return "Thiết lập tham số huấn luyện";
  }, [step]);

  const stepDescription = useMemo(() => {
    if (step === 1) {
      return "Bắt đầu một mô hình mới hoặc tạo phiên bản mới khi hệ thống hỗ trợ.";
    }
    if (step === 2) {
      return "Chọn cách HAutoML chạy pipeline và tối ưu cấu hình.";
    }
    if (step === 3) {
      return "Loại bài toán quyết định metric, target phù hợp và cách đánh giá mô hình.";
    }
    return "Chọn target, feature đầu vào và metric chính trước khi bắt đầu huấn luyện.";
  }, [step]);

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
    <div className="h-[calc(100svh-7rem)] overflow-hidden rounded-[2rem] bg-gradient-to-br from-slate-50 via-white to-blue-50/70 p-4 shadow-sm ring-1 ring-slate-200 dark:from-white/5 dark:via-white/5 dark:to-blue-950/20 dark:ring-white/10 lg:p-5">
      <div
        className={cn(
          "grid h-full min-h-0 gap-5 transition-[grid-template-columns] duration-300",
          summaryCollapsed ? "xl:grid-cols-[1fr_96px]" : "xl:grid-cols-[1fr_360px]",
        )}
      >
        <main className="relative flex min-h-0 flex-col overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white/80 p-5 shadow-sm backdrop-blur dark:border-white/10 dark:bg-white/10 lg:p-8">
          <div className="pointer-events-none absolute -left-16 top-16 h-44 w-44 rounded-full bg-blue-100/70 blur-3xl dark:bg-blue-500/10" />
          <div className="pointer-events-none absolute bottom-10 right-10 h-32 w-32 rounded-full bg-cyan-100/70 blur-3xl dark:bg-cyan-500/10" />

          <div className="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-3xl font-black tracking-tight text-automl-ink dark:text-white">
                  {step}. {stepTitle}
                </h1>
                <Info className="h-5 w-5 text-slate-400" />
              </div>
              <p className="mt-3 max-w-3xl text-sm font-semibold leading-6 text-automl-muted dark:text-white/60">
                {stepDescription}
              </p>
            </div>
            <Button
              variant="outline"
              className="h-11 rounded-2xl border-slate-200 bg-white px-4 font-bold shadow-none dark:border-white/10 dark:bg-white/10"
              type="button"
            >
              <Lightbulb className="mr-2 h-4 w-4 text-automl-blue" />
              Gợi ý cấu hình
            </Button>
          </div>

          <div className="relative z-10 mt-8 min-h-0 flex-1 overflow-hidden pr-1 pt-14">
            <StepBubbleDeck currentStep={displayedStep} />
            <div
              key={step}
              className="relative z-20 h-full overflow-hidden rounded-[2rem] border border-white/80 bg-white/95 p-4 shadow-2xl shadow-blue-950/10 ring-1 ring-blue-100/80 backdrop-blur transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 dark:border-white/10 dark:bg-slate-950/70 dark:ring-white/10 lg:p-5"
            >
            {step === 1 && (
              <RadioGroup
                value={selectedOption}
                onValueChange={(value) => {
                  setSelectedOption(value);
                  setStorage("choose", value);
                }}
                className="grid gap-4 md:grid-cols-2"
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
              <div className="h-full min-h-0 space-y-5 overflow-hidden">
                <RadioGroup
                  value={method}
                  onValueChange={(value) => {
                    setMethod(value);
                    setStorage("method", value);
                  }}
                  className="grid gap-4 md:grid-cols-2"
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
                      <div className="mt-4 space-y-3">
                        <ProgressLine label="Thời gian thiết lập" value={option.value === "auto" ? 92 : 42} />
                        <ProgressLine label="Mức tự động hóa" value={option.value === "auto" ? 96 : 35} />
                      </div>
                    </ChoiceCard>
                  ))}
                </RadioGroup>

                <div className="flex items-center justify-between rounded-3xl border border-slate-200 bg-slate-50 p-5 dark:border-white/10 dark:bg-white/5">
                  <div className="flex gap-4">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-violet-100 text-violet-600">
                      <Sparkles className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="font-black text-automl-ink dark:text-white">
                        Để HAutoML tự động tối ưu pipeline
                      </p>
                      <p className="mt-1 text-sm font-semibold text-automl-muted dark:text-white/60">
                        Hệ thống sẽ thử nhiều cấu hình và chọn mô hình tốt nhất theo metric đã chọn.
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
                className="grid gap-4 md:grid-cols-2"
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
                        Đang tải cấu hình huấn luyện...
                      </div>
                    )}

                    <div className="grid min-h-0 gap-4 lg:grid-cols-2">
                      <section className="min-h-0 rounded-3xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-white/5">
                        <SectionTitle
                          icon={Target}
                          title="Thuộc tính mục tiêu"
                          description="Chọn cột cần dự đoán."
                        />
                        <ScrollArea className="mt-4 h-48 rounded-2xl border border-slate-100 p-3 dark:border-white/10">
                          <RadioGroup
                            value={selectedTarget}
                            onValueChange={handleTargetChange}
                            className="grid gap-3 xl:grid-cols-2"
                          >
                            {Object.entries(listFeature).map(([feature, recommended]) => (
                              <label
                                key={feature}
                                htmlFor={`target-${feature}`}
                                className={cn(
                                  "flex cursor-pointer items-center justify-between gap-3 rounded-2xl border p-3 text-sm font-bold transition",
                                  selectedTarget === feature
                                    ? "border-automl-blue bg-automl-blue-soft text-automl-blue"
                                    : recommended
                                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                      : "border-slate-200 bg-white text-slate-600 hover:border-automl-blue/40 dark:border-white/10 dark:bg-white/5 dark:text-white/70",
                                )}
                              >
                                <span className="min-w-0 truncate">{feature}</span>
                                <RadioGroupItem id={`target-${feature}`} value={feature} />
                              </label>
                            ))}
                          </RadioGroup>
                        </ScrollArea>
                      </section>

                      <section className="min-h-0 rounded-3xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-white/5">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <SectionTitle
                            icon={FileSpreadsheet}
                            title="Thuộc tính đưa vào huấn luyện"
                            description={`${selectedFeatures.length} / ${selectableFeatures.length} cột đang được chọn.`}
                          />
                          <Button
                            variant="outline"
                            className="h-10 rounded-2xl border-slate-200 bg-white font-bold shadow-none dark:border-white/10 dark:bg-white/10"
                            onClick={handleSelectAllFeatures}
                            type="button"
                          >
                            {isAllSelected ? "Bỏ chọn tất cả" : "Chọn tất cả"}
                          </Button>
                        </div>
                        <ScrollArea className="mt-4 h-48 rounded-2xl border border-slate-100 p-3 dark:border-white/10">
                          <div className="grid gap-3 xl:grid-cols-2">
                            {featureNames.map((feature) => {
                              const disabled = feature === selectedTarget;
                              const checked = selectedFeatures.includes(feature);

                              return (
                                <label
                                  key={feature}
                                  htmlFor={`feature-${feature}`}
                                  className={cn(
                                    "flex cursor-pointer items-center gap-3 rounded-2xl border p-3 text-sm font-bold transition",
                                    checked
                                      ? "border-automl-blue bg-automl-blue-soft text-automl-blue"
                                      : "border-slate-200 bg-white text-slate-600 hover:border-automl-blue/40 dark:border-white/10 dark:bg-white/5 dark:text-white/70",
                                    disabled && "cursor-not-allowed opacity-45",
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
                                </label>
                              );
                            })}
                          </div>
                        </ScrollArea>
                      </section>
                    </div>

                    <section className="rounded-3xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-white/5">
                      <SectionTitle
                        icon={Gauge}
                        title="Chỉ số đánh giá"
                        description="Metric này sẽ được dùng để chọn mô hình tốt nhất."
                      />
                      <RadioGroup
                        value={metricSort}
                        onValueChange={handleMetricChange}
                        className="mt-4 grid gap-3 md:grid-cols-2 2xl:grid-cols-3"
                      >
                        {Object.entries(metrics).map(([metric, value]) => (
                          <label
                            key={metric}
                            htmlFor={`metric-${value}`}
                            className={cn(
                              "flex cursor-pointer items-center justify-between gap-3 rounded-2xl border p-4 text-sm font-bold transition",
                              metricSort === value
                                ? "border-automl-blue bg-automl-blue-soft text-automl-blue"
                                : "border-slate-200 bg-white text-slate-600 hover:border-automl-blue/40 dark:border-white/10 dark:bg-white/5 dark:text-white/70",
                            )}
                          >
                            <span>{toTitleLabel(value)}</span>
                            <RadioGroupItem id={`metric-${value}`} value={value} />
                          </label>
                        ))}
                      </RadioGroup>
                    </section>
                  </>
                )}
              </div>
            )}
            </div>
          </div>

          <div className="relative z-20 mt-auto border-t border-slate-100 bg-white/70 pt-5 backdrop-blur dark:border-white/10 dark:bg-slate-950/30">
            <div className="grid gap-4 lg:grid-cols-[180px_1fr_180px] lg:items-end">
              <div className="flex justify-start">
              <Button
                variant="outline"
                onClick={handleBack}
                className="h-12 rounded-2xl border-slate-200 bg-white px-5 font-bold shadow-sm dark:border-white/10 dark:bg-white/10"
                type="button"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Quay lại
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
                  className="h-12 rounded-2xl bg-automl-blue px-5 font-black text-white shadow-sm disabled:opacity-50"
                  type="button"
                >
                  Tiếp tục
                  <ChevronRight className="ml-2 h-4 w-4" />
                </Button>
              ) : (
                !isFeaturesError && (
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        disabled={!canStart}
                        className="h-12 rounded-2xl bg-automl-blue px-5 font-black text-white shadow-sm disabled:opacity-50"
                        type="button"
                      >
                        Xác nhận & bắt đầu
                        <Rocket className="ml-2 h-4 w-4" />
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent className="rounded-3xl">
                      <AlertDialogHeader>
                        <AlertDialogTitle>Xác nhận huấn luyện</AlertDialogTitle>
                        <AlertDialogDescription>
                          HAutoML sẽ bắt đầu huấn luyện với target, feature và metric đã chọn.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Hủy</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={handleStartTraining}
                          className="bg-automl-blue text-white"
                        >
                          Đồng ý
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
            "min-h-0 overflow-y-auto rounded-[1.75rem] border border-slate-200 bg-white shadow-sm transition-all duration-300 dark:border-white/10 dark:bg-white/10",
            summaryCollapsed ? "p-3" : "p-5",
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
                Tóm tắt cấu hình
              </h2>
            </div>
            <Button
              variant="outline"
              size="icon"
              className="h-10 w-10 rounded-2xl border-slate-200 bg-white shadow-none dark:border-white/10 dark:bg-white/10"
              onClick={() => setSummaryCollapsed((value) => !value)}
              title={summaryCollapsed ? "Mở tóm tắt" : "Thu gọn tóm tắt"}
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
              <div className="mt-6 grid grid-cols-2 rounded-2xl bg-slate-50 p-1 text-sm font-black dark:bg-white/5">
                <span className="rounded-xl bg-white px-3 py-2 text-center text-automl-blue shadow-sm dark:bg-white/10">
                  Tóm tắt
                </span>
                <span className="px-3 py-2 text-center text-slate-500 dark:text-white/55">
                  Gợi ý tham số
                </span>
              </div>

              <div className="mt-6 space-y-5">
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
      "relative flex min-h-56 cursor-pointer flex-col rounded-3xl border bg-white p-5 transition dark:bg-white/5",
      selected
        ? "border-automl-blue shadow-lg shadow-blue-500/10 ring-4 ring-automl-blue/10"
        : "border-slate-200 hover:border-automl-blue/40 hover:shadow-md dark:border-white/10",
      disabled && "cursor-not-allowed opacity-50",
    )}
  >
    <RadioGroupItem id={id} value={id} disabled={disabled} className="sr-only" />
    {selected && (
      <span className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full bg-automl-blue text-white">
        <Check className="h-4 w-4" />
      </span>
    )}
    <div className={cn("flex h-20 w-20 items-center justify-center rounded-full", tone)}>
      <Icon className="h-9 w-9" />
    </div>
    <div className="mt-5">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-xl font-black text-automl-ink dark:text-white">
          {title}
        </h3>
        {badge && (
          <span className="rounded-full bg-automl-blue-soft px-2.5 py-1 text-xs font-black text-automl-blue">
            {badge}
          </span>
        )}
      </div>
      <p className="mt-3 text-sm font-semibold leading-6 text-automl-muted dark:text-white/60">
        {description}
      </p>
    </div>
    {children}
  </label>
);

const ProgressLine = ({ label, value }: { label: string; value: number }) => (
  <div>
    <div className="mb-2 flex justify-between text-xs font-black text-slate-500 dark:text-white/55">
      <span>{label}</span>
      <span>{value}%</span>
    </div>
    <div className="h-2 rounded-full bg-slate-100 dark:bg-white/10">
      <div
        className="h-2 rounded-full bg-automl-blue"
        style={{ width: `${value}%` }}
      />
    </div>
  </div>
);

const StepBubbleDeck = ({ currentStep }: { currentStep: number }) => (
  <div className="pointer-events-none absolute inset-x-4 top-0 z-0 hidden h-28 overflow-visible md:block">
    {steps.map((stepItem) => {
      const Icon = stepItem.icon;
      const distance = stepItem.id - currentStep;
      const isCurrent = stepItem.id === currentStep;
      const isPast = stepItem.id < currentStep;
      const translateX = distance * 210;
      const translateY = Math.abs(distance) * 7 - 18;
      const scale = isCurrent ? 1 : Math.max(0.78, 0.94 - Math.abs(distance) * 0.05);

      return (
        <div
          key={stepItem.id}
          className={cn(
            "absolute left-1/2 top-0 flex h-20 w-56 items-center gap-3 rounded-[1.35rem] border px-4 shadow-xl backdrop-blur transition-all duration-500",
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
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-black",
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
            <Icon className="mb-1 h-4 w-4" />
            <p className="truncate text-xs font-black">{stepItem.label}</p>
          </div>
        </div>
      );
    })}
  </div>
);

const SectionTitle = ({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) => (
  <div className="flex gap-3">
    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-automl-blue-soft text-automl-blue">
      <Icon className="h-5 w-5" />
    </div>
    <div>
      <h2 className="font-black text-automl-ink dark:text-white">{title}</h2>
      <p className="mt-1 text-sm font-semibold text-automl-muted dark:text-white/60">
        {description}
      </p>
    </div>
  </div>
);

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
  <div className="border-b border-slate-100 pb-5 last:border-0 last:pb-0 dark:border-white/10">
    <div className="flex gap-4">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-slate-50 text-automl-blue dark:bg-white/5">
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-black uppercase tracking-wide text-automl-blue">
          {title}
        </p>
        <p className="mt-2 truncate font-black text-automl-ink dark:text-white">
          {value}
        </p>
        <p className="mt-1 text-sm font-semibold text-automl-muted dark:text-white/60">
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
  <div className="mt-6 flex flex-col items-center gap-3">
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

const StepProgress = ({ currentStep }: { currentStep: number }) => (
  <div className="flex min-w-0 flex-1 items-end justify-center overflow-x-auto px-2 pb-1">
    {steps.map((stepItem, index) => {
      const done = stepItem.id < currentStep;
      const active = stepItem.id === currentStep;

      return (
        <div key={stepItem.id} className="flex items-center">
          <div className="relative flex min-w-[76px] flex-col items-center">
            <span
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-black shadow-sm transition",
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
                "mt-2 whitespace-nowrap text-xs font-black",
                active
                  ? "text-automl-blue"
                  : done
                    ? "text-emerald-600"
                    : "text-slate-400 dark:text-white/45",
              )}
            >
              {stepItem.label}
            </p>
          </div>
          {index < steps.length - 1 && (
            <span
              className={cn(
                "mb-7 h-0.5 w-12 rounded-full",
                done ? "bg-emerald-300" : "bg-slate-200 dark:bg-white/10",
              )}
            />
          )}
        </div>
      );
    })}
  </div>
);
