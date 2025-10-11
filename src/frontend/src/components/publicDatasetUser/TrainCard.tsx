"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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

import StepModel from "./StepChooseModel";

interface TrainCardProps {
  datasetID?: string;
  datasetName: string;
}

const TrainCard = ({ datasetID, datasetName }: TrainCardProps) => {
  const router = useRouter();

  const [step, setStep] = useState(1);
  const [selectedOption, setSelectedOption] = useState("");
  const [method, setMethod] = useState("");

  const [listFeature, setListFeature] = useState<string[]>([]);
  const [selectedTarget, setSelectedTarget] = useState("");
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);

  const [isLoading, setIsLoading] = useState(false);

  // 31. Lấy dữ liệu dataset theo datasetID chọn
  useEffect(() => {
    if (step === 3 && datasetID) {
      fetch(
        `${process.env.NEXT_PUBLIC_BASE_API}/v2/auto/features?id_data=${datasetID}`,
        {
          method: "GET",
          headers: { accept: "application/json" },
        }
      )
        .then((res) => res.json())
        .then(({ features }) => {
          setListFeature(features);
        })
        .catch((err) => {
          console.error("Lỗi khi gọi API:", err);
          alert("Không thể tải dữ liệu huấn luyện.");
        });
    }
  }, [step, datasetID]);

  const handleNext = () => {
    if (step === 1) {
      sessionStorage.setItem("choose", selectedOption);
      setStep(2);
    } else if (step === 2 && method) {
      sessionStorage.setItem("method", method);
      setStep(3);
    }
  };

  const handleBack = () => {
    if (step === 1) {
      router.push("/public-datasets");
    } else {
      setStep((prev) => prev - 1);
    }
  };

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

    setIsLoading(true);

    setTimeout(() => {
      router.push(`/public-datasets/${datasetID}/result`);
    }, 100);
  };

  return (
    <Card className="max-w-3xl mx-auto mt-10 p-6 shadow-lg rounded-xl dark:bg-[#171717]">
      <CardHeader className="text-center text-xl font-semibold text-[#3b6cf5]">
        Huấn luyện cho bộ dữ liệu: {datasetName}
      </CardHeader>

      <CardContent>
        {step === 1 && (
          <StepModel
            title="Chọn mô hình huấn luyện:"
            options={[
              { value: "new_model", label: "Mô hình mới" },
              { value: "new_version", label: "Version mới", disabled: true },
            ]}
            value={selectedOption}
            onChange={(val) => {
              console.log("Giá trị được chọn:", val);
              setSelectedOption(val);
              sessionStorage.setItem("choose", val);
            }}
            onBack={handleBack}
            onNext={handleNext}
            nextDisabled={!selectedOption}
          />
        )}

        {step === 2 && (
          <StepModel
            title="Chọn phương thức huấn luyện:"
            options={[
              { value: "auto", label: "Auto" },
              { value: "custom", label: "Custom", disabled: true },
            ]}
            value={method}
            onChange={(val) => {
              console.log("Giá trị được chọn:", val);
              setMethod(val);
              sessionStorage.setItem("method", val);
            }}
            onBack={handleBack}
            onNext={handleNext}
            nextDisabled={!selectedOption}
          />
        )}

        {step === 3 && (
          <div className="space-y-6 mt-6">
            {/* Thuộc tính mục tiêu */}
            <div>
              <Label className="block font-medium text-gray-700 mb-2 dark:text-white">
                Thuộc tính mục tiêu:
              </Label>
              <RadioGroup
                value={selectedTarget}
                onValueChange={handleTargetChange}
                className="grid grid-cols-2 gap-4"
              >
                {listFeature.map((feature) => (
                  <div
                    key={feature}
                    className="flex items-center p-4 border rounded-lg cursor-pointer hover:shadow data-[state=checked]:border-primary data-[state=checked]:bg-primary/10"
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
            </div>

            {/* Thuộc tính đưa vào huấn luyện */}
            <div>
              <Label className="block font-medium text-gray-700 mb-2 dark:text-white">
                Thuộc tính đưa vào huấn luyện:
              </Label>
              <div className="grid grid-cols-2 gap-3">
                {listFeature.map((feature) => (
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
            </div>

            {/* Chỉ số đánh giá */}
            <div>
              <Label className="block font-medium text-gray-700 mb-2 dark:text-white">
                Chỉ số đánh giá:
              </Label>
              <RadioGroup
                defaultValue={sessionStorage.getItem("metric_sort") || ""}
                onValueChange={(val) => {
                  sessionStorage.setItem("metric_sort", val);
                }}
                className="grid grid-cols-2 gap-4"
              >
                {["accuracy", "precision", "recall", "f1"].map((metric) => (
                  <div
                    key={metric}
                    className="flex items-center p-4 border rounded-lg cursor-pointer hover:shadow data-[state=checked]:border-primary data-[state=checked]:bg-primary/10"
                  >
                    <RadioGroupItem
                      id={metric}
                      value={metric}
                      className="mr-3"
                    />
                    <Label htmlFor={metric}>
                      {metric.charAt(0).toUpperCase() + metric.slice(1)}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>

            {/* Confirm Dialog */}
            <div className="flex justify-between mt-6">
              <Button variant="secondary" onClick={handleBack}>
                Quay lại
              </Button>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button className="bg-[#3a6df4] text-white dark:hover:bg-[#2f5ed6]">
                    Bắt đầu huấn luyện
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent className="dark:bg-[#171717]">
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
                      className="bg-[#3a6df4] text-white dark:hover:bg-[#2f5ed6]"
                    >
                      Đồng ý
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TrainCard;
