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
  const [confirmOpen, setConfirmOpen] = useState(false);

  const resetForm = () => {
    setDataName("");
    setDataType("table");
    setFile(null);
  };

  const handleUpload = async () => {
    if (!dataName || !file) {
      toast({
        title: "Vui lòng nhập đầy đủ thông tin",
        variant: "destructive",
        duration: 3000,
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
        `${process.env.NEXT_PUBLIC_BASE_API}/upload-dataset?user_id=${userId}`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!res.ok) throw new Error("Upload failed");

      toast({
        title: "Tải lên thành công!",
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
        title: "Có lỗi xảy ra",
        description: "Không thể tải lên dữ liệu.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-md">
          <DialogHeader className="flex flex-col items-center text-center">
            <DialogTitle>Thêm bộ dữ liệu</DialogTitle>
            <DialogDescription>
              Nhập thông tin và chọn file để tải lên.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label>Tên bộ dữ liệu</Label>
              <Input
                value={dataName}
                onChange={(e) => setDataName(e.target.value)}
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

          <DialogFooter className="mt-6">
            <Button
              disabled={loading}
              onClick={() => setConfirmOpen(true)}
              className="bg-[#3a6df4] text-white hover:bg-[#5b85f7]"
            >
              {loading ? "Đang tải..." : "Tải lên"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog xác nhận đơn giản */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Xác nhận</DialogTitle>
            <DialogDescription>
              Bạn có chắc chắn muốn tải lên bộ dữ liệu này?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Hủy
            </Button>
            <Button
              disabled={loading}
              onClick={handleUpload}
              className="bg-[#3a6df4] text-white hover:bg-[#5b85f7]"
            >
              {loading ? "Đang tải..." : "Xác nhận"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default AddDatasetDialog;