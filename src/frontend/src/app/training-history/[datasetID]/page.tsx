"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useEffect, useState, useCallback } from "react";
import { AlertCircle, LoaderCircle } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ChartContainer } from "@/components/ui/chart";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { ChartLegend, ChartLegendContent } from "@/components/ui/chart";
import { type ChartConfig } from "@/components/ui/chart";
import { useSession } from "next-auth/react";
import React from "react";

type Props = {
  params: Promise<{
    datasetID: string;
  }>;
};

const ResultPage = ({ params }: Props) => {
  const [datasetID, setDatasetID] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const { data: session } = useSession();

  const [showChart, setShowChart] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    const unwrapParams = async () => {
      const unwrappedParams = await params;
      setDatasetID(unwrappedParams.datasetID);
    };

    unwrapParams();
  }, [params]);

  // Fetch data train từ API đầu tiên
  const fetchDataResult = useCallback(async () => {
    if (datasetID) {
      setIsLoading(true);
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_BASE_API}/get-job-info?id=${datasetID}`,
          {
            method: "POST",
            headers: { accept: "application/json" },
            body: "",
          }
        );

        const data = await response.json();
        console.log("Dữ liệu từ API:", data);
        setResult(data);

      } catch (err) {
        console.log("Lỗi khi gọi API:", err);
        setError("Có lỗi xảy ra trong quá trình huấn luyện, vui lòng xem lại cấu hình thuộc tính.");
      } finally {
        setIsLoading(false);
      }
    }
  }, [datasetID]);

  useEffect(() => {
    fetchDataResult();
  }, [datasetID, fetchDataResult]);


  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-muted/50 px-4">
        <Card className="w-full max-w-md shadow-lg border border-red-300">
          <CardHeader className="flex flex-row items-center gap-3">
            <AlertCircle className="text-red-500" />
            <CardTitle className="text-red-600 text-lg">Đã xảy ra lỗi</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-700">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Chart data
  const chartData = result?.orther_model_scores?.map((model: any) => ({
    name: model.model_name,
    accuracy: model.scores.accuracy,
    f1: model.scores.f1,
    precision: model.scores.precision,
    recall: model.scores.recall,
  }));

  // Chart config
  const chartConfig = {
    accuracy: {
      label: "Accuracy",
      color: "#102E50",
    },
    f1: {
      label: "F1",
      color: "#EAB308",
    },
    precision: {
      label: "Precision",
      color: "#F43F5E",
    },
    recall: {
      label: "Recall",
      color: "#169976",
    },
  } satisfies ChartConfig;

  return (
    <div className="relative p-6">
      {/* Hiển thị loading bao trùm toàn màn hình */}
      {isLoading && (
        <div className="fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2 bg-white/80 p-4">
          <div className="flex items-center gap-2 text-blue-700">
            <LoaderCircle className="w-6 h-6 animate-spin" />
            <span className="text-lg font-medium">Đang tải...</span>
          </div>
        </div>
      )}

      {/* Card chứa kết quả huấn luyện */}
      {result && (
        <Card className="mb-6 text-center p-6">
          <h2 className="text-xl font-semibold text-[#3a6df4]">
            Kết quả huấn luyện
          </h2>

          {/* Bảng kết quả mô hình tốt nhất */}
          <Table className="mt-4 p-4">
            <TableHeader>
              <TableRow className="text-center">
                <TableHead className="text-center">Best Model ID</TableHead>
                <TableHead className="text-center">Best Model Name</TableHead>
                <TableHead className="text-center">Best Score</TableHead>
                <TableHead className="text-center">Best Params</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>{result.best_model_id}</TableCell>
                <TableCell>{result.best_model}</TableCell>
                <TableCell>{result.best_score}</TableCell>
                <TableCell>{JSON.stringify(result.best_params)}</TableCell>
              </TableRow>
            </TableBody>
          </Table>

          <div className="mt-6">
            <p className="text-[#3a6df4] text-xl font-semibold">
              Cấu hình thuộc tính
            </p>

            <Table className="mt-4 p-4">
            <TableHeader>
              <TableRow className="text-center">
                <TableHead className="text-center">Mô hình huấn luyện</TableHead>
                <TableHead className="text-center">Thuộc tính mục tiêu</TableHead>
                <TableHead className="text-center">Thuộc tính huấn luyện</TableHead>
                <TableHead className="text-center">Chỉ số đánh giá</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>{result.config.choose}</TableCell>
                <TableCell>{result.config.target}</TableCell>
                <TableCell>{result.config.list_feature.join(", ")}</TableCell>
                <TableCell>{result.config.metric_sort}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
          </div>

          {/* Bảng thông tin các mô hình khác */}
          <div className="mt-6">
            <p className="text-[#3a6df4] text-xl font-semibold">
              Thông tin tất cả các mô hình
            </p>

            <div className="flex items-center justify-end mb-4 gap-2">
              <Label htmlFor="toggle-chart">Hiển thị dạng biểu đồ</Label>
              <Switch
                id="toggle-chart"
                checked={showChart}
                onCheckedChange={setShowChart}
              />
            </div>

            {showChart ? (
              <ChartContainer
                config={chartConfig}
                className="max-h-[450px] w-full"
              >
                <BarChart accessibilityLayer data={chartData}>
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="name"
                    tickLine={false}
                    tickMargin={10}
                    axisLine={false}
                    tickFormatter={(value) =>
                      value.replace(/([a-z])([A-Z])/g, "$1 $2")
                    }
                  />
                  <YAxis
                    domain={[0, 1]}
                    tickLine={false}
                    axisLine={false}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <ChartLegend content={<ChartLegendContent />} />
                  <Bar
                    dataKey="accuracy"
                    fill="var(--color-accuracy)"
                    radius={4}
                  />
                  <Bar dataKey="f1" fill="var(--color-f1)" radius={4} />
                  <Bar
                    dataKey="precision"
                    fill="var(--color-precision)"
                    radius={4}
                  />
                  <Bar dataKey="recall" fill="var(--color-recall)" radius={4} />
                </BarChart>
              </ChartContainer>
            ) : (
              <Table className="mt-4 p-4">
                <TableHeader>
                  <TableRow className="text-center">
                    <TableHead className="text-center">Model</TableHead>
                    <TableHead className="text-center">Accuracy</TableHead>
                    <TableHead className="text-center">F1</TableHead>
                    <TableHead className="text-center">Precision</TableHead>
                    <TableHead className="text-center">Recall</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.orther_model_scores.map(
                    (model: any, index: number) => (
                      <TableRow key={index}>
                        <TableCell>{model.model_name}</TableCell>
                        <TableCell>{model.scores.accuracy}</TableCell>
                        <TableCell>{model.scores.f1}</TableCell>
                        <TableCell>{model.scores.precision}</TableCell>
                        <TableCell>{model.scores.recall}</TableCell>
                      </TableRow>
                    )
                  )}
                </TableBody>
              </Table>
            )}
          </div>
        </Card>
      )}
    </div>
  );
};

export default ResultPage;