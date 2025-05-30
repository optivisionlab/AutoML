"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
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
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";

type TrainingJob = {
  _id: string;
  job_id: string;
  data: {
    name: string;
  };
  best_model?: string;
  best_score?: number;
  create_at?: number;
  status: number; // 0 = đang training, 1 = đã hoàn thành
};

const formatDate = (timestamp?: number): string => {
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
  const [loading, setLoading] = useState<boolean>(false);
  const { data: session } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  useEffect(() => {
    const fetchTrainingJobs = async () => {
      if (!session?.user?.id) return;

      setLoading(true);
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_BASE_API}/get-list-job-by-userId?user_id=${session.user.id}`,
          {
            method: "POST",
            headers: {
              Accept: "application/json",
            },
          }
        );

        if (!response.ok) throw new Error("Lỗi khi gọi API");

        const data = await response.json();
        setJobs(data || []);
      } catch (error) {
        console.error("Lỗi khi lấy lịch sử huấn luyện:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchTrainingJobs();
  }, [session?.user?.id]);

  const handleConfirm = async () => {
    if (!selectedJobId) return;

    try {
      const response = await fetch(
        `http://10.100.200.119:9999/activate-model?job_id=${selectedJobId}&activate=1`,
        {
          method: "POST",
          headers: {
            accept: "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error("Kích hoạt mô hình thất bại");
      }

      router.push(`/implement-project/${selectedJobId}`);
    } catch (error) {
      console.error("Lỗi khi kích hoạt mô hình:", error);
      alert("Không thể triển khai mô hình. Vui lòng thử lại.");
    } finally {
      setSelectedJobId(null);
    }
  };


  console.log("Training jobs:", jobs);

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
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tên bộ dữ liệu</TableHead>
                <TableHead>Mô hình tốt nhất</TableHead>
                <TableHead>Độ chính xác</TableHead>
                <TableHead>Ngày huấn luyện</TableHead>
                <TableHead>Trạng thái</TableHead>
                <TableHead className="text-center">Hành động</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job._id}>
                  <TableCell>{job.data?.name || "Không rõ"}</TableCell>
                  <TableCell>
                    {job.status === 1
                      ? job.best_model || "Không rõ"
                      : "Đang xử lý"}
                  </TableCell>
                  <TableCell>
                    {job.status === 1 && job.best_score !== undefined
                      ? `${(job.best_score * 100).toFixed(2)}%`
                      : "Đang xử lý"}
                  </TableCell>
                  <TableCell>{formatDate(job.create_at)}</TableCell>
                  <TableCell>
                    {job.status === 1 ? <Badge variant="outline" className="bg-green-100 text-green-800">Đã hoàn thành</Badge>
                      : <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">
                        Đang training
                      </Badge>}
                  </TableCell>
                  <TableCell className="text-center">
                    <AlertDialog open={selectedJobId === job.job_id} onOpenChange={(open) => {
                      if (!open) setSelectedJobId(null);
                    }}>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="default"
                          className={`px-4 py-2 rounded-md text-white ${job.status === 1
                            ? "bg-[#3a6df4] hover:bg-[#5b85f7]"
                            : "bg-gray-400 cursor-not-allowed"
                            }`}
                          disabled={job.status !== 1}
                          onClick={() => {
                            if (job.status === 1) {
                              setSelectedJobId(job.job_id);
                            }
                          }}
                        >
                          Triển khai mô hình
                        </Button>
                      </AlertDialogTrigger>

                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Bạn có chắc chắn muốn triển khai mô hình này không?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Hành động này sẽ chuyển bạn đến trang triển khai. Vui lòng xác nhận để tiếp tục.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Hủy</AlertDialogCancel>
                          <AlertDialogAction onClick={handleConfirm}>Đồng ý</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>

                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
};

export default ImplementProject;