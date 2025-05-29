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
    const formData = new FormData();
    formData.append("data_name", dataName);
    formData.append("data_type", dataType);
    if (file) {
      formData.append("file_data", file);
    }

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BASE_API}/update-dataset/${dataset._id}`,
        {
          method: "PUT",
          headers: { Accept: "application/json" },
          body: formData,
        }
      );

      if (!res.ok) throw new Error("Cập nhật thất bại");

      toast({
        title: "Cập nhật thành công",
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });
      setConfirmOpen(false);
      onOpenChange(false);
    } catch (error) {
      toast({
        title: "Cập nhật thất bại",
        description: error instanceof Error ? error.message : "Có lỗi xảy ra",
        variant: "destructive",
        duration: 3000,
      });
    }
  };

  return (
    <>
      {/* Dialog chỉnh sửa dữ liệu */}
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-2xl font-bold text-center w-full">
              Chỉnh sửa dữ liệu
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Tên dữ liệu</Label>
              <Input
                value={dataName}
                onChange={(e) => setDataName(e.target.value)}
              />
            </div>
            <div>
              <Label>Loại dữ liệu</Label>
              <Select value={dataType} onValueChange={setDataType}>
                <SelectTrigger>
                  <SelectValue placeholder="Chọn kiểu" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="table">Table</SelectItem>
                  <SelectItem value="image">Image</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Chọn file dữ liệu (.csv)</Label>
              <Input
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              {!file && (
                <p className="text-sm text-muted-foreground">
                  Nếu không chọn file mới, dữ liệu hiện tại sẽ được giữ nguyên.
                </p>
              )}
            </div>
            <div className="flex justify-center mt-4 space-x-4">
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                className="w-20 px-4 py-2 rounded-md"
              >
                Hủy
              </Button>
              <Button
                onClick={() => setConfirmOpen(true)}
                className="bg-[#3a6df4] w-20 text-white hover:bg-[#5b85f7] px-4 py-2 rounded-md"
              >
                Lưu
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Dialog confirm trước khi cập nhật */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold text-center w-full">
              Xác nhận chỉnh sửa
            </DialogTitle>
          </DialogHeader>
          <p className="text-center mb-6">
            Bạn có chắc chắn muốn sửa bộ dữ liệu này?
          </p>
          <div className="flex justify-center space-x-4">
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              className="w-20 px-4 py-2 rounded-md"
            >
              Hủy
            </Button>
            <Button
              onClick={handleUpdate}
              className="bg-[#3a6df4] w-20 text-white hover:bg-[#5b85f7] px-4 py-2 rounded-md"
            >
              Đồng ý
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default EditDatasetDialog;
