"use client";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useEffect, useState, useCallback } from "react";
import { LoaderCircle } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ChartContainer } from "@/components/ui/chart";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { ChartLegend, ChartLegendContent } from "@/components/ui/chart";
import { type ChartConfig } from "@/components/ui/chart";

type Props = {
  params: Promise<{
    datasetID: string;
  }>;
};

const ResultPage = ({ params }: Props) => {
  const [datasetID, setDatasetID] = useState<string | null>(null);
  const [dataTrain, setDataTrain] = useState<any[]>([]);
  const [config, setConfig] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const [showChart, setShowChart] = useState(false);

  useEffect(() => {
    setIsClient(true); // Đảm bảo code chạy trên client
  }, []);

  useEffect(() => {
    const unwrapParams = async () => {
      const unwrappedParams = await params;
      setDatasetID(unwrappedParams.datasetID);
    };

    unwrapParams();
  }, [params]);

  // Fetch data train từ API đầu tiên
  const fetchDataTrain = useCallback(async () => {
    if (datasetID) {
      setIsLoading(true);
      try {
        const response = await fetch(
          `http://10.100.200.119:9999/get-data-from-mongodb-to-train?id=${datasetID}`,
          {
            method: "POST",
            headers: { accept: "application/json" },
            body: "", // empty body if not needed
          }
        );
        const { data } = await response.json();
        setDataTrain(data);
      } catch (err) {
        console.log("Lỗi khi fetch:", err);
      } finally {
        setIsLoading(false);
      }
    }
  }, [datasetID]);

  useEffect(() => {
    fetchDataTrain();
  }, [datasetID, fetchDataTrain]);

  // Lấy cấu hình từ sessionStorage và chuẩn bị config
  useEffect(() => {
    if (!isClient) return;

    try {
      const choose = sessionStorage.getItem("choose");
      const metric_sort = sessionStorage.getItem("metric_sort");
      const target = sessionStorage.getItem("target");
      const method = sessionStorage.getItem("method");
      const listFeatureString = sessionStorage.getItem("list_feature");

      if (!choose || !metric_sort || !target || !method || !listFeatureString) {
        setError("Không tìm thấy đủ cấu hình trong session.");
        return;
      }

      // Chuyển list_feature từ string thành array
      const list_feature = JSON.parse(listFeatureString);

      const formattedConfig = {
        choose,
        metric_sort,
        target,
        list_feature,
        method,
      };

      setConfig(formattedConfig);
      console.log(">> Check formatted config: ", formattedConfig);
    } catch (err) {
      console.log(err);
      setError("Lỗi khi parse dữ liệu từ sessionStorage.");
    }
  }, [isClient]);

  // Gửi dataTrain và config tới API tiếp theo
  useEffect(() => {
    const trainModel = async () => {
      if (dataTrain.length && config) {
        const requestBody = {
          data: dataTrain,
          config: {
            choose: config.choose,
            metric_sort: config.metric_sort,
            list_feature: config.list_feature,
            target: config.target,
          },
        };

        setIsLoading(true);
        try {
          const response = await fetch(
            "http://10.100.200.119:9999/train-from-requestbody-json/",
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(requestBody),
            }
          );
          const resultData = await response.json();
          setResult(resultData); // Cập nhật kết quả từ API trả về
        } catch (err) {
          console.error("Lỗi khi gọi API train:", err);
        } finally {
          setIsLoading(false);
        }
      }
    };

    trainModel();
  }, [dataTrain, config]);

  if (error) {
    return <div>{error}</div>;
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

          {/* Bảng thông tin các mô hình khác */}
          <div className="mt-6">
            <p className="text-[#3a6df4] text-xl font-semibold">
              Thông tin tất cả các mô hình:{" "}
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
