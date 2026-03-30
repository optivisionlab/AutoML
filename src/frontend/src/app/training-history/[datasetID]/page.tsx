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
import { useEffect, useState, useCallback, useMemo } from "react";
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
import toTitleLabel from "@/utils/toTitleLable";
import { useApi } from "@/hooks/useApi";

type Props = {
  params: Promise<{
    datasetID: string;
  }>;
};

const ResultPage = ({ params }: Props) => {
  const { post, get } = useApi();

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

  // Lấy danh sách độ đo theo loại bài toán
  type MetricOb = Record<string, string>;
  const [metrics, setMetrics] = useState<MetricOb>({});

  const getMetrics = useCallback(async (type: string) => {
    try {
      const data = await get(`/v2/auto/metrics?problem_type=${type}`);

      console.log(data.metrics);
      setMetrics(data.metrics);
    } catch (err) {
      console.error("Lỗi khi gọi API:", err);
      alert("Không thể tải dữ liệu huấn luyện.");
    }
  }, []);

  // Fetch data train từ API đầu tiên
  const fetchDataResult = useCallback(async () => {
    if (datasetID) {
      setIsLoading(true);
      try {
        const data = await post(`get-job-info?id=${datasetID}`);
        setResult(data);

        const problemType = data.config?.problem_type || "classification";
        const test_value = data?.orther_model_scores[0]?.scores?.f1;

        if (!test_value && problemType) {
          getMetrics(problemType);
        } else {
          setMetrics({
            0: "accuracy",
            1: "f1",
            2: "precision",
            3: "recall",
          });
        }
      } catch (err) {
        console.log("Lỗi khi gọi API:", err);
        setError(
          "Có lỗi xảy ra trong quá trình huấn luyện, vui lòng xem lại cấu hình thuộc tính.",
        );
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
            <CardTitle className="text-red-600 text-lg">
              Đã xảy ra lỗi
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-700">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Setup biểu đồ
  // Chart config
  const randomColor = () => `hsl(${Math.floor(Math.random() * 360)}, 70%, 45%)`;

  const chartConfig = Object.entries(metrics).reduce(
    (config: any, [key, value]) => {
      config[key] = {
        label: value, // <-- HIỂN THỊ CHỮ NÀY
        value: value, // dùng để map scores
        color: randomColor(),
      };
      return config;
    },
    {},
  ) satisfies ChartConfig;

  // Chart data
  const chartData = useMemo(() => {
    if (!result?.orther_model_scores) return [];

    return result.orther_model_scores
      .filter((model: any) => {
        const r2 = model.scores?.r2;
        if (r2 !== undefined && r2 < -1) return false;
        
        const mse = model.scores?.mse;
        if (mse !== undefined && mse > 1000000) return false; 
        
        return true;
      })
      .map((model: any) => {
        const row: any = { name: model.model_name };
        Object.entries(chartConfig).forEach(([key, metric]: any) => {
          let val = model.scores?.[metric.value] || 0;
          if (metric.value === "r2" && val < 0) val = 0;
          row[key] = parseFloat(val.toFixed(4));
        });
        return row;
      });
  }, [result, chartConfig]);

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
                  <TableHead className="text-center">
                    Mô hình huấn luyện
                  </TableHead>
                  <TableHead className="text-center">
                    Thuộc tính mục tiêu
                  </TableHead>
                  <TableHead className="text-center">
                    Thuộc tính huấn luyện
                  </TableHead>
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

                  <YAxis domain={[0, 1]} tickLine={false} axisLine={false} />

                  <ChartTooltip content={<ChartTooltipContent />} />

                  {/* Chú thích */}
                  <ChartLegend content={<ChartLegendContent />} />

                  {Object.entries(chartConfig).map(([key]) => (
                    <Bar
                      key={key}
                      dataKey={key} //
                      fill={`var(--color-${key})`}
                      radius={4}
                    />
                  ))}
                </BarChart>
              </ChartContainer>
            ) : (
              <Table className="mt-4 p-4">
                <TableHeader>
                  <TableRow className="text-center">
                    <TableHead className="text-center">Model</TableHead>
                    {Object.entries(metrics).map(([metric, value]) => (
                      <TableHead key={metric} className="text-center">
                        {toTitleLabel(value)}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.orther_model_scores.map(
                    (model: any, index: number) => (
                      <TableRow key={index} className="text-center">
                        <TableCell>{model.model_name}</TableCell>

                        {Object.values(metrics).map((metricKey: string) => (
                          <TableCell key={metricKey}>
                            {model.scores?.[metricKey]?.toFixed(6) ?? "-"}
                          </TableCell>
                        ))}
                      </TableRow>
                    ),
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
