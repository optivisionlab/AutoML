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

  // Xử lý
  const handleUploadAndDownload = async (jobId: string, file: File) => {
    try {
      const formData = new FormData();
      formData.append("file_data", file);

      const response = await post(`/v2/auto/${jobId}/predictions`, formData, {
        isBlob: true,
      });

      const blob = response.data;

      if (!(blob instanceof Blob)) {
        console.error("Không phải file:", blob);
        alert("API không trả file");
        return;
      }

      // lấy tên file
      const contentDisposition = response.headers["content-disposition"];
      let fileName = "result.csv";

      if (contentDisposition) {
        const match =
          contentDisposition.match(/filename\*=UTF-8''(.+)/) ||
          contentDisposition.match(/filename="?([^"]+)"?/);

        if (match?.[1]) {
          fileName = decodeURIComponent(match[1]);
        }
      }

      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;

      document.body.appendChild(a);
      a.click();

      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      const blob = err.response?.data;

      if (blob instanceof Blob) {
        const text = await blob.text(); // convert blob → text
        alert("ERROR TEXT:" + text);

        try {
          const json = JSON.parse(text);
          console.log("ERROR JSON:", json);
        } catch {
          console.log("Không parse được JSON");
        }
      } else {
        console.log("ERROR:", err.response?.data);
      }
    }
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
                    <TableCell className="text-center">
                      <Button
                        variant="default"
                        className={`px-4 py-2 rounded-md text-white ${
                          job.status === 1
                            ? "bg-[#3a6df4] hover:bg-[#5b85f7]"
                            : "bg-gray-400 cursor-not-allowed"
                        }`}
                        onClick={() => {
                          if (job.status === 1) {
                            router.push(`/training-history/${job.job_id}`);
                          }
                        }}
                        disabled={job.status !== 1}
                      >
                        Xem chi tiết
                      </Button>

                      {/* Upload + Predict */}
                      <label>
                        <input
                          type="file"
                          accept=".csv"
                          className="hidden"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file && job.status === 1) {
                              handleUploadAndDownload(job.job_id, file);
                            }
                          }}
                        />
                        <Button
                          className={`px-4 ml-2 py-2 ${
                            job.status === 1
                              ? "bg-green-600 hover:bg-green-700 text-white"
                              : "bg-gray-400 cursor-not-allowed"
                          }`}
                          disabled={job.status !== 1}
                          asChild
                        >
                          <span>Tải về</span>
                        </Button>
                      </label>
                    </TableCell>
                  </TableRow>
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
