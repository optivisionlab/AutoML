"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useSession } from "next-auth/react";
import { useApi } from "@/hooks/useApi";
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
  AlertDialogDescription,
} from "@/components/ui/alert-dialog";

import { ScrollArea } from "@/components/ui/scroll-area";
import toTitleLabel from "@/utils/toTitleLable";
import { cn } from "@/lib/utils";

interface TrainMyDataCardProps {
  datasetID?: string;
  datasetName: string;
}

const TrainMyDataCard = ({ datasetID, datasetName }: TrainMyDataCardProps) => {
  const router = useRouter();
  const { get } = useApi();
  const { data: session } = useSession();

  const [step, setStep] = useState(1);
  const [selectedOption, setSelectedOption] = useState("new_model");
  const [method, setMethod] = useState("");
  const [problemType, setProblemType] = useState("");

  type FeatureMap = Record<string, boolean>;
  const [listFeature, setListFeature] = useState<FeatureMap>({});
  const [apiError, setApiError] = useState<string | null>(null);

  const [selectedTarget, setSelectedTarget] = useState("");
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [metrics, setMetrics] = useState<Record<string, string>>({});

  const getMetrics = useCallback(async (type: string) => {
    if (!type) return;
    try {
      const data = await get(`/v2/auto/metrics?problem_type=${type}`);
      setMetrics(data.metrics);
    } catch (err) {
      console.error("Lỗi khi gọi API metrics:", err);
    }
  }, [get]);

  useEffect(() => {
    if (step === 4 && datasetID && problemType) {
      get(`/v2/auto/features?id_data=${datasetID}&problem_type=${problemType}`)
        .then((data) => {
          if (data && data.features) {
            setListFeature(data.features);
          } else {
            setListFeature({});
            setApiError("Không tìm thấy bộ dữ liệu.");
          }
        })
        .catch((err) => {
          console.error("Lỗi khi gọi API features:", err);
          setListFeature({});
          setApiError("Không tìm thấy bộ dữ liệu.");
        });

      getMetrics(problemType);
    }
  }, [step, datasetID, problemType]);

  const handleNext = () => {
    if (step === 1) {
      sessionStorage.setItem("choose", selectedOption);
      setStep(2);
    } else if (step === 2 && method) {
      sessionStorage.setItem("method", method);
      setStep(3);
    } else if (step === 3 && problemType) {
      sessionStorage.setItem("problem_type", problemType);
      setStep(4);
    }
  };

  const handleBack = () => {
    if (step === 1) {
      if (session?.user?.role === "admin") {
        router.push("/admin/datasets/users");
      } else {
        router.push("/my-datasets");
      }
    } else {
      setStep((prev) => prev - 1);
    }
  };

  // Chọn tất cả thuộc tính
  const selectableFeatures = Object.keys(listFeature || {}).filter((f) => f !== selectedTarget);
  const isAllSelected = selectableFeatures.length > 0 && selectableFeatures.every((f) => selectedFeatures.includes(f));

  const handleSelectAllFeatures = () => {
    const updated = isAllSelected ? [] : selectableFeatures;
    setSelectedFeatures(updated);
    sessionStorage.setItem("list_feature", JSON.stringify(updated));
  };

  // Xử lý chọn/bỏ chọn tất cả thuộc tính
  const handleTargetChange = (value: string) => {
    setSelectedTarget(value);
    sessionStorage.setItem("target", value);

    const newFeatures = selectedFeatures.filter((f) => f !== value);
    setSelectedFeatures(newFeatures);
    sessionStorage.setItem("list_feature", JSON.stringify(newFeatures));
  };

  const handleFeatureToggle = (feature: string, checked: boolean) => {
    const updated = checked
      ? [...selectedFeatures, feature]
      : selectedFeatures.filter((f) => f !== feature);

    setSelectedFeatures(updated);
    sessionStorage.setItem("list_feature", JSON.stringify(updated));
  };

  const handleStartTraining = () => {
    if (!selectedTarget) return alert("Vui lòng chọn một thuộc tính mục tiêu!");
    if (selectedFeatures.length === 0) return alert("Vui lòng chọn ít nhất một thuộc tính huấn luyện!");
    if (!sessionStorage.getItem("metric_sort")) return alert("Vui lòng chọn một chỉ số đánh giá!");

    router.push(`/my-datasets/${datasetID}/result`);
  };

  return (
    <Card className="max-w-5xl mx-auto mt-10 p-6 shadow-lg rounded-xl">
      <CardHeader className="text-center text-xl font-semibold text-[#3b6cf5]">
        Huấn luyện cho bộ dữ liệu: {datasetName}
      </CardHeader>

      <CardContent>
        {step === 1 && (
          <div className="space-y-6 mt-6">
            <Label className="text-base font-medium">
              Chọn mô hình huấn luyện:
            </Label>
            <RadioGroup
              value={selectedOption}
              onValueChange={(val) => {
                setSelectedOption(val);
                sessionStorage.setItem("choose", val);
              }}
              className="grid grid-cols-2 gap-4"
            >
              {[
                { value: "new_model", label: "Mô hình mới" },
                { value: "new_version", label: "Version mới", disabled: true },
              ].map(({ value, label, disabled }) => (
                <div
                  key={value}
                  className="flex items-center p-4 border rounded-lg cursor-pointer hover:shadow data-[state=checked]:border-primary data-[state=checked]:bg-primary/10"
                >
                  <RadioGroupItem
                    id={value}
                    value={value}
                    disabled={disabled}
                    className="mr-3"
                  />
                  <Label htmlFor={value}>{label}</Label>
                </div>
              ))}
            </RadioGroup>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={handleBack}>
                Quay lại
              </Button>
              <Button onClick={handleNext} className="bg-[#3a6df4] text-white">
                Tiếp theo
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-6 mt-6">
            <Label className="text-base font-medium">
              Chọn phương thức huấn luyện:
            </Label>
            <RadioGroup
              value={method}
              onValueChange={(val) => {
                setMethod(val);
                sessionStorage.setItem("method", val);
              }}
              className="grid grid-cols-2 gap-4"
            >
              {[
                { value: "auto", label: "Auto" },
                { value: "custom", label: "Custom", disabled: true },
              ].map(({ value, label, disabled }) => (
                <div
                  key={value}
                  className="flex items-center p-4 border rounded-lg cursor-pointer hover:shadow data-[state=checked]:border-primary data-[state=checked]:bg-primary/10"
                >
                  <RadioGroupItem
                    id={value}
                    value={value}
                    disabled={disabled}
                    className="mr-3"
                  />
                  <Label htmlFor={value}>{label}</Label>
                </div>
              ))}
            </RadioGroup>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={handleBack}>
                Quay lại
              </Button>
              <Button
                onClick={handleNext}
                disabled={!method}
                className="bg-[#3a6df4] text-white disabled:opacity-50"
              >
                Tiếp theo
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6 mt-6">
            <Label className="text-base font-medium">
              Chọn loại bài toán huấn luyện:
            </Label>
            <RadioGroup
              value={problemType}
              onValueChange={(val) => {
                setProblemType(val);
                sessionStorage.setItem("problem_type", val);
              }}
              className="grid grid-cols-2 gap-4"
            >
              {[
                { value: "classification", label: "Classification" },
                { value: "regression", label: "Regression" },
              ].map(({ value, label }) => (
                <div
                  key={value}
                  className="flex items-center p-4 border rounded-lg cursor-pointer hover:shadow data-[state=checked]:border-primary data-[state=checked]:bg-primary/10"
                >
                  <RadioGroupItem
                    id={value}
                    value={value}
                    // disabled={disabled}
                    className="mr-3"
                  />
                  <Label htmlFor={value}>{label}</Label>
                </div>
              ))}
            </RadioGroup>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={handleBack}>
                Quay lại
              </Button>
              <Button
                onClick={handleNext}
                disabled={!problemType}
                className="bg-[#3a6df4] text-white disabled:opacity-50"
              >
                Tiếp theo
              </Button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-6 mt-6">
            {apiError ? (
              <div className="flex flex-col items-center justify-center py-10 text-red-500 font-medium bg-red-50 rounded-lg border border-red-200">
                <p className="text-lg">{apiError}</p>
                <p className="text-sm mt-2 text-red-400">Vui lòng chọn bộ dữ liệu khác.</p>
              </div>
            ) : (
              <>
                <div>
                  <Label className="block font-medium text-gray-700 mb-2">
                    Thuộc tính mục tiêu:
                  </Label>
                  <div className="text-sm text-center my-10">
                    Các ô được tô màu biểu thị các đặc trưng phù hợp với loại bài
                    toán đã chọn
                  </div>
                  <ScrollArea className="w-full h-80 border rounded-md p-3 scroll-bar">
                    <RadioGroup
                      value={selectedTarget}
                      onValueChange={handleTargetChange}
                      className="grid grid-cols-4 gap-4"
                    >
                      {Object.entries(listFeature).map(([feature, value]) => (
                        <div
                          key={feature}
                          className={cn(
                            "flex items-center p-4 border rounded-lg cursor-pointer transition-all duration-200",
                            value
                              ? "border-emerald-500 bg-emerald-50 shadow-sm"
                              : "border-border hover:border-emerald-300",
                          )}
                        >
                          <RadioGroupItem
                            id={feature}
                            value={feature}
                            className="mr-3"
                          />
                          <Label htmlFor={feature}>{feature}</Label>
                        </div>
                      ))}
                    </RadioGroup>
                  </ScrollArea>
                </div>

                <div>
                  <Label className="block font-medium text-gray-700 mb-2">
                    Thuộc tính đưa vào huấn luyện:
                  </Label>

                  <Button
                    variant={isAllSelected ? "secondary" : "default"}
                    className="mb-5"
                    onClick={handleSelectAllFeatures}
                  >
                    {isAllSelected ? "Bỏ chọn tất cả" : "Chọn tất cả"}
                  </Button>

                  <ScrollArea className="w-full h-80 border rounded-md p-3 scroll-bar">
                    <div className="grid grid-cols-4 gap-3">
                      {Object.keys(listFeature).map((feature) => (
                        <div key={feature} className="flex items-center gap-2">
                          <Checkbox
                            id={`feature-${feature}`}
                            checked={selectedFeatures.includes(feature)}
                            disabled={feature === selectedTarget}
                            onCheckedChange={(checked) =>
                              handleFeatureToggle(feature, !!checked)
                            }
                          />
                          <Label htmlFor={`feature-${feature}`}>{feature}</Label>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </div>

                {/* Chỉ số đánh giá */}
                <div>
                  <Label className="block font-medium text-gray-700 mb-2">
                    Chỉ số đánh giá:
                  </Label>
                  <RadioGroup
                    defaultValue={sessionStorage.getItem("metric_sort") || ""}
                    onValueChange={(val) => {
                      sessionStorage.setItem("metric_sort", val);
                    }}
                    className="grid grid-cols-2 gap-4"
                  >
                    {Object.entries(metrics).map(([metric, value]) => (
                      <div
                        key={metric}
                        className="flex items-center p-4 border rounded-lg cursor-pointer hover:shadow"
                      >
                        <RadioGroupItem id={value} value={value} className="mr-3" />
                        <Label htmlFor={metric}>
                          <span className="ml-2 text-sm">
                            {toTitleLabel(value)}
                          </span>
                        </Label>
                      </div>
                    ))}
                  </RadioGroup>
                </div>
              </>
            )}

            <div className="flex justify-between mt-6">
              <Button variant="secondary" onClick={handleBack}>
                Quay lại
              </Button>
              {!apiError && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button className="bg-[#3a6df4] text-white">
                      Bắt đầu huấn luyện
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Xác nhận huấn luyện</AlertDialogTitle>
                      <AlertDialogDescription>
                        Bạn có chắc chắn muốn bắt đầu huấn luyện mô hình với cấu
                        hình đã chọn không?
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Hủy</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleStartTraining}
                        className="bg-[#3a6df4] text-white"
                      >
                        Đồng ý
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TrainMyDataCard;
