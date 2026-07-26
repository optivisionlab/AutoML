"use client";

import AppLoading from "@/components/common/AppLoading";
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSession } from "next-auth/react";
import EditDatasetDialog from "@/components/crudDataset/EditDatasetDialog";
import { useToast } from "@/hooks/use-toast";
import AddDatasetDialog from "@/components/crudDataset/AddDatasetDialog";
import DialogForm from "../../../../components/dialog";
import DatasetTable from "@/components/datasets/DatasetTable";
import {
  Dataset,
  useDeleteDatasetMutation,
  useGetAllUserDatasetsQuery,
} from "@/redux/api/datasetApi";
import { getApiErrorMessage } from "@/redux/api/baseApi";

const Page = () => {
  const { data: session } = useSession();
  const {
    data: datasets = [],
    isLoading,
    refetch,
  } = useGetAllUserDatasetsQuery();
  const [deleteDataset] = useDeleteDatasetMutation();

  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [datasetIdToDelete, setDatasetIdToDelete] = useState<string | null>(
    null,
  );
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const { toast } = useToast();

  const handleOpenEdit = (dataset: Dataset) => {
    setSelectedDataset(dataset);
    setEditDialogOpen(true);
  };

  const handleOpenDelete = (id: string) => {
    setDatasetIdToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!datasetIdToDelete) return;

    try {
      await deleteDataset(datasetIdToDelete).unwrap();

      toast({
        title: "Xóa thành công",
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });
      refetch();
    } catch (err) {
      console.log("Lỗi xoá:", err);
      toast({
        title: "Xóa thất bại",
        description: getApiErrorMessage(
          err,
          "Có lỗi xảy ra khi xoá bộ dữ liệu.",
        ),
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
      <Card className="automl-data-card mt-2 w-full">
        <CardHeader className="automl-data-toolbar">
          <div>
            <CardTitle className="automl-data-title">
              Quản lý bộ dữ liệu của người dùng
            </CardTitle>
            <p className="automl-data-subtitle">
              Theo dõi dataset đã upload trong toàn workspace và xử lý quyền quản trị.
            </p>
          </div>
          <div className="automl-data-actions">
            <span className="automl-data-chip">{datasets.length} datasets</span>
            <span className="automl-data-chip automl-data-chip-secondary">
              User workspace
            </span>
          </div>
        </CardHeader>

        <CardContent className="automl-table-wrap pt-5">
          {isLoading ? (
            <AppLoading />
          ) : (
            <DatasetTable
              datasets={datasets}
              onEdit={handleOpenEdit}
              onDelete={handleOpenDelete}
            />
          )}
        </CardContent>
      </Card>

      {selectedDataset && (
        <EditDatasetDialog
          open={editDialogOpen}
          onOpenChange={(open) => {
            setEditDialogOpen(open);
            if (!open) refetch();
          }}
          dataset={selectedDataset}
        />
      )}

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
          onSuccess={refetch}
        />
      )}
    </>
  );
};

export default Page;
