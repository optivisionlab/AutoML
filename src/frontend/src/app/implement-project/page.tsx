"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationPrevious,
  PaginationNext,
  PaginationLink,
} from "@/components/ui/pagination";

import PaginationCustom from "@/components/common/Panigation";

type TrainingJob = {
  _id: string;
  job_id: string;
  data: { name: string };
  best_model?: string;
  best_score?: number;
  create_at?: number;
  status: number; // 0 = đang training, 1 = đã hoàn thành
};

const formatDate = (timestamp?: number) => {
  if (!timestamp) return "Không có dữ liệu";
  const date = new Date(timestamp * 1000);
  return date.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const ImplementProject = () => {
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const { data: session } = useSession();
  const router = useRouter();

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  const fetchTrainingJobs = async () => {
    if (!session?.user?.id) return;
    setLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BASE_API}/get-list-job-by-userId?user_id=${session.user.id}`,
        {
          method: "POST",
          headers: { Accept: "application/json" },
        }
      );
      if (!res.ok) throw new Error("Lỗi khi gọi API");
      const data = await res.json();
      setJobs(data || []);
    } catch (err) {
      console.error("Lỗi khi lấy lịch sử huấn luyện:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrainingJobs();
  }, [session?.user?.id]);

  const handleConfirm = async () => {
    if (!selectedJobId) return;
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BASE_API}/activate-model?job_id=${selectedJobId}&activate=1`,
        {
          method: "POST",
          headers: { Accept: "application/json" },
        }
      );
      if (!res.ok) throw new Error("Kích hoạt mô hình thất bại");
      router.push(`/implement-project/${selectedJobId}`);
    } catch (err) {
      console.error("Lỗi khi kích hoạt mô hình:", err);
      alert("Không thể triển khai mô hình. Vui lòng thử lại.");
    } finally {
      setSelectedJobId(null);
    }
  };

  const sortedJobs = [...jobs].sort((a, b) => {
    if (!a.create_at || !b.create_at) return 0;
    return sortOrder === "asc"
      ? a.create_at - b.create_at
      : b.create_at - a.create_at;
  });

  const totalPages = Math.ceil(sortedJobs.length / itemsPerPage);
  const paginatedJobs = sortedJobs.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  return (
    <Card className="max-w-6xl mx-auto mt-8 shadow-md">
      <CardHeader>
        <CardTitle className="text-2xl font-bold text-[#3b6cf5] text-center">
          Triển khai mô hình huấn luyện
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-center text-gray-500">Đang tải dữ liệu...</p>
        ) : jobs.length === 0 ? (
          <p className="text-center text-gray-500">
            Không có mô hình huấn luyện nào.
          </p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tên bộ dữ liệu</TableHead>
                  <TableHead>Mô hình tốt nhất</TableHead>
                  <TableHead>Độ chính xác</TableHead>
                  <TableHead
                    onClick={() =>
                      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"))
                    }
                    className="cursor-pointer hover:text-[#3a6df4]"
                  >
                    Ngày huấn luyện {sortOrder === "asc" ? "↑" : "↓"}
                  </TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead className="text-center">Hành động</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedJobs.map((job) => {
                  const isDone = job.status === 1;
                  const isSelected = selectedJobId === job.job_id;

                  return (
                    <TableRow key={job._id}>
                      <TableCell>{job.data?.name || "Không rõ"}</TableCell>
                      <TableCell>
                        {isDone ? job.best_model || "Không rõ" : "Đang xử lý"}
                      </TableCell>
                      <TableCell>
                        {isDone && job.best_score !== undefined
                          ? `${(job.best_score * 100).toFixed(2)}%`
                          : "Đang xử lý"}
                      </TableCell>
                      <TableCell>{formatDate(job.create_at)}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={
                            isDone
                              ? "bg-green-100 text-green-800"
                              : "bg-yellow-100 text-yellow-800"
                          }
                        >
                          {isDone ? "Đã hoàn thành" : "Đang training"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <AlertDialog
                          open={isSelected}
                          onOpenChange={(open) =>
                            !open && setSelectedJobId(null)
                          }
                        >
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="default"
                              className={`px-4 py-2 rounded-md text-white ${
                                isDone
                                  ? "bg-[#3a6df4] hover:bg-[#5b85f7]"
                                  : "bg-gray-400 cursor-not-allowed"
                              }`}
                              disabled={!isDone}
                              onClick={() =>
                                isDone && setSelectedJobId(job.job_id)
                              }
                            >
                              Triển khai mô hình
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>
                                Bạn có chắc chắn muốn triển khai mô hình này
                                không?
                              </AlertDialogTitle>
                              <AlertDialogDescription>
                                Hành động này sẽ kích hoạt mô hình được chọn.
                                Vui lòng xác nhận để tiếp tục.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Hủy</AlertDialogCancel>
                              <AlertDialogAction onClick={handleConfirm}>
                                Đồng ý
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>

            {/* Panigation */}
            <PaginationCustom
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default ImplementProject;
