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
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";

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
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const { data: session } = useSession();
  const router = useRouter();

  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = 5;

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
                  <TableHead>Trạng thái</TableHead>
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
                    <TableCell>
                      {job.status === 1 ? (
                        <Badge
                          variant="outline"
                          className="bg-green-100 text-green-800"
                        >
                          Đã hoàn thành
                        </Badge>
                      ) : (
                        <Badge
                          variant="secondary"
                          className="bg-yellow-100 text-yellow-800"
                        >
                          Đang training
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
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* Pagination */}
            {totalPages > 1 && (
              <Pagination className="mt-4 justify-center">
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      onClick={() =>
                        setCurrentPage((prev) => Math.max(prev - 1, 1))
                      }
                      className={
                        currentPage === 1
                          ? "pointer-events-none opacity-50"
                          : ""
                      }
                    />
                  </PaginationItem>

                  {Array.from({ length: totalPages }, (_, i) => (
                    <PaginationItem key={i}>
                      <Button
                        variant="ghost"
                        onClick={() => setCurrentPage(i + 1)}
                        className={`px-3 ${
                          currentPage === i + 1
                            ? "bg-white border border-gray-300 text-black" // trang hiện tại
                            : ""
                        }`}
                      >
                        {i + 1}
                      </Button>
                    </PaginationItem>
                  ))}

                  <PaginationItem>
                    <PaginationNext
                      onClick={() =>
                        setCurrentPage((prev) => Math.min(prev + 1, totalPages))
                      }
                      className={
                        currentPage === totalPages
                          ? "pointer-events-none opacity-50"
                          : ""
                      }
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default TrainingHistory;
