"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

// Step wrapper
interface StepProps {
  title: string;
  options: { value: string; label: string; disabled?: boolean }[];
  value: string;
  onChange: (val: string) => void;
  onNext?: () => void;
  onBack?: () => void;
  nextDisabled?: boolean;
  isLastStep?: boolean;
}

const StepModel = ({
  title,
  options,
  value,
  onChange,
  onNext,
  onBack,
  nextDisabled,
  isLastStep,
}: StepProps) => {
  return (
    <div className="space-y-6 mt-6">
      <Label className="text-base font-medium">{title}</Label>

      <RadioGroup
        value={value}
        onValueChange={onChange}
        className="grid grid-cols-2 gap-4"
      >
        {options.map(({ value, label, disabled }) => (
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
        {onBack && (
          <Button variant="secondary" onClick={onBack}>
            Quay lại
          </Button>
        )}
        {onNext && (
          <Button
            onClick={onNext}
            disabled={nextDisabled}
            className="bg-[#3a6df4] text-white disabled:opacity-50 dark:hover:bg-[#2f5ed6]"
          >
            {isLastStep ? "Hoàn tất" : "Tiếp theo"}
          </Button>
        )}
      </div>
    </div>
  );
};

export default StepModel;
