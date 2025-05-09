// components/crudDataset/AddDatasetDialog.tsx

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

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId: string;
  onSuccess?: () => void;
};

const AddDatasetDialog = ({ open, onOpenChange, userId, onSuccess }: Props) => {
  const { toast } = useToast();

  const [dataName, setDataName] = useState("");
  const [dataType, setDataType] = useState("table");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!dataName || !file) {
      toast({
        title: "Vui lòng nhập đầy đủ thông tin",
        variant: "destructive",
      });
      return;
    }

    const formData = new FormData();
    formData.append("data_name", dataName);
    formData.append("data_type", dataType);
    formData.append("file_data", file);

    try {
      setLoading(true);

      const res = await fetch(
        `http://127.0.0.1:9999/upload-dataset?user_id=${userId}`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!res.ok) throw new Error("Tải lên thất bại");

      toast({
        title: "Tải lên thành công!",
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });

      onOpenChange(false);
      onSuccess?.();
      setDataName("");
      setFile(null);
    } catch (err) {
      toast({
        title: "Có lỗi xảy ra",
        description: "Không thể tải lên dữ liệu.",
        variant: "destructive",
      });
      console.log("Lỗi tải lên:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader className="text-center flex flex-col items-center">
          <DialogTitle className="text-center">Thêm bộ dữ liệu</DialogTitle>
          <DialogDescription className="text-center">
            Nhập thông tin và chọn file để tải lên.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label>Tên bộ dữ liệu</Label>
            <Input
              type="text"
              value={dataName}
              onChange={(e) => setDataName(e.target.value)}
              placeholder="Nhập tên bộ dữ liệu"
            />
          </div>

          <div>
            <Label>Kiểu dữ liệu</Label>
            <select
              value={dataType}
              onChange={(e) => setDataType(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
            >
              <option value="table">Bảng</option>
              <option value="image">Hình ảnh</option>
              <option value="text">Văn bản</option>
            </select>
          </div>

          <div>
            <Label>Chọn file</Label>
            <Input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>
        </div>

        <DialogFooter className="mt-6 flex justify-end">
          <Button
            disabled={loading}
            onClick={handleSubmit}
            className="bg-[#3a6df4] text-white hover:bg-[#5b85f7]"
          >
            {loading ? "Đang tải lên..." : "Tải lên"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AddDatasetDialog;
