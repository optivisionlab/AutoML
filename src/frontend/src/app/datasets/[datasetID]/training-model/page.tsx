"use client";
import { useParams } from "next/navigation";
import React, { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import Link from "next/link";
import { Button } from "@/components/ui/button";

const TrainingModel = () => {
  const params = useParams();
  const [choice, setChoice] = useState("new_model");

  useEffect(() => {
    sessionStorage.setItem(
      "choose",
      choice === "new_model" ? "new_model" : "new_version"
    );
  }, [choice]);

  return (
    <>
      <h3>Huấn luyện cho mô hình có ID: {params?.datasetID}</h3>

      <div className="mt-4">
        <h4 className="mb-3">Chọn mô hình huấn luyện</h4>
        <RadioGroup defaultValue="auto" onValueChange={setChoice}>
          <div className="flex items-center space-x-2 mb-2">
            <RadioGroupItem value="new_model" id="new_model" />
            <Label htmlFor="new_model">Huấn luyện một mô hình mới</Label>
          </div>
          <div className="flex items-center space-x-2 mb-2">
            <RadioGroupItem value="new_version" id="new_version" disabled />
            <Label htmlFor="new_version">Huấn luyện một version mới</Label>
          </div>
        </RadioGroup>

        <div className="flex justify-end mt-4 space-x-4">
          <Button asChild>
            <Link href={`/datasets`} type="button">
              Quay lại
            </Link>
          </Button>

          <Button asChild>
            <Link href={`/datasets/${params?.datasetID}/method`} type="button">
              Tiếp theo
            </Link>
          </Button>
        </div>
      </div>
    </>
  );
};

export default TrainingModel;