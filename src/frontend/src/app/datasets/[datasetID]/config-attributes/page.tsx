"use client";
import React, { useEffect, useState } from "react";
import { useDispatch } from "react-redux";
import { AppDispatch } from "@/redux/store";
import { getDataUCIAsync } from "@/redux/slices/dataUCISlice";
import { Card } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useParams } from "next/navigation";

const ConfigAttributes = () => {
  const dispatch = useDispatch<AppDispatch>();
  const [targetAttributes, setTargetAttributes] = useState<string[]>([]);
  const [trainingAttributes, setTrainingAttributes] = useState<string[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null);
  const [selectAll, setSelectAll] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const params = useParams();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await dispatch(getDataUCIAsync()).unwrap();
        if (res) {
          setTargetAttributes(res.list_feature);
        }
      } catch (err: any) {
        setError(err || "Lỗi không xác định");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [dispatch]);

  const handleTrainingAttributeChange = (attr: string) => {
    setTrainingAttributes((prev) => {
      const updatedList = prev.includes(attr)
        ? prev.filter((item) => item !== attr)
        : [...prev, attr];
      sessionStorage.setItem("list_feature", JSON.stringify(updatedList));
      return updatedList;
    });
  };

  const handleSelectAll = () => {
    if (selectAll) {
      setTrainingAttributes([]);
      sessionStorage.setItem("list_feature", JSON.stringify([]));
    } else {
      const filteredAttributes = targetAttributes.filter(
        (attr) => attr !== selectedTarget
      );
      setTrainingAttributes(filteredAttributes);
      sessionStorage.setItem("list_feature", JSON.stringify(filteredAttributes));
    }
    setSelectAll(!selectAll);
  };

  return (
    <Card className="p-6 space-y-4">
      <h2 className="text-lg font-semibold text-center">Cấu hình thuộc tính</h2>

      {loading && <p>Đang tải dữ liệu...</p>}
      {error && <p className="text-red-500">{error}</p>}

      <div className="flex">
        {/* Chọn thuộc tính mục tiêu */}
        <div className="w-1/3">
          <h3 className="font-medium">Chọn thuộc tính mục tiêu</h3>
          <RadioGroup
            value={selectedTarget ?? ""}
            onValueChange={(value) => {
              setSelectedTarget(value);
              sessionStorage.setItem("target", value);
            }}
            className="space-y-2 mt-4"
          >
            {targetAttributes.map((attr) => (
              <div key={attr} className="flex items-center space-x-2">
                <RadioGroupItem value={attr} id={attr} />
                <Label htmlFor={attr}>{attr}</Label>
              </div>
            ))}
          </RadioGroup>
        </div>

        {/* Chọn thuộc tính đưa vào huấn luyện */}
        <div className="w-1/3">
          <h3 className="font-medium">Chọn thuộc tính đưa vào huấn luyện</h3>
          <div className="flex flex-col space-y-2 mt-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="selectAll"
                checked={selectAll}
                onCheckedChange={handleSelectAll}
              />
              <Label htmlFor="selectAll">Chọn tất cả thuộc tính</Label>
            </div>
            {targetAttributes.map((attr) => (
              <div key={attr} className="flex items-center space-x-2">
                <Checkbox
                  id={attr}
                  checked={trainingAttributes.includes(attr)}
                  onCheckedChange={() => handleTrainingAttributeChange(attr)}
                  disabled={selectedTarget === attr}
                />
                <Label
                  htmlFor={attr}
                  className={selectedTarget === attr ? "text-gray-400" : ""}
                >
                  {attr}
                </Label>
              </div>
            ))}
          </div>
        </div>

        {/* Chọn chỉ số đánh giá */}
        <div className="w-1/3">
          <h3 className="font-medium">Chọn chỉ số đánh giá</h3>
          <RadioGroup
            value={selectedMetric}
            onValueChange={(value) => {
              setSelectedMetric(value);
              sessionStorage.setItem("metric_sort", value);
            }}
            className="space-y-2 mt-4"
          >
            {["accuracy", "precision", "recall", "f1-score"].map((metric) => (
              <div key={metric} className="flex items-center space-x-2">
                <RadioGroupItem value={metric} id={metric} />
                <Label htmlFor={metric}>{metric}</Label>
              </div>
            ))}
          </RadioGroup>
        </div>
      </div>

      <div className="flex justify-end mt-4 space-x-4">
        <Button asChild>
          <Link href={`/datasets/${params?.datasetID}/method`} type="button">
            Quay lại
          </Link>
        </Button>

        <Button asChild>
          <Link href={`/datasets/${params?.datasetID}/result`} type="button">
            Tiếp theo
          </Link>
        </Button>
      </div>
    </Card>
  );
};

export default ConfigAttributes;