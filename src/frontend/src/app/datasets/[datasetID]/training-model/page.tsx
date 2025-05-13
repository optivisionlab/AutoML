"use client";
import { useParams } from "next/navigation";
import React, { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import Link from "next/link";

const TrainingModel = () => {
  const params = useParams();
  const [choice, setChoice] = useState("auto");

  useEffect(() => {
    sessionStorage.setItem("choose", choice === "auto" ? "new_model" : "new_version");
  }, [choice]);

  return (
    <>
      <h3>Training page for dataset ID: {params?.datasetID}</h3>

      <div className="mt-4">
        <h4>Chọn mô hình huấn luyện</h4>
        <RadioGroup defaultValue="auto" onValueChange={setChoice}>
          <div className="flex items-center space-x-2">
            <RadioGroupItem value="new_model" id="new_model" />
            <Label htmlFor="new_model">Huấn luyện một mô hình mới</Label>
          </div>
          <div className="flex items-center space-x-2">
            <RadioGroupItem value="new_version" id="new_version" />
            <Label htmlFor="new_version">Huấn luyện một version mới</Label>
          </div>
        </RadioGroup>

        <Link href={"/method"} type="button">Tiếp theo</Link>
      </div>
    </>
  );
};

export default TrainingModel;
