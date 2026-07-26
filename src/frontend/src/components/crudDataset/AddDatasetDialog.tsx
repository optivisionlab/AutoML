"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useState } from "react";
import { useUploadDatasetMutation } from "@/redux/api/datasetApi";
import { getApiErrorMessage } from "@/redux/api/baseApi";
import { UploadCloud } from "lucide-react";
import { useTranslations } from "next-intl";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId: string;
  onSuccess?: () => void;
};

const AddDatasetDialog = ({ open, onOpenChange, userId, onSuccess }: Props) => {
  const t = useTranslations("DatasetDialogs.add");
  const common = useTranslations("Common");
  const { toast } = useToast();
  const [uploadDataset, { isLoading }] = useUploadDatasetMutation();

  const [dataName, setDataName] = useState("");
  const [dataType, setDataType] = useState("table");
  const [file, setFile] = useState<File | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const resetForm = () => {
    setDataName("");
    setDataType("table");
    setFile(null);
  };

  const handleUpload = async () => {
    if (!dataName || !file) {
      toast({
        title: t("missingInfo"),
        variant: "destructive",
        duration: 3000,
      });
      return;
    }

    try {
      await uploadDataset({
        userId,
        dataName,
        dataType,
        file,
      }).unwrap();

      toast({
        title: t("uploadSuccess"),
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });

      resetForm();
      setConfirmOpen(false); // đóng dialog xác nhận
      onOpenChange(false); // đóng dialog chính
      onSuccess?.();
    } catch (err) {
      console.error("Upload error:", err);
      toast({
        title: t("errorTitle"),
        description: getApiErrorMessage(err, t("uploadFailed")),
        variant: "destructive",
      });
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="automl-dialog-content max-w-md">
          <DialogHeader className="automl-dialog-header">
            <div className="automl-dialog-kicker mb-3">
              <UploadCloud className="h-5 w-5" />
            </div>
            <DialogTitle className="automl-dialog-title">
              {t("title")}
            </DialogTitle>
            <DialogDescription className="automl-dialog-description">
              {t("description")}
            </DialogDescription>
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
              <select
                value={dataType}
                onChange={(e) => setDataType(e.target.value)}
                className="automl-dialog-input w-full"
              >
                <option value="table">{t("types.table")}</option>
                <option value="image">{t("types.image")}</option>
                <option value="text">{t("types.text")}</option>
              </select>
            </div>

            <div className="automl-dialog-field">
              <Label>{t("chooseFile")}</Label>
              <Input
                className="automl-dialog-input py-2"
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </div>
          </div>

          <DialogFooter className="automl-dialog-footer">
            <Button
              disabled={isLoading}
              onClick={() => setConfirmOpen(true)}
              className="automl-action-primary"
            >
              {isLoading ? t("uploading") : t("upload")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog xác nhận đơn giản */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="automl-dialog-content max-w-md">
          <DialogHeader className="automl-dialog-header">
            <DialogTitle className="automl-dialog-title">{common("confirm")}</DialogTitle>
            <DialogDescription className="automl-dialog-description">
              {t("confirmDescription")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="automl-dialog-footer">
            <Button
              variant="outline"
              className="automl-dialog-button-muted"
              onClick={() => setConfirmOpen(false)}
            >
              {common("cancel")}
            </Button>
            <Button
              disabled={isLoading}
              onClick={handleUpload}
              className="automl-action-primary"
            >
              {isLoading ? t("uploading") : common("confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default AddDatasetDialog;
