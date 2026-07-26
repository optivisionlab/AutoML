"use client";

import RowActionMenu from "@/components/common/RowActionMenu";
import AppLoading from "@/components/common/AppLoading";
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import EditDatasetDialog from "@/components/crudDataset/EditDatasetDialog";
import DialogForm from "../../../../components/dialog";
import { useToast } from "@/hooks/use-toast";
import AddDatasetDialog from "@/components/crudDataset/AddDatasetDialog";
import { CirclePlus } from "lucide-react";
import {
  Dataset,
  useDeleteDatasetMutation,
  useGetDatasetsByUserIdQuery,
} from "@/redux/api/datasetApi";
import { getApiErrorMessage } from "@/redux/api/baseApi";

const formatDate = (timestamp?: number): string => {
  if (!timestamp) return "Không có dữ liệu";
  return new Date(timestamp * 1000).toLocaleDateString("vi-VN");
};

const Page = () => {
  const { data: session } = useSession();
  const router = useRouter();
  const { toast } = useToast();

  const {
    data: datasets = [],
    isLoading,
    refetch,
  } = useGetDatasetsByUserIdQuery("0");

  const [deleteDataset] = useDeleteDatasetMutation();

  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [datasetIdToDelete, setDatasetIdToDelete] = useState<string | null>(
    null,
  );
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const handleOpenEdit = (dataset: Dataset) => {
    setSelectedDataset(dataset);
    setEditDialogOpen(true);
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
              Quản lý bộ dữ liệu có sẵn
            </CardTitle>
            <p className="automl-data-subtitle">
              Tạo, chỉnh sửa và huấn luyện trên các dataset public dùng chung.
            </p>
          </div>

          <div className="automl-data-actions">
            <span className="automl-data-chip">{datasets.length} datasets</span>
            <Button
              className="automl-action-primary gap-2 px-4"
              onClick={() => setAddDialogOpen(true)}
            >
              <CirclePlus className="h-4 w-4" /> Thêm bộ dữ liệu
            </Button>
          </div>
        </CardHeader>

        <CardContent className="automl-table-wrap pt-5">
          {isLoading ? (
            <AppLoading />
          ) : datasets.length === 0 ? (
            <div className="automl-state-panel">Chưa có bộ dữ liệu public.</div>
          ) : (
            <Table className="automl-data-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Tên bộ dữ liệu</TableHead>
                  <TableHead>Kiểu dữ liệu</TableHead>
                  <TableHead>Ngày tạo</TableHead>
                  <TableHead>Lần cập nhật mới nhất</TableHead>
                  <TableHead className="text-center">Tác vụ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {datasets.map((dataset) => (
                  <TableRow key={dataset._id}>
                    <TableCell className="font-bold text-[var(--automl-data-text)]">
                      {dataset.dataName || "Không có tên"}
                    </TableCell>
                    <TableCell>{dataset.dataType || "Chưa rõ"}</TableCell>
                    <TableCell>{formatDate(dataset.createDate)}</TableCell>
                    <TableCell>
                      {formatDate(
                        dataset.latestUpdate || dataset.lastestUpdate,
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="flex justify-center">
                        <RowActionMenu
                          label={`Mở tác vụ ${dataset.dataName}`}
                          items={[
                            {
                              label: "Huấn luyện",
                              onClick: () => router.push(`/admin/datasets/public/${dataset._id}/train`),
                            },
                            { label: "Sửa", onClick: () => handleOpenEdit(dataset) },
                            {
                              label: "Xoá",
                              destructive: true,
                              onClick: () => {
                                setDatasetIdToDelete(dataset._id);
                                setDeleteDialogOpen(true);
                              },
                            },
                          ]}
                        />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
        title="Bạn có chắc chắn muốn xoá?"
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
