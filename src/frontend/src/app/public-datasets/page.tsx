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
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await fetch("http://127.0.0.1:9999/get-list-data-by-userid?id=0", {
          method: "POST",
          headers: {
            Accept: "application/json",
          },
        });

        if (!res.ok) throw new Error("Lỗi khi gọi API");

        const json = await res.json();
        setDatasets(json || []);
      } catch (err) {
        console.error("Lỗi khi lấy dữ liệu:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  return (
    <Card className="max-w-6xl mx-auto mt-8 shadow-md">
      <CardHeader>
        <CardTitle className="text-2xl font-bold text-[#3b6cf5] text-center w-full">
          Bộ dữ liệu có sẵn
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div>Đang tải dữ liệu...</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tên bộ dữ liệu</TableHead>
                <TableHead>Kiểu DL</TableHead>
                <TableHead>Ngày tạo</TableHead>
                <TableHead>Lần cập nhật</TableHead>
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
                    {formatDate(dataset.latestUpdate || dataset.lastestUpdate)}
                  </TableCell>
                  <TableCell className="text-center">
                    <Button
                      className="bg-[#3a6df4] w-20 text-white hover:bg-[#5b85f7] px-4 py-2 rounded-md"
                      variant="default"
                      onClick={() =>
                        router.push(`/public-datasets/${dataset._id}/train`)
                      }
                    >
                      Huấn luyện
                    </Button>
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

export default Page;
