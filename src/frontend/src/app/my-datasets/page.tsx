"use client";

import React, { useEffect, useState } from "react";
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
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/hooks/use-toast";
import AddDatasetDialog from "@/components/crudDataset/AddDatasetDialog";
import { CirclePlus } from "lucide-react";

type Dataset = {
  _id: string;
  dataName: string;
  dataType: string;
  createDate: number;
  latestUpdate?: number;
  lastestUpdate?: number;
  userId: string;
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
        `http://127.0.0.1:9999/get-list-data-by-userid?id=${session.user.id}`,
        {
          method: "POST",
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

  const confirmDelete = async () => {
    if (!datasetIdToDelete) return;

    try {
      const res = await fetch(
        `http://127.0.0.1:9999/delete-dataset/${datasetIdToDelete}`,
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
            Bộ dữ liệu của tôi
          </CardTitle>

          <div className="flex justify-end mt-4">
            <Button
              className="bg-[#1e8449] text-white hover:bg-[#196f3d] px-6 py-2 rounded-md"
              onClick={() => setAddDialogOpen(true)}
            >
               <CirclePlus className="w-8 h-8" /> Thêm bộ dữ liệu
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div>Đang tải dữ liệu...</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tên bộ dữ liệu</TableHead>
                  <TableHead>Kiểu dữ liệu</TableHead>
                  <TableHead>Ngày tạo</TableHead>
                  <TableHead>Lần cập nhật mới nhất</TableHead>
                  <TableHead className="text-center">Chức năng</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {datasets.map((dataset) => (
                  <TableRow key={dataset._id}>
                    <TableCell>{dataset.dataName || "Không có tên"}</TableCell>
                    <TableCell>{dataset.dataType || "Chưa rõ"}</TableCell>
                    <TableCell>{formatDate(dataset.createDate)}</TableCell>
                    <TableCell>
                      {formatDate(
                        dataset.latestUpdate || dataset.lastestUpdate
                      )}
                    </TableCell>
                    <TableCell className="text-center space-x-2">
                      <Button
                        className="bg-[#3a6df4] text-white hover:bg-[#5b85f7]"
                        onClick={() =>
                          router.push(`/my-datasets/${dataset._id}/train`)
                        }
                      >
                        Huấn luyện
                      </Button>
                      <Button
                        className="bg-yellow-500 text-white hover:bg-yellow-600"
                        onClick={() => handleOpenEdit(dataset)}
                      >
                        Sửa
                      </Button>
                      <Button
                        className="bg-red-500 text-white hover:bg-red-600"
                        onClick={() => {
                          setDatasetIdToDelete(dataset._id);
                          setDeleteDialogOpen(true);
                        }}
                      >
                        Xoá
                      </Button>
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
            if (!open) fetchDatasets();
          }}
          dataset={selectedDataset}
        />
      )}

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader className="text-center space-y-2">
            <AlertDialogTitle className="text-lg font-semibold text-center">
              Bạn có chắc chắn muốn xoá?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-center text-gray-500">
              Thao tác này không thể hoàn tác. Dữ liệu sẽ bị xoá vĩnh viễn khỏi
              hệ thống.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <AlertDialogFooter className="flex justify-center gap-4 mt-4">
            <AlertDialogCancel className="px-4 py-2 rounded-md border border-gray-300 hover:bg-gray-100">
              Hủy
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-red-600 text-white hover:bg-red-700 px-4 py-2 rounded-md"
            >
              Xoá
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
