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

  // Cập nhật dữ liệu mỗi khi dataset thay đổi
  useEffect(() => {
    if (dataset) {
      setDataName(dataset.dataName);
      setDataType(dataset.dataType);
      setFile(null); // reset file nếu có
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
        `http://10.100.200.119:9999/update-dataset/${dataset._id}`,
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
              onClick={handleUpdate}
              className="bg-[#3a6df4] w-20 text-white hover:bg-[#5b85f7] px-4 py-2 rounded-md"
            >
              Lưu
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EditDatasetDialog;
