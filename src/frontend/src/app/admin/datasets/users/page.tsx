"use client";

import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import EditDatasetDialog from "@/components/crudDataset/EditDatasetDialog";
import { useToast } from "@/hooks/use-toast";
import AddDatasetDialog from "@/components/crudDataset/AddDatasetDialog";
import DialogForm from "../../../../components/dialog";
import DatasetTable from "@/components/datasets/DatasetTable";

type Dataset = {
  _id: string;
  dataName: string;
  dataType: string;
  createDate: number;
  latestUpdate?: number;
  lastestUpdate?: number;
  userId: string;
  username: string;
};

const formatDate = (timestamp?: number): string => {
  if (!timestamp) return "Không có dữ liệu";
  return new Date(timestamp * 1000).toLocaleDateString("vi-VN");
};

const Page = () => {
  const { data: session } = useSession();
  const router = useRouter();

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [datasetIdToDelete, setDatasetIdToDelete] = useState<string | null>(
    null
  );
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const { toast } = useToast();

  const fetchDatasets = async () => {
    if (!session?.user?.id) return;
    setLoading(true);

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BASE_API}/get-list-data-user`,
        {
          method: "GET",
          headers: { Accept: "application/json" },
        }
      );

      if (!res.ok) throw new Error("Lỗi khi gọi API");

      const data = await res.json();
      setDatasets(data || []);
    } catch (err) {
      console.error("Lỗi khi lấy dữ liệu:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const handleOpenEdit = (dataset: Dataset) => {
    setSelectedDataset(dataset);
    setEditDialogOpen(true);
  };

  // Khi click xoá dataset trong bảng
  const handleOpenDelete = (id: string) => {
    setDatasetIdToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!datasetIdToDelete) return;

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BASE_API}/delete-dataset/${datasetIdToDelete}`,
        {
          method: "DELETE",
          headers: { Accept: "application/json" },
        }
      );

      if (!res.ok) throw new Error("Xoá thất bại");

      toast({
        title: "Xóa thành công",
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });
      fetchDatasets();
    } catch (err) {
      console.log("Lỗi xoá:", err);
      toast({
        title: "Xóa thất bại",
        description: "Có lỗi xảy ra khi xoá bộ dữ liệu.",
        variant: "destructive",
        duration: 3000,
      });
    } finally {
      setDeleteDialogOpen(false);
      setDatasetIdToDelete(null);
    }
  };

  return (
    <>
      <Card className="max-w-6xl mx-auto mt-8 shadow-md">
        <CardHeader>
          <CardTitle className="text-2xl font-bold text-[#3b6cf5] text-center w-full">
            Quản lý bộ dữ liệu của người dùng
          </CardTitle>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div>Đang tải dữ liệu...</div>
          ) : (
            <DatasetTable
              datasets={datasets}
              onEdit={handleOpenEdit}
              onDelete={handleOpenDelete}
            />
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      {selectedDataset && (
        <EditDatasetDialog
          open={editDialogOpen}
          onOpenChange={(open) => {
            setEditDialogOpen(open);
            if (!open) fetchDatasets();
          }}
          dataset={selectedDataset}
        />
      )}

      {/* Delete Dialog */}
      <DialogForm
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="XÁC NHẬN XOÁ"
        description="Thao tác này không thể hoàn tác. Dữ liệu sẽ bị xoá vĩnh viễn khỏi hệ thống."
        canceltext="Hủy"
        actionText="Xoá"
        onConfirm={confirmDelete}
      />

      {session?.user?.id && (
        <AddDatasetDialog
          open={addDialogOpen}
          onOpenChange={setAddDialogOpen}
          userId={session.user.id}
          onSuccess={fetchDatasets}
        />
      )}
    </>
  );
};

export default Page;
