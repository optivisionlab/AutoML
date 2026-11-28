"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
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
  Zap,
  TrendingUp,
  Info,
  CheckSquare,
  Square,
  Search,
  RotateCcw,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/shared/components/ui/sheet";
import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/shared/components/ui/radio-group";
import { Switch } from "@/shared/components/ui/switch";
import { useToast } from "@/shared/hooks/use-toast";
import {
  useGetFeaturesQuery,
  useGetMetricsQuery,
  useGetDatasetPreviewQuery,
} from "@/core/api/automlApi";
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
  badgeVariant?: "primary" | "warning" | "success" | "muted";
  features?: string[];
  tone: string;
  children?: ReactNode;
};

type SummaryConfig = {
  id: number;
  icon: LucideIcon;
  title: string;
  value: string;
  detail: string;
  isConfigured: boolean;
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
  const { toast } = useToast();

  const [step, setStep] = useState(1);
  const [selectedOption, setSelectedOption] = useState(initialChoose);
  const [method, setMethod] = useState("");
  const [problemType, setProblemType] = useState("");
  const [selectedTarget, setSelectedTarget] = useState("");
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [metricSort, setMetricSort] = useState("");
  const [summaryCollapsed, setSummaryCollapsed] = useState(false);
  const [activeSummaryTab, setActiveSummaryTab] = useState<"summary" | "recommendations">("summary");
  const [isAdvisorOpen, setIsAdvisorOpen] = useState(false);
  const [isMobileSummaryOpen, setIsMobileSummaryOpen] = useState(false);
  const [featureSearchQuery, setFeatureSearchQuery] = useState("");

  const modeOptions = [
    {
      value: "new_model",
      title: t("modeOptions.newModel.title"),
      description: t("modeOptions.newModel.description"),
      icon: BrainCircuit,
      badge: t("modeOptions.newModel.badge"),
      badgeVariant: "primary" as const,
      tone: "bg-blue-50 text-automl-blue dark:bg-blue-500/10 dark:text-cyan-300",
      features: isEn
        ? [
            "Independent AutoML pipeline trained from scratch",
            "Automatic data cleaning & feature pre-processing",
            "Multi-model search & validation (LightGBM, XGBoost, CatBoost)",
          ]
        : [
            "Tạo pipeline AutoML độc lập từ đầu cho bộ dữ liệu",
            "Tự động làm sạch dữ liệu & tiền xử lý các thuộc tính",
            "Thử nghiệm đồng thời nhiều kiến trúc thuật toán tối tân",
          ],
    },
    {
      value: "new_version",
      title: t("modeOptions.newVersion.title"),
      description: t("modeOptions.newVersion.description"),
      icon: Layers3,
      badge: t("modeOptions.newVersion.badge"),
      badgeVariant: "muted" as const,
      tone: "bg-slate-100 text-slate-500 dark:bg-white/5 dark:text-white/40",
      disabled: true,
      features: isEn
        ? [
            "Fine-tune from an existing model checkpoint",
            "Inherit trained weights & optimal hyperparameters",
            "Compare performance drift across versions",
          ]
        : [
            "Huấn luyện tăng cường từ checkpoint mô hình sẵn có",
            "Kế thừa trọng số và siêu tham số tốt nhất",
            "Đo lường độ lệch hiệu năng qua từng phiên bản",
          ],
    },
  ];

  const strategyOptions = [
    {
      value: "auto",
      title: t("strategyOptions.auto.title"),
      description: t("strategyOptions.auto.description"),
      icon: Sparkles,
      badge: t("strategyOptions.auto.badge"),
      badgeVariant: "primary" as const,
      tone: "bg-blue-50 text-automl-blue dark:bg-blue-500/10 dark:text-cyan-300",
      features: isEn
        ? [
            "Intelligent algorithm selection based on data characteristics",
            "Automated Cross-Validation & Early Stopping",
            "Ready for production deployment with optimal latency",
          ]
        : [
            "Tự động chọn thuật toán phù hợp nhất với dữ liệu",
            "K-Fold Cross-Validation và Early Stopping thông minh",
            "Sẵn sàng triển khai phục vụ thực tế với độ trễ tối ưu",
          ],
    },
    {
      value: "custom",
      title: t("strategyOptions.custom.title"),
      description: t("strategyOptions.custom.description"),
      icon: Settings2,
      badge: t("strategyOptions.custom.badge"),
      badgeVariant: "muted" as const,
      tone: "bg-slate-100 text-slate-500 dark:bg-white/5 dark:text-white/40",
      disabled: true,
      features: isEn
        ? [
            "Manually define custom hyperparameter search grids",
            "Select specific model architectures to evaluate",
            "Custom train/val/test data splits",
          ]
        : [
            "Tự thiết lập không gian tìm kiếm siêu tham số chi tiết",
            "Chỉ định danh sách thuật toán cụ thể cần thử nghiệm",
            "Tùy biến tỉ lệ phân chia tập huấn luyện và kiểm thử",
          ],
    },
  ];

  const problemOptions = [
    {
      value: "classification",
      title: t("problemOptions.classification.title"),
      description: t("problemOptions.classification.description"),
      icon: Target,
      badge: t("problemOptions.classification.badge"),
      badgeVariant: "primary" as const,
      tone: "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-cyan-300",
      features: isEn
        ? [
            "Predict categorical labels (binary or multi-class)",
            "Use cases: Credit Approval, Churn Detection, Fraud",
            "Key metrics: Accuracy, F1-Score, ROC-AUC, Precision",
          ]
        : [
            "Dự đoán nhãn danh mục rời rạc (nhị phân hoặc đa lớp)",
            "Ứng dụng: Duyệt tín dụng, dự báo churn, phân loại rủi ro",
            "Chỉ số mục tiêu: Accuracy, F1-Score, ROC-AUC, Precision",
          ],
    },
    {
      value: "regression",
      title: t("problemOptions.regression.title"),
      description: t("problemOptions.regression.description"),
      icon: Gauge,
      badge: t("problemOptions.regression.badge"),
      badgeVariant: "warning" as const,
      tone: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",
      features: isEn
        ? [
            "Predict continuous numeric values and ranges",
            "Use cases: Sales forecasting, Price prediction, Risk scores",
            "Key metrics: R², RMSE, MAE, MSE",
          ]
        : [
            "Dự đoán giá trị số liên tục trên trục thực",
            "Ứng dụng: Dự báo doanh thu, định giá bất động sản, điểm số",
            "Chỉ số mục tiêu: R², RMSE, MAE, MSE",
          ],
    },
  ];

  const shouldFetchTrainingMeta =
    step === 4 && Boolean(datasetID) && Boolean(problemType);
  const {
    data: featuresData,
    isError: isFeaturesError,
    isFetching: isFeaturesFetching,
    refetch: refetchFeatures,
  } = useGetFeaturesQuery(
    { datasetId: datasetID ?? "", problemType },
    { skip: !shouldFetchTrainingMeta },
  );
  const { data: metricsData, isFetching: isMetricsFetching } =
    useGetMetricsQuery(problemType, {
      skip: !shouldFetchTrainingMeta,
    });
  const { data: previewData } = useGetDatasetPreviewQuery(datasetID ?? "", {
    skip: !shouldFetchTrainingMeta,
  });

  const listFeature = useMemo<Record<string, boolean>>(() => {
    const raw =
      (featuresData as any)?.features ??
      (featuresData as any)?.data?.features ??
      (featuresData as any)?.data ??
      featuresData;

    const result: Record<string, boolean> = {};

    if (Array.isArray(raw) && raw.length > 0) {
      raw.forEach((f: string) => {
        result[f] = true;
      });
      return result;
    }

    if (raw && typeof raw === "object") {
      Object.entries(raw).forEach(([k, v]) => {
        if (k !== "success" && k !== "message" && k !== "status" && k !== "meta") {
          result[k] = Boolean(v);
        }
      });
      if (Object.keys(result).length > 0) {
        return result;
      }
    }

    // Fallback: nếu /features rỗng, đọc schema các cột từ data preview
    if (previewData?.data && previewData.data.length > 0) {
      const firstRow = previewData.data[0];
      if (firstRow && typeof firstRow === "object") {
        Object.keys(firstRow).forEach((col) => {
          result[col] = true;
        });
        return result;
      }
    }

    return {};
  }, [featuresData, previewData?.data]);

<<<<<<< HEAD
  const listFeature = featuresData?.features ?? (featuresData as any) ?? {};
=======
>>>>>>> 74d7c7dad45c7c2b084c2a84f048936d3ec164fe
  const metrics = metricsData?.metrics ?? {};
  const featureNames = Object.keys(listFeature);
  const selectableFeatures = featureNames.filter((name) => name !== selectedTarget);
  const isAllSelected =
    selectableFeatures.length > 0 &&
    selectableFeatures.every((name) => selectedFeatures.includes(name));
  const canStart =
    Boolean(selectedTarget) && selectedFeatures.length > 0 && Boolean(metricSort);

  // Filter features based on search query
  const filteredFeatures = useMemo(() => {
    if (!featureSearchQuery.trim()) return featureNames;
    const query = featureSearchQuery.toLowerCase();
    return featureNames.filter((f) => f.toLowerCase().includes(query));
  }, [featureNames, featureSearchQuery]);

  // Tự động chọn mục tiêu và tất cả các đặc trưng khi tải xong danh sách cột
  useEffect(() => {
    if (featureNames.length === 0) return;

    if (!selectedTarget) {
      const recommendedTarget = Object.entries(listFeature).find(([, isRec]) => isRec)?.[0];
      const targetToSelect = recommendedTarget || featureNames[featureNames.length - 1];

      if (targetToSelect) {
        setSelectedTarget(targetToSelect);
        setStorage("target", targetToSelect);

        const otherFeatures = featureNames.filter((f) => f !== targetToSelect);
        setSelectedFeatures(otherFeatures);
        setStorage("list_feature", JSON.stringify(otherFeatures));
      }
    } else if (selectedFeatures.length === 0) {
      const otherFeatures = featureNames.filter((f) => f !== selectedTarget);
      if (otherFeatures.length > 0) {
        setSelectedFeatures(otherFeatures);
        setStorage("list_feature", JSON.stringify(otherFeatures));
      }
    }
  }, [featureNames, listFeature, selectedTarget, selectedFeatures.length]);

  // Tự động chọn metric mặc định nếu chưa chọn
  useEffect(() => {
    if (!metricSort && metrics && Object.keys(metrics).length > 0) {
      const defaultMetric =
        problemType === "regression"
          ? (metrics["r2"] ? "r2" : Object.values(metrics)[0])
          : (metrics["accuracy"] ? "accuracy" : Object.values(metrics)[0]);

      if (defaultMetric) {
        setMetricSort(defaultMetric);
        setStorage("metric_sort", defaultMetric);
      }
    }
  }, [metrics, metricSort, problemType]);

  const displayedStep = step === 4 && canStart ? 5 : step;

  const summaryItems: SummaryConfig[] = [
    {
      id: 1,
      icon: Database,
      title: t("summary.dataset"),
      value: datasetName || "Australian Credit Approval",
      detail: datasetID ? `ID: ${datasetID}` : "Chưa xác định",
      isConfigured: Boolean(datasetID || datasetName),
    },
    {
      id: 2,
      icon: BrainCircuit,
      title: t("summary.mode"),
      value:
        selectedOption === "new_version"
          ? "Phiên bản mới"
          : selectedOption
            ? "Mô hình mới"
            : (isEn ? "Not selected" : "Chưa chọn"),
      detail:
        method === "auto"
          ? (isEn ? "AutoML automated optimization" : "AutoML tự động tối ưu")
          : method
            ? (isEn ? "Custom strategy" : "Tùy chỉnh chiến lược")
            : (isEn ? "Pending strategy choice" : "Chưa chọn chiến lược"),
      isConfigured: Boolean(selectedOption && method),
    },
    {
      id: 3,
      icon: Target,
      title: t("summary.problem"),
      value:
        problemType === "classification"
          ? (isEn ? "Classification" : "Phân loại")
          : problemType === "regression"
            ? (isEn ? "Regression" : "Hồi quy")
            : (isEn ? "Not selected" : "Chưa chọn"),
      detail: selectedTarget ? `${t("summary.target")}: ${selectedTarget}` : (isEn ? "No target yet" : "Chưa có mục tiêu"),
      isConfigured: Boolean(problemType),
    },
    {
      id: 4,
      icon: SlidersHorizontal,
      title: t("summary.params"),
      value: metricSort ? toTitleLabel(metricSort) : (isEn ? "No metric chosen" : "Chưa chọn metric"),
      detail: t("summary.featuresCount", { count: selectedFeatures.length }),
      isConfigured: Boolean(selectedTarget && selectedFeatures.length > 0 && metricSort),
    },
    {
      id: 5,
      icon: Rocket,
      title: isEn ? "Resources" : "Tài nguyên",
      value: "Auto (GPU/CPU)",
      detail: isEn ? "High-performance priority" : "Tự động tối ưu theo phần cứng",
      isConfigured: true,
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
    if (!selectedTarget) {
      toast({
        title: isEn ? "Missing Target" : "Thiếu thuộc tính mục tiêu",
        description: isEn ? "Please select a target column to predict." : "Vui lòng chọn một thuộc tính mục tiêu!",
        variant: "destructive",
      });
      return;
    }
    if (selectedFeatures.length === 0) {
      toast({
        title: isEn ? "Missing Features" : "Thiếu đặc trưng huấn luyện",
        description: isEn ? "Please select at least one feature." : "Vui lòng chọn ít nhất một thuộc tính huấn luyện!",
        variant: "destructive",
      });
      return;
    }
    if (!metricSort) {
      toast({
        title: isEn ? "Missing Metric" : "Thiếu chỉ số đánh giá",
        description: isEn ? "Please select an evaluation metric." : "Vui lòng chọn một chỉ số đánh giá!",
        variant: "destructive",
      });
      return;
    }

    router.push(resultHref);
  };

  // Smart Config Presets
  const applyPreset = (presetType: "fast" | "balanced" | "accuracy") => {
    setSelectedOption("new_model");
    setStorage("choose", "new_model");
    setMethod("auto");
    setStorage("method", "auto");

    if (!problemType) {
      setProblemType("classification");
      setStorage("problem_type", "classification");
    }

    if (featureNames.length > 0) {
      const recTarget = Object.entries(listFeature).find(([, isRec]) => isRec)?.[0] || featureNames[featureNames.length - 1];
      setSelectedTarget(recTarget);
      setStorage("target", recTarget);

      const otherFeatures = featureNames.filter((f) => f !== recTarget);
      if (presetType === "fast") {
        const topFeatures = otherFeatures.slice(0, Math.min(10, otherFeatures.length));
        setSelectedFeatures(topFeatures);
        setStorage("list_feature", JSON.stringify(topFeatures));
      } else {
        setSelectedFeatures(otherFeatures);
        setStorage("list_feature", JSON.stringify(otherFeatures));
      }
    }

    const targetMetric = problemType === "regression" ? "r2" : (presetType === "accuracy" ? "f1" : "accuracy");
    setMetricSort(targetMetric);
    setStorage("metric_sort", targetMetric);

    setIsAdvisorOpen(false);
    toast({
      title: isEn ? "Config Applied Successfully" : "Đã áp dụng cấu hình gợi ý",
      description:
        presetType === "fast"
          ? (isEn ? "Fast Baseline preset active." : "Đã kích hoạt cấu hình Huấn luyện Nhanh.")
          : presetType === "balanced"
            ? (isEn ? "Balanced Recommendation preset active." : "Đã kích hoạt cấu hình Cân bằng Khuyến nghị.")
            : (isEn ? "Maximum Accuracy Deep Search preset active." : "Đã kích hoạt cấu hình Tối đa Độ chính xác."),
    });
  };

  return (
    <div className="flex flex-col min-h-[calc(100svh-7.5rem)] w-full rounded-[2rem] bg-gradient-to-br from-slate-50 via-white to-slate-100/50 p-3 shadow-xs ring-1 ring-slate-200/80 dark:from-slate-950/60 dark:via-slate-900/40 dark:to-blue-950/20 dark:ring-white/10 lg:p-4">
      <div
        className={cn(
          "grid flex-1 min-h-0 gap-4 transition-[grid-template-columns] duration-300",
          summaryCollapsed ? "xl:grid-cols-[1fr_88px]" : "xl:grid-cols-[1fr_360px]",
        )}
      >
        {/* Main Wizard Area */}
        <main className="relative flex flex-col min-h-0 overflow-hidden rounded-[1.75rem] border border-slate-200/90 bg-white/95 p-4 shadow-sm backdrop-blur dark:border-white/10 dark:bg-[#0b1329]/80 lg:p-6">
          <div className="pointer-events-none absolute -left-16 top-16 h-48 w-48 rounded-full bg-blue-100/30 blur-3xl dark:bg-blue-500/10" />
          <div className="pointer-events-none absolute bottom-10 right-10 h-40 w-40 rounded-full bg-cyan-100/25 blur-3xl dark:bg-cyan-500/10" />

          {/* Top Header: Step Stepper + Action buttons */}
          <div className="relative z-10 flex flex-col gap-4 border-b border-slate-100 pb-4 dark:border-white/5">
            {/* Header Title & Advisor Trigger */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-automl-blue-soft text-xs font-black text-automl-blue">
                    {step}
                  </span>
                  <h1 className="text-base sm:text-lg font-black text-slate-900 dark:text-white">
                    {step === 1 && (isEn ? "Input Dataset & Model Mode" : "Bộ dữ liệu & Chế độ mô hình")}
                    {step === 2 && (isEn ? "AutoML Strategy Selection" : "Chiến lược tối ưu AutoML")}
                    {step === 3 && (isEn ? "Machine Learning Task Type" : "Xác định dạng bài toán")}
                    {step === 4 && (isEn ? "Target, Features & Evaluation Metric" : "Mục tiêu, Đặc trưng & Chỉ số đánh giá")}
                  </h1>
                </div>
                <p className="mt-1 text-xs sm:text-sm font-medium leading-relaxed text-slate-500 dark:text-slate-400">
                  {stepDescription}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  variant="outline"
                  onClick={() => setIsAdvisorOpen(true)}
                  className="h-10 rounded-2xl border-amber-300/80 bg-amber-50/70 text-xs sm:text-sm font-bold text-amber-900 shadow-xs hover:bg-amber-100 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-300 dark:hover:bg-amber-950/50"
                  type="button"
                >
                  <Lightbulb className="mr-1.5 h-4 w-4 fill-amber-500 text-amber-500 animate-pulse" />
                  <span>{t("suggestConfig")}</span>
                </Button>

                {/* Mobile summary trigger button */}
                <Button
                  variant="outline"
                  onClick={() => setIsMobileSummaryOpen(true)}
                  className="xl:hidden h-10 rounded-2xl border-slate-200 bg-white px-3 text-xs font-bold shadow-xs dark:border-white/10 dark:bg-white/5"
                  type="button"
                >
                  <ShieldCheck className="mr-1 h-4 w-4 text-automl-blue" />
                  <span>{t("summary.title")}</span>
                </Button>
              </div>
            </div>

            {/* Responsive Stepper Navigation */}
            <div className="mt-1">
              <ResponsiveStepNavigator
                currentStep={displayedStep}
                onStepClick={(targetStep) => {
                  if (targetStep < step) {
                    setStep(targetStep);
                  }
                }}
              />
            </div>
          </div>

          {/* Central Options Content Area */}
          <div className="relative z-10 flex-1 min-h-0 overflow-y-auto px-1 py-4 scrollbar-thin scroll-smooth overscroll-contain">
            {step === 1 && (
              <div className="space-y-4">
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
                      badgeVariant={option.badgeVariant}
                      tone={option.tone}
                      features={option.features}
                    />
                  ))}
                </RadioGroup>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-5">
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
                      badgeVariant={option.badgeVariant}
                      tone={option.tone}
                      features={option.features}
                    >
                      <div className="mt-4 space-y-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 dark:border-white/5 dark:bg-white/5">
                        <ProgressLine
                          label={t("strategyOptions.auto.setupTime")}
                          value={option.value === "auto" ? 95 : 35}
                        />
                        <ProgressLine
                          label={t("strategyOptions.auto.automationLevel")}
                          value={option.value === "auto" ? 98 : 40}
                        />
                      </div>
                    </ChoiceCard>
                  ))}
                </RadioGroup>

                {/* Auto Switch highlight banner */}
                <div className="flex items-center justify-between rounded-2xl border border-blue-200/80 bg-gradient-to-r from-blue-50/80 via-indigo-50/40 to-cyan-50/60 p-4 shadow-xs dark:border-blue-900/40 dark:from-blue-950/30 dark:to-cyan-950/20">
                  <div className="flex items-center gap-3.5">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-automl-blue text-white shadow-md shadow-blue-500/20">
                      <Sparkles className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-black text-slate-900 dark:text-white">
                        {t("strategyOptions.autoSwitchTitle")}
                      </p>
                      <p className="mt-0.5 text-xs font-semibold leading-relaxed text-slate-600 dark:text-slate-400">
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
              <div className="space-y-4">
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
                      badgeVariant={option.badgeVariant}
                      tone={option.tone}
                      features={option.features}
                    />
                  ))}
                </RadioGroup>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-5">
                {isFeaturesError ? (
                  <div className="rounded-3xl border border-red-200 bg-red-50 p-8 text-center font-semibold text-red-600 dark:border-red-900/40 dark:bg-red-950/30">
                    <p className="text-lg font-black">{featureErrorMessage}</p>
                    <p className="mt-2 text-sm text-red-500">
                      {isEn ? "Please return to select another dataset or retry." : "Vui lòng quay lại chọn bộ dữ liệu khác hoặc thử lại sau."}
                    </p>
                  </div>
                ) : (
                  <>
                    {(isFeaturesFetching || isMetricsFetching) && (
                      <div className="flex items-center justify-center gap-3 rounded-2xl bg-blue-50/80 p-5 text-center text-sm font-bold text-automl-blue dark:bg-blue-950/30 dark:text-cyan-300">
                        <Sparkles className="h-5 w-5 animate-spin" />
                        <span>{t("step4.loading")}</span>
                      </div>
                    )}

                    {!isFeaturesFetching && !isFeaturesError && featureNames.length === 0 && (
                      <div className="rounded-2xl border border-amber-300/60 bg-amber-50/70 p-6 text-center text-sm font-semibold text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300">
                        <p className="font-bold">
                          {isEn ? "No feature columns found in dataset." : "Không tìm thấy thuộc tính nào trong bộ dữ liệu."}
                        </p>
                        <p className="mt-1 text-xs text-amber-700/80 dark:text-amber-400">
                          {isEn ? "Please inspect your dataset schema or click retry." : "Vui lòng kiểm tra lại cấu trúc bộ dữ liệu hoặc bấm tải lại."}
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3 rounded-xl border-amber-300 bg-white hover:bg-amber-100 dark:border-amber-800 dark:bg-slate-900"
                          onClick={() => refetchFeatures()}
                        >
                          <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                          {isEn ? "Reload Features" : "Tải lại thuộc tính"}
                        </Button>
                      </div>
                    )}

                    {/* Step 4: 3 Well-structured Parameter Sections */}
                    <div className="space-y-6 py-1">
                      {/* Section 1: Target Attribute */}
                      <section className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-xs dark:border-white/10 dark:bg-slate-900/50">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3.5 border-b border-slate-100 dark:border-white/5">
                          <div className="flex items-center gap-2.5">
                            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-automl-blue-soft text-xs font-black text-automl-blue">
                              1
                            </span>
                            <div>
                              <h3 className="text-sm sm:text-base font-black text-slate-900 dark:text-white flex items-center gap-2">
                                <Target className="h-4 w-4 text-automl-blue" />
                                {t("step4.targetTitle")}
                              </h3>
                              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                                {t("step4.targetDesc")}
                              </p>
                            </div>
                          </div>
                          {selectedTarget && (
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-black text-automl-blue border border-blue-200/70 dark:border-blue-900/40 dark:bg-blue-950/40 dark:text-cyan-300">
                              {t("step4.selectedTarget")} <strong>{selectedTarget}</strong>
                            </span>
                          )}
                        </div>

                        <div className="mt-4 max-h-64 sm:max-h-72 overflow-y-auto overscroll-contain rounded-xl p-1.5 scrollbar-thin scroll-smooth">
                          <RadioGroup
                            value={selectedTarget}
                            onValueChange={handleTargetChange}
                            className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4"
                          >
                            {Object.entries(listFeature).map(([feature, recommended]) => (
                              <label
                                key={feature}
                                htmlFor={`target-${feature}`}
                                className={cn(
                                  "flex cursor-pointer items-center justify-between gap-2.5 rounded-xl border p-3 text-xs sm:text-sm font-bold transition",
                                  selectedTarget === feature
                                    ? "border-automl-blue bg-automl-blue-soft text-automl-blue shadow-xs ring-1 ring-automl-blue"
                                    : recommended
                                      ? "border-emerald-300 bg-emerald-50/70 text-emerald-800 hover:border-emerald-400 dark:border-emerald-700/50 dark:bg-emerald-950/30 dark:text-emerald-300"
                                      : "border-slate-200 bg-white text-slate-700 hover:border-automl-blue/50 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white/80 dark:hover:bg-white/10",
                                )}
                              >
                                <div className="min-w-0 flex items-center gap-1.5">
                                  <span className="truncate">{feature}</span>
                                  {recommended && (
                                    <span className="shrink-0 rounded-md bg-emerald-100 px-1.5 py-0.5 text-[10px] font-black text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300">
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

                      {/* Section 2: Input Features */}
                      <section className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-xs dark:border-white/10 dark:bg-slate-900/50">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3.5 border-b border-slate-100 dark:border-white/5">
                          <div className="flex items-center gap-2.5">
                            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-automl-blue-soft text-xs font-black text-automl-blue">
                              2
                            </span>
                            <div>
                              <h3 className="text-sm sm:text-base font-black text-slate-900 dark:text-white flex items-center gap-2">
                                <FileSpreadsheet className="h-4 w-4 text-automl-blue" />
                                {t("step4.featuresTitle")}
                              </h3>
                              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                                {t("step4.featuresDesc", {
                                  count: selectedFeatures.length,
                                  total: selectableFeatures.length,
                                })}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            {/* Feature quick search */}
                            {featureNames.length > 8 && (
                              <div className="relative">
                                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                                <input
                                  type="text"
                                  placeholder={isEn ? "Search columns..." : "Tìm cột..."}
                                  value={featureSearchQuery}
                                  onChange={(e) => setFeatureSearchQuery(e.target.value)}
                                  className="h-8 w-32 sm:w-40 rounded-xl border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs outline-none focus:border-automl-blue dark:border-white/10 dark:bg-white/5"
                                />
                              </div>
                            )}

                            <Button
                              variant="outline"
                              size="sm"
                              className="h-8 rounded-xl border-slate-200 bg-white px-3 text-xs font-bold shadow-none hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 shrink-0"
                              onClick={handleSelectAllFeatures}
                              type="button"
                            >
                              {isAllSelected ? (
                                <>
                                  <Square className="mr-1 h-3.5 w-3.5 text-slate-400" />
                                  {t("step4.deselectAll")}
                                </>
                              ) : (
                                <>
                                  <CheckSquare className="mr-1 h-3.5 w-3.5 text-automl-blue" />
                                  {t("step4.selectAll")}
                                </>
                              )}
                            </Button>
                          </div>
                        </div>

                        <div className="mt-4 max-h-72 sm:max-h-80 overflow-y-auto overscroll-contain rounded-xl p-1.5 scrollbar-thin scroll-smooth">
                          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
                            {filteredFeatures.map((feature) => {
                              const disabled = feature === selectedTarget;
                              const checked = selectedFeatures.includes(feature);

                              return (
                                <label
                                  key={feature}
                                  htmlFor={`feature-${feature}`}
                                  className={cn(
                                    "flex cursor-pointer items-center gap-2.5 rounded-xl border p-3 text-xs sm:text-sm font-bold transition",
                                    checked
                                      ? "border-automl-blue bg-automl-blue-soft text-automl-blue shadow-xs ring-1 ring-automl-blue/50"
                                      : "border-slate-200 bg-white text-slate-700 hover:border-automl-blue/50 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white/80 dark:hover:bg-white/10",
                                    disabled && "cursor-not-allowed opacity-40 bg-slate-100 dark:bg-white/5",
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

                      {/* Section 3: Evaluation Metric */}
                      <section className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-xs dark:border-white/10 dark:bg-slate-900/50">
                        <div className="flex items-center gap-2.5 pb-3.5 border-b border-slate-100 dark:border-white/5">
                          <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-automl-blue-soft text-xs font-black text-automl-blue">
                            3
                          </span>
                          <div>
                            <h3 className="text-sm sm:text-base font-black text-slate-900 dark:text-white flex items-center gap-2">
                              <Gauge className="h-4 w-4 text-automl-blue" />
                              {t("step4.metricTitle")}
                            </h3>
                            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                              {t("step4.metricDesc")}
                            </p>
                          </div>
                        </div>

                        <div className="mt-4 p-1">
                          <RadioGroup
                            value={metricSort}
                            onValueChange={handleMetricChange}
                            className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4"
                          >
                            {Object.entries(metrics).map(([metric, value]) => (
                              <label
                                key={metric}
                                htmlFor={`metric-${value}`}
                                className={cn(
                                  "flex cursor-pointer items-center justify-between gap-3 rounded-xl border p-3 text-xs sm:text-sm font-bold transition",
                                  metricSort === value
                                    ? "border-automl-blue bg-automl-blue-soft text-automl-blue shadow-xs ring-1 ring-automl-blue"
                                    : "border-slate-200 bg-white text-slate-700 hover:border-automl-blue/50 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-white/80 dark:hover:bg-white/10",
                                )}
                              >
                                <span className="font-extrabold">{toTitleLabel(value)}</span>
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

          {/* Bottom Navigation Actions Bar */}
          <div className="relative z-20 mt-3 shrink-0 border-t border-slate-100 bg-white/90 pt-3 backdrop-blur dark:border-white/10 dark:bg-slate-950/40">
            <div className="flex items-center justify-between gap-3">
              <Button
                variant="outline"
                onClick={handleBack}
                className="h-11 rounded-2xl border-slate-200 bg-white px-5 font-bold shadow-xs hover:bg-slate-50 dark:border-white/10 dark:bg-white/10"
                type="button"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                <span>{t("actions.back")}</span>
              </Button>

              <div className="flex items-center gap-2">
                {step < 4 ? (
                  <Button
                    onClick={handleNext}
                    disabled={
                      (step === 1 && !selectedOption) ||
                      (step === 2 && !method) ||
                      (step === 3 && !problemType)
                    }
                    className="h-11 rounded-2xl bg-automl-blue px-6 font-black text-white shadow-md shadow-blue-500/20 hover:bg-automl-blue-hover disabled:opacity-50"
                    type="button"
                  >
                    <span>{t("actions.continue")}</span>
                    <ChevronRight className="ml-1.5 h-4 w-4" />
                  </Button>
                ) : (
                  !isFeaturesError && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          disabled={!canStart}
                          className="h-11 rounded-2xl bg-gradient-to-r from-automl-blue to-cyan-600 px-6 font-black text-white shadow-md shadow-blue-500/20 hover:opacity-95 disabled:opacity-50"
                          type="button"
                        >
                          <span>{t("actions.confirmStart")}</span>
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

        {/* Right Sidebar: Summary & Parameters Deck (Desktop XL) */}
        <aside
          className={cn(
            "hidden xl:flex flex-col min-h-0 overflow-hidden rounded-[1.75rem] border border-slate-200/90 bg-white/95 shadow-sm backdrop-blur transition-all duration-300 dark:border-white/10 dark:bg-[#0b1329]/80",
            summaryCollapsed ? "p-3" : "p-5",
          )}
        >
          {/* Sidebar Header */}
          <div
            className={cn(
              "flex items-center justify-between gap-3 border-b border-slate-100 pb-3.5 dark:border-white/5",
              summaryCollapsed && "flex-col border-b-0 pb-0",
            )}
          >
            <div className={cn("flex items-center gap-3", summaryCollapsed && "flex-col")}>
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-automl-blue to-indigo-600 text-white shadow-md shadow-blue-500/20">
                <ShieldCheck className="h-5 w-5" />
              </div>
              {!summaryCollapsed && (
                <div>
                  <h2 className="text-base font-black text-slate-900 dark:text-white">
                    {t("summary.title")}
                  </h2>
                  <span className="text-[11px] font-bold text-automl-blue">
                    {isEn ? `Step ${displayedStep} of 5` : `Tiến trình: Bước ${displayedStep}/5`}
                  </span>
                </div>
              )}
            </div>
            <Button
              variant="outline"
              size="icon"
              className="h-9 w-9 rounded-xl border-slate-200 bg-white shadow-none hover:bg-slate-50 dark:border-white/10 dark:bg-white/10"
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

          {/* Sidebar Body */}
          {summaryCollapsed ? (
            <CollapsedSummary
              items={summaryItems}
              currentStep={displayedStep}
              onItemClick={(itemStep) => setStep(itemStep)}
            />
          ) : (
            <div className="flex flex-col flex-1 min-h-0 mt-3">
              {/* Tab Switcher: Summary vs Recommendations */}
              <div className="grid grid-cols-2 rounded-2xl border border-slate-200/80 bg-slate-100/70 p-1 text-xs font-black dark:border-white/10 dark:bg-white/5">
                <button
                  type="button"
                  onClick={() => setActiveSummaryTab("summary")}
                  className={cn(
                    "rounded-xl py-2 text-center transition shadow-xs",
                    activeSummaryTab === "summary"
                      ? "bg-white text-automl-blue shadow-sm dark:bg-slate-800 dark:text-white"
                      : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white",
                  )}
                >
                  {t("summary.tabSummary")}
                </button>
                <button
                  type="button"
                  onClick={() => setActiveSummaryTab("recommendations")}
                  className={cn(
                    "rounded-xl py-2 text-center transition",
                    activeSummaryTab === "recommendations"
                      ? "bg-white text-automl-blue shadow-sm dark:bg-slate-800 dark:text-white"
                      : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white",
                  )}
                >
                  {t("summary.tabParams")}
                </button>
              </div>

              {/* Tab Content */}
              <div className="flex-1 min-h-0 overflow-y-auto pr-1 mt-4 scrollbar-thin">
                {activeSummaryTab === "summary" ? (
                  <div className="space-y-3">
                    {summaryItems.map((item) => (
                      <SummaryCard
                        key={item.id}
                        item={item}
                        onJump={() => {
                          if (item.id <= 4) setStep(item.id);
                        }}
                      />
                    ))}
                  </div>
                ) : (
                  <RecommendationsPanel
                    onApplyPreset={applyPreset}
                    problemType={problemType}
                    isEn={isEn}
                  />
                )}
              </div>

              {/* Ready status pill at bottom of sidebar */}
              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-white/5">
                {canStart ? (
                  <div className="flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700 border border-emerald-200/80 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-800/40">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                    <span>{isEn ? "Ready for AutoML Training!" : "Cấu hình hợp lệ! Đã sẵn sàng."}</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-xs font-medium text-slate-500 dark:bg-white/5 dark:text-slate-400">
                    <Info className="h-4 w-4 shrink-0 text-slate-400" />
                    <span>{isEn ? "Complete all steps to proceed." : "Hoàn thiện các bước để tiếp tục."}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* Mobile Slide-over Sheet for Summary (< xl) */}
      <Sheet open={isMobileSummaryOpen} onOpenChange={setIsMobileSummaryOpen}>
        <SheetContent side="right" className="w-full sm:max-w-md p-6 flex flex-col">
          <SheetHeader className="border-b pb-3">
            <SheetTitle className="flex items-center gap-2.5 text-base font-black">
              <ShieldCheck className="h-5 w-5 text-automl-blue" />
              <span>{t("summary.title")}</span>
            </SheetTitle>
          </SheetHeader>

          <div className="grid grid-cols-2 rounded-2xl border border-slate-200/80 bg-slate-100/70 p-1 text-xs font-black my-4 dark:border-white/10 dark:bg-white/5">
            <button
              type="button"
              onClick={() => setActiveSummaryTab("summary")}
              className={cn(
                "rounded-xl py-2 text-center transition",
                activeSummaryTab === "summary"
                  ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-white"
                  : "text-slate-500",
              )}
            >
              {t("summary.tabSummary")}
            </button>
            <button
              type="button"
              onClick={() => setActiveSummaryTab("recommendations")}
              className={cn(
                "rounded-xl py-2 text-center transition",
                activeSummaryTab === "recommendations"
                  ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-white"
                  : "text-slate-500",
              )}
            >
              {t("summary.tabParams")}
            </button>
          </div>

          <div className="flex-1 overflow-y-auto pr-1 scrollbar-thin">
            {activeSummaryTab === "summary" ? (
              <div className="space-y-3">
                {summaryItems.map((item) => (
                  <SummaryCard
                    key={item.id}
                    item={item}
                    onJump={() => {
                      if (item.id <= 4) {
                        setStep(item.id);
                        setIsMobileSummaryOpen(false);
                      }
                    }}
                  />
                ))}
              </div>
            ) : (
              <RecommendationsPanel
                onApplyPreset={(p) => {
                  applyPreset(p);
                  setIsMobileSummaryOpen(false);
                }}
                problemType={problemType}
                isEn={isEn}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>

      {/* Smart Config Advisor Dialog (Gợi ý cấu hình thông minh) */}
      <Dialog open={isAdvisorOpen} onOpenChange={setIsAdvisorOpen}>
        <DialogContent className="max-w-2xl rounded-3xl p-6">
          <DialogHeader className="border-b pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
                <Lightbulb className="h-6 w-6 fill-amber-400" />
              </div>
              <div>
                <DialogTitle className="text-xl font-black text-slate-900 dark:text-white">
                  {isEn ? "HAutoML Smart Config Advisor" : "Gợi ý cấu hình AutoML thông minh"}
                </DialogTitle>
                <DialogDescription className="mt-1 text-xs sm:text-sm">
                  {isEn
                    ? "Select a pre-tuned profile to instantly configure hyperparameters for this dataset."
                    : "Lựa chọn cấu hình tối ưu phù hợp với bài toán của bạn chỉ với 1 lượt bấm."}
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="grid gap-3.5 py-4 sm:grid-cols-3">
            {/* Preset 1: Fast Baseline */}
            <div className="flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs transition hover:border-automl-blue hover:shadow-md dark:border-white/10 dark:bg-white/5">
              <div>
                <div className="flex items-center justify-between">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-950/40">
                    <Zap className="h-5 w-5" />
                  </span>
                  <span className="rounded-md bg-amber-100 px-2 py-0.5 text-[10px] font-black text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                    {isEn ? "Fast" : "Nhanh"}
                  </span>
                </div>
                <h4 className="mt-3 text-sm font-black text-slate-900 dark:text-white">
                  {isEn ? "Fast Baseline" : "Thử nghiệm nhanh"}
                </h4>
                <p className="mt-1 text-xs text-slate-500 leading-relaxed dark:text-slate-400">
                  {isEn
                    ? "Ideal for fast prototyping. Selects top features with minimal training time."
                    : "Kiểm thử giả định nhanh. Rút ngắn thời gian huấn luyện với các đặc trưng quan trọng nhất."}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => applyPreset("fast")}
                className="mt-4 w-full rounded-xl border-amber-300 font-bold text-amber-900 hover:bg-amber-50 dark:border-amber-800 dark:text-amber-300"
              >
                {isEn ? "Apply Fast" : "Áp dụng"}
              </Button>
            </div>

            {/* Preset 2: Balanced (Recommended) */}
            <div className="flex flex-col justify-between rounded-2xl border-2 border-automl-blue bg-blue-50/40 p-4 shadow-md shadow-blue-500/10 dark:bg-blue-950/20">
              <div>
                <div className="flex items-center justify-between">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-automl-blue text-white shadow-xs">
                    <Sparkles className="h-5 w-5" />
                  </span>
                  <span className="rounded-md bg-automl-blue px-2 py-0.5 text-[10px] font-black text-white">
                    {isEn ? "Recommended" : "Khuyến nghị"}
                  </span>
                </div>
                <h4 className="mt-3 text-sm font-black text-slate-900 dark:text-white">
                  {isEn ? "Balanced Profile" : "Cân bằng tối ưu"}
                </h4>
                <p className="mt-1 text-xs text-slate-600 leading-relaxed dark:text-slate-300">
                  {isEn
                    ? "Optimal trade-off between speed & precision. Evaluates full feature space."
                    : "Cân bằng hoàn hảo giữa độ chính xác và tài nguyên. Giữ nguyên toàn bộ thuộc tính chuẩn hóa."}
                </p>
              </div>
              <Button
                size="sm"
                onClick={() => applyPreset("balanced")}
                className="mt-4 w-full rounded-xl bg-automl-blue font-black text-white shadow-xs hover:bg-automl-blue-hover"
              >
                {isEn ? "Apply Balanced" : "Áp dụng khuyến nghị"}
              </Button>
            </div>

            {/* Preset 3: High Accuracy */}
            <div className="flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs transition hover:border-automl-blue hover:shadow-md dark:border-white/10 dark:bg-white/5">
              <div>
                <div className="flex items-center justify-between">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40">
                    <TrendingUp className="h-5 w-5" />
                  </span>
                  <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-[10px] font-black text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                    {isEn ? "Max" : "Tối đa"}
                  </span>
                </div>
                <h4 className="mt-3 text-sm font-black text-slate-900 dark:text-white">
                  {isEn ? "Deep Search" : "Độ chính xác cao"}
                </h4>
                <p className="mt-1 text-xs text-slate-500 leading-relaxed dark:text-slate-400">
                  {isEn
                    ? "Deep hyperparameter exploration & stacked ensemble for highest benchmark metrics."
                    : "Thử nghiệm sâu các mô hình ensemble. Tối đa hóa chỉ số mục tiêu cho môi trường sản xuất."}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => applyPreset("accuracy")}
                className="mt-4 w-full rounded-xl border-emerald-300 font-bold text-emerald-800 hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-300"
              >
                {isEn ? "Apply Deep" : "Áp dụng"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Subcomponent: ChoiceCard (Clean, Spacious, Informative)
const ChoiceCard = ({
  id,
  title,
  description,
  icon: Icon,
  selected,
  disabled,
  badge,
  badgeVariant = "primary",
  tone,
  features,
  children,
}: ChoiceCardProps) => (
  <label
    htmlFor={id}
    className={cn(
      "group relative flex min-h-[220px] cursor-pointer flex-col justify-between rounded-3xl border bg-white p-5 sm:p-6 transition-all duration-200 dark:bg-[#0f172a]/70",
      selected
        ? "border-automl-blue bg-blue-50/30 shadow-xl shadow-blue-500/10 ring-2 ring-automl-blue dark:border-automl-blue dark:bg-blue-950/30"
        : "border-slate-200/90 hover:-translate-y-0.5 hover:border-automl-blue/50 hover:shadow-lg hover:shadow-slate-900/5 dark:border-white/10 dark:hover:border-automl-blue/40",
      disabled && "cursor-not-allowed opacity-50 hover:translate-y-0 hover:border-slate-200 hover:shadow-none",
    )}
  >
    <RadioGroupItem id={id} value={id} disabled={disabled} className="sr-only" />

    {/* Top Row: Icon + Badge + Radio Indicator */}
    <div className="flex items-start justify-between gap-3">
      <div className={cn("flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl shadow-xs transition-transform duration-200 group-hover:scale-105", tone)}>
        <Icon className="h-7 w-7" />
      </div>

      <div className="flex items-center gap-2">
        {badge && (
          <span
            className={cn(
              "rounded-full px-3 py-1 text-xs font-black",
              badgeVariant === "primary" && "bg-automl-blue-soft text-automl-blue dark:bg-blue-500/10 dark:text-cyan-300",
              badgeVariant === "warning" && "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300",
              badgeVariant === "muted" && "bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-white/60",
            )}
          >
            {badge}
          </span>
        )}

        <div
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded-full border transition-all",
            selected
              ? "border-automl-blue bg-automl-blue text-white shadow-xs"
              : "border-slate-300 bg-white dark:border-white/20 dark:bg-transparent",
          )}
        >
          {selected && <Check className="h-3.5 w-3.5 stroke-[3]" />}
        </div>
      </div>
    </div>

    {/* Middle Content */}
    <div className="mt-4 flex-1">
      <h3 className="text-base sm:text-lg font-black text-slate-900 transition-colors group-hover:text-automl-blue dark:text-white dark:group-hover:text-cyan-300">
        {title}
      </h3>
      <p className="mt-1 text-xs sm:text-sm font-medium leading-relaxed text-slate-500 dark:text-slate-400">
        {description}
      </p>

      {/* Feature Bullet Points */}
      {features && features.length > 0 && (
        <ul className="mt-3.5 space-y-2 border-t border-slate-100 pt-3 dark:border-white/5">
          {features.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-xs font-semibold text-slate-600 dark:text-slate-300">
              <Check className="h-3.5 w-3.5 mt-0.5 shrink-0 text-emerald-500" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>

    {children}
  </label>
);

// Subcomponent: Progress Line
const ProgressLine = ({ label, value }: { label: string; value: number }) => (
  <div>
    <div className="mb-1 flex justify-between text-xs font-bold text-slate-600 dark:text-slate-300">
      <span>{label}</span>
      <span className="text-automl-blue">{value}%</span>
    </div>
    <div className="h-2 rounded-full bg-slate-200/80 dark:bg-white/10 overflow-hidden">
      <div
        className="h-full rounded-full bg-gradient-to-r from-automl-blue to-cyan-500 transition-all duration-500"
        style={{ width: `${value}%` }}
      />
    </div>
  </div>
);

// Subcomponent: Responsive Step Navigator Bar
const ResponsiveStepNavigator = ({
  currentStep,
  onStepClick,
}: {
  currentStep: number;
  onStepClick: (stepId: number) => void;
}) => {
  const t = useTranslations("TrainingWizard.steps");

  return (
    <div className="flex items-center justify-between gap-1 sm:gap-2 overflow-x-auto py-1 scrollbar-none">
      {steps.map((item, index) => {
        const isDone = item.id < currentStep;
        const isActive = item.id === currentStep;

        return (
          <div key={item.id} className="flex items-center flex-1 min-w-[70px] sm:min-w-[120px]">
            <button
              type="button"
              disabled={!isDone}
              onClick={() => onStepClick(item.id)}
              className={cn(
                "flex items-center gap-2 rounded-xl px-2.5 py-1.5 transition-all text-xs font-extrabold w-full justify-start",
                isActive
                  ? "bg-automl-blue-soft text-automl-blue ring-1 ring-automl-blue/30 dark:bg-blue-500/10 dark:text-cyan-300"
                  : isDone
                    ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100 cursor-pointer dark:bg-emerald-950/30 dark:text-emerald-300"
                    : "text-slate-400 dark:text-slate-600 cursor-default",
              )}
            >
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-[11px] font-black transition",
                  isActive
                    ? "bg-automl-blue text-white shadow-xs"
                    : isDone
                      ? "bg-emerald-500 text-white"
                      : "bg-slate-200 text-slate-500 dark:bg-white/10 dark:text-white/40",
                )}
              >
                {isDone ? <Check className="h-3.5 w-3.5 stroke-[3]" /> : item.id}
              </span>
              <span className="hidden sm:inline truncate">{t(item.labelKey)}</span>
            </button>

            {index < steps.length - 1 && (
              <span
                className={cn(
                  "mx-1 h-0.5 w-3 sm:w-6 shrink-0 rounded-full",
                  isDone ? "bg-emerald-400" : "bg-slate-200 dark:bg-white/10",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};

// Subcomponent: Summary Card
const SummaryCard = ({
  item,
  onJump,
}: {
  item: SummaryConfig;
  onJump: () => void;
}) => {
  const Icon = item.icon;

  return (
    <div
      onClick={onJump}
      className="group flex cursor-pointer items-start justify-between gap-3 rounded-2xl border border-slate-200/80 bg-white p-3.5 shadow-xs transition hover:border-automl-blue/50 hover:bg-blue-50/20 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10"
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-automl-blue group-hover:bg-automl-blue-soft transition dark:bg-white/10 dark:text-cyan-300">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 dark:text-slate-500">
              {item.title}
            </span>
            {item.isConfigured ? (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                <Check className="h-2.5 w-2.5" />
              </span>
            ) : (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-white/10">
                Chờ chọn
              </span>
            )}
          </div>
          <p className="mt-0.5 truncate text-xs sm:text-sm font-black text-slate-900 group-hover:text-automl-blue transition dark:text-white dark:group-hover:text-cyan-300">
            {item.value}
          </p>
          <p className="truncate text-xs font-medium text-slate-500 dark:text-slate-400">
            {item.detail}
          </p>
        </div>
      </div>
    </div>
  );
};

// Subcomponent: Recommendations Panel
const RecommendationsPanel = ({
  onApplyPreset,
  problemType,
  isEn,
}: {
  onApplyPreset: (p: "fast" | "balanced" | "accuracy") => void;
  problemType: string;
  isEn: boolean;
}) => (
  <div className="space-y-3.5">
    <div className="rounded-2xl border border-blue-200/80 bg-blue-50/50 p-3.5 dark:border-blue-900/40 dark:bg-blue-950/20">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-automl-blue" />
        <span className="text-xs font-black text-slate-900 dark:text-white">
          {isEn ? "Smart Recommendations" : "Gợi ý tối ưu từ HAutoML"}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-600 leading-relaxed dark:text-slate-300">
        {problemType === "regression"
          ? (isEn
              ? "Recommended metric for continuous target is R² Score (Coefficient of determination)."
              : "Với bài toán hồi quy, chỉ số R² Score được khuyến nghị để tối ưu tổng thể.")
          : (isEn
              ? "For imbalanced classification datasets, F1-Score or ROC-AUC is recommended."
              : "Nếu dữ liệu mất cân bằng nhãn, khuyến nghị chọn F1-Score hoặc ROC-AUC thay cho Accuracy.")}
      </p>
    </div>

    <div className="space-y-2">
      <Button
        variant="outline"
        size="sm"
        onClick={() => onApplyPreset("balanced")}
        className="w-full justify-start rounded-xl border-automl-blue/50 text-xs font-bold text-automl-blue hover:bg-automl-blue-soft"
      >
        <Sparkles className="mr-2 h-3.5 w-3.5" />
        {isEn ? "Apply Balanced Recommendation" : "Áp dụng cấu hình Khuyến nghị"}
      </Button>

      <Button
        variant="outline"
        size="sm"
        onClick={() => onApplyPreset("fast")}
        className="w-full justify-start rounded-xl border-amber-300/80 text-xs font-bold text-amber-900 hover:bg-amber-50 dark:text-amber-300"
      >
        <Zap className="mr-2 h-3.5 w-3.5 text-amber-600" />
        {isEn ? "Apply Fast Baseline" : "Áp dụng cấu hình Nhanh"}
      </Button>
    </div>
  </div>
);

// Subcomponent: Collapsed Summary Rail
const CollapsedSummary = ({
  items,
  currentStep,
  onItemClick,
}: {
  items: SummaryConfig[];
  currentStep: number;
  onItemClick: (s: number) => void;
}) => (
  <div className="mt-5 flex flex-col items-center gap-3">
    {items.map((item) => {
      const Icon = item.icon;
      const active = item.id <= currentStep;

      return (
        <button
          key={item.id}
          type="button"
          onClick={() => onItemClick(item.id)}
          title={`${item.title}: ${item.value}`}
          className={cn(
            "relative flex h-12 w-12 items-center justify-center rounded-2xl border transition-all",
            active
              ? "border-automl-blue/40 bg-automl-blue-soft text-automl-blue shadow-xs"
              : "border-slate-200 bg-slate-50 text-slate-400 dark:border-white/10 dark:bg-white/5",
          )}
        >
          <Icon className="h-5 w-5" />
          {item.isConfigured && (
            <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-slate-950" />
          )}
        </button>
      );
    })}
  </div>
);
