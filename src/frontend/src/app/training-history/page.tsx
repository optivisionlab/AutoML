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

import PaginationCustom from "@/components/common/Panigation";
import { useApi } from "@/hooks/useApi";
import UploadPredictButton from "@/components/common/UploadPredictButton";
import UploadPredictBox from "@/components/common/UploadPredictBox";

type TrainingJob = {
  _id: string;
  job_id: string;
  data: {
    name: string;
  };
  best_model?: string;
  best_score?: number;
  create_at?: number;
  status: number;
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

const TrainingHistory = () => {
  const { post } = useApi();

  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  const { data: session } = useSession();
  const router = useRouter();

  const [currentPage, setCurrentPage] = useState<number>(1); // xác định trang hiện tại
  const itemsPerPage = 5; // số trang 1 page

  const [openRow, setOpenRow] = useState<string | null>(null);

  useEffect(() => {
    const fetchTrainingJobs = async () => {
      if (!session?.user?.id) return;

      setLoading(true);
      try {
        const data = await post(
          `/get-list-job-by-userId?user_id=${session.user.id}`,
        );

        setJobs(data || []);
      } catch (error) {
        console.error("Lỗi khi lấy lịch sử huấn luyện:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchTrainingJobs();
  }, [session?.user?.id]);

  const handleSortByDate = () => {
    const sortedJobs = [...jobs].sort((a, b) => {
      const timeA = a.create_at || 0;
      const timeB = b.create_at || 0;
      return sortAsc ? timeA - timeB : timeB - timeA;
    });

    setJobs(sortedJobs);
    setSortAsc(!sortAsc);
  };

  const totalPages = Math.ceil(jobs.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const currentJobs = jobs.slice(startIndex, startIndex + itemsPerPage);

  return (
    <Card className="max-w-6xl mx-auto mt-8 shadow-md">
      <CardHeader>
        <CardTitle className="text-2xl font-bold text-[#3b6cf5] text-center">
          Lịch sử huấn luyện
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-center text-gray-500">Đang tải dữ liệu...</p>
        ) : jobs.length === 0 ? (
          <p className="text-center text-gray-500">
            Không có lịch sử huấn luyện nào.
          </p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tên bộ dữ liệu</TableHead>
                  <TableHead>Mô hình tốt nhất</TableHead>
                  <TableHead>Độ chính xác</TableHead>
                  <TableHead>
                    <Button
                      variant="ghost"
                      className="flex items-center gap-1 p-0 hover:bg-transparent text-sm text-gray-700"
                      onClick={handleSortByDate}
                    >
                      Ngày huấn luyện {sortAsc ? "↑" : "↓"}
                    </Button>
                  </TableHead>
                  <TableHead className="text-center">Trạng thái</TableHead>
                  <TableHead className="text-center">Hành động</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {currentJobs.map((job) => (
                  <React.Fragment key={job._id}>
                    {/* Row chính */}
                    <TableRow>
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

                      <TableCell className="text-center">
                        {job.status === 1 ? (
                          <Badge
                            variant="outline"
                            className="bg-green-100 text-green-800"
                          >
                            Đã hoàn thành
                          </Badge>
                        ) : job.status === 0 ? (
                          <Badge
                            variant="secondary"
                            className="bg-yellow-100 text-yellow-800"
                          >
                            Đang training
                          </Badge>
                        ) : (
                          <Badge
                            variant="default"
                            className="bg-[#ef6363] text-[#fff] px-5 py-2"
                          >
                            Có lỗi xảy ra
                          </Badge>
                        )}
                      </TableCell>

                      <TableCell className="text-center flex justify-around">
                        <Button
                          variant="default"
                          className={`px-4 py-2 rounded-md text-white ${job.status === 1 ? "bg-[#3a6df4] hover:bg-[#5b85f7]" : "bg-gray-400 cursor-not-allowed"}`}
                          onClick={() => {
                            if (job.status === 1) {
                              router.push(`/training-history/${job.job_id}`);
                            }
                          }}
                          disabled={job.status !== 1}
                        >
                          Xem chi tiết
                        </Button>
                        <Button
                          className={`px-4 py-2 text-white transition ${
                            openRow === job.job_id
                              ? "bg-red-500 hover:bg-red-600"
                              : "bg-green-600 hover:bg-green-700"
                          }`}
                          onClick={() =>
                            setOpenRow(
                              openRow === job.job_id ? null : job.job_id,
                            )
                          }
                        >
                          {openRow === job.job_id ? "X" : "Upload & Dự đoán"}
                        </Button>
                      </TableCell>
                    </TableRow>

                    {/* Row mở rộng */}
                    {openRow === job.job_id && (
                      <TableRow>
                        <TableCell colSpan={6}>
                          <div className="p-4 bg-gray-50 rounded-lg animate-in fade-in slide-in-from-top-2">
                            <UploadPredictBox
                              jobId={job.job_id}
                              disabled={job.status !== 1}
                            />
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>

            {/* Pagination */}
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

export default TrainingHistory;
