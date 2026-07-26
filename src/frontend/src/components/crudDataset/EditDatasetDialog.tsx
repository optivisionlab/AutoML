"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useState, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { useUpdateDatasetMutation } from "@/redux/api/datasetApi";
import { getApiErrorMessage } from "@/redux/api/baseApi";
import { PencilLine } from "lucide-react";
import { useTranslations } from "next-intl";

type Props = {
  open: boolean;
  onOpenChange: (value: boolean) => void;
  dataset: {
    _id: string;
    dataName: string;
    dataType: string;
  };
};

const EditDatasetDialog = ({ open, onOpenChange, dataset }: Props) => {
  const t = useTranslations("DatasetDialogs.edit");
  const common = useTranslations("Common");
  const [updateDataset, { isLoading }] = useUpdateDatasetMutation();

  const [dataName, setDataName] = useState("");
  const [dataType, setDataType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const { toast } = useToast();

  // State quản lý dialog confirm sửa
  const [confirmOpen, setConfirmOpen] = useState(false);

  // Cập nhật dữ liệu mỗi khi dataset thay đổi
  useEffect(() => {
    if (dataset) {
      setDataName(dataset.dataName);
      setDataType(dataset.dataType);
      setFile(null);
    }
  }, [dataset]);

  const handleUpdate = async () => {
    try {
      await updateDataset({
        datasetId: dataset._id,
        dataName,
        dataType,
        file,
      }).unwrap();

      toast({
        title: t("updateSuccess"),
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });
      setConfirmOpen(false);
      onOpenChange(false);
    } catch (error) {
      toast({
        title: t("updateFailed"),
        description: getApiErrorMessage(error, t("errorDescription")),
        variant: "destructive",
        duration: 3000,
      });
    }
  };

  return (
    <>
      {/* Dialog chỉnh sửa dữ liệu */}
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="automl-dialog-content max-w-md">
          <DialogHeader className="automl-dialog-header">
            <div className="automl-dialog-kicker mb-3">
              <PencilLine className="h-5 w-5" />
            </div>
            <DialogTitle className="automl-dialog-title">
              {t("title")}
            </DialogTitle>
          </DialogHeader>
          <div className="automl-dialog-body automl-dialog-fields">
            <div className="automl-dialog-field">
              <Label>{t("datasetName")}</Label>
              <Input
                className="automl-dialog-input"
                value={dataName}
                onChange={(e) => setDataName(e.target.value)}
              />
            </div>
            <div className="automl-dialog-field">
              <Label>{t("dataType")}</Label>
              <Select value={dataType} onValueChange={setDataType}>
                <SelectTrigger className="automl-dialog-input">
                  <SelectValue placeholder={t("chooseType")} />
                </SelectTrigger>
                <SelectContent className="border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] text-[var(--automl-data-text)]">
                  <SelectItem value="table">{t("types.table")}</SelectItem>
                  <SelectItem value="image">{t("types.image")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="automl-dialog-field">
              <Label>{t("chooseFile")}</Label>
              <Input
                className="automl-dialog-input py-2"
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              {!file && (
                <p className="automl-dialog-helper">
                  {t("keepCurrentFile")}
                </p>
              )}
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                className="automl-dialog-button-muted px-4"
              >
                {common("cancel")}
              </Button>
              <Button
                onClick={() => setConfirmOpen(true)}
                className="automl-action-primary px-4"
              >
                {common("save")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Dialog confirm trước khi cập nhật */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="automl-dialog-content max-w-md">
          <DialogHeader className="automl-dialog-header">
            <DialogTitle className="automl-dialog-title">
              {t("confirmTitle")}
            </DialogTitle>
          </DialogHeader>
          <p className="automl-dialog-confirm-text">
            {t("confirmDescription")}
          </p>
          <div className="automl-dialog-footer">
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              className="automl-dialog-button-muted px-4"
            >
              {common("cancel")}
            </Button>
            <Button
              disabled={isLoading}
              onClick={handleUpdate}
              className="automl-action-primary px-4"
            >
              {isLoading ? "..." : common("confirm")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default EditDatasetDialog;
