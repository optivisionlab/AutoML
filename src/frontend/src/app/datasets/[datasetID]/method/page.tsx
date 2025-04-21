"use client";
import { useParams } from "next/navigation";
import React, { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import Link from "next/link";
import { Button } from "@/components/ui/button";

const Method = () => {
  const params = useParams();
  const [method, setMethod] = useState("auto");

  useEffect(() => {
    sessionStorage.setItem("method", method === "auto" ? "auto" : "custom");
  }, [method]);

  return (
    <>
      <h3>Huấn luyện cho mô hình có ID: {params?.datasetID}</h3>

      <div className="mt-4">
        <h4 className="mb-3">Chọn cách huấn luyện</h4>
        <RadioGroup defaultValue="auto" onValueChange={setMethod}>
          <div className="flex items-center space-x-2 mb-2">
            <RadioGroupItem value="auto" id="auto" />
            <Label htmlFor="auto">Auto</Label>
          </div>
          <div className="flex items-center space-x-2 mb-2">
            <RadioGroupItem value="custom" id="custom" disabled/>
            <Label htmlFor="custom">Custom</Label>
          </div>
        </RadioGroup>

        <div className="flex justify-end mt-4 space-x-4">
          <Button asChild>
            <Link href={`/datasets/${params?.datasetID}/training-model`} type="button">Quay lại</Link>
          </Button>
          <Button asChild>
            <Link href={`/datasets/${params?.datasetID}/config-attributes`} type="button">Tiếp theo</Link>
          </Button>
        </div>

      </div>
    </>
  );
};

export default Method;