"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useSession } from "next-auth/react";
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

interface TrainMyDataCardProps {
  datasetID?: string;
  datasetName: string;
}

const TrainMyDataCard = ({ datasetID, datasetName }: TrainMyDataCardProps) => {
  const router = useRouter();

  const [step, setStep] = useState(1);
  const [selectedOption, setSelectedOption] = useState("new-model");
  const [method, setMethod] = useState("");
  const [listFeature, setListFeature] = useState<string[]>([]);
  const [selectedTarget, setSelectedTarget] = useState("");
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const { data: session } = useSession();
  const [isLoading, setIsLoading] = useState(false);

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
      if (session?.user?.role === "admin") {
        router.push("/admin/datasets/users");
      } else {
        router.push("/my-datasets");
      }
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
    <Card className="max-w-3xl mx-auto mt-10 p-6 shadow-lg rounded-xl">
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
            <div>
              <Label className="block font-medium text-gray-700 mb-2">
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

            <div>
              <Label className="block font-medium text-gray-700 mb-2">
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

            <div className="flex justify-between mt-6">
              <Button variant="secondary" onClick={handleBack}>
                Quay lại
              </Button>
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
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TrainMyDataCard;
