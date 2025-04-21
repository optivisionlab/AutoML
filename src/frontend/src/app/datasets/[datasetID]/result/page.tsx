"use client";
import React, { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "@/redux/store";
import axios from "axios";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getDataUCIAsync } from "@/redux/slices/dataUCISlice";
import { AppDispatch } from "@/redux/store";
import { ChartContainer } from "@/components/ui/chart";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { ChartLegend, ChartLegendContent } from "@/components/ui/chart";
import { type ChartConfig } from "@/components/ui/chart";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { LoaderCircle } from "lucide-react";

const Result = () => {
  const data = useSelector((state: RootState) => state.getDataUCI); // Lấy data từ Redux

  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<any>(null);
  const [otherModel, setOrtherModel] = useState<any>(null);

  const [showChart, setShowChart] = useState<boolean>(false);

  const dispatch = useDispatch<AppDispatch>();

  const dataTrain = data?.dataUCI?.data || null;

  useEffect(() => {
    if (data.status == "idle" && !data.dataUCI) {
      dispatch(getDataUCIAsync());
    }
  }, [dispatch, data.dataUCI, data.status]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const choose = sessionStorage.getItem("choose");
        const metric_sort = sessionStorage.getItem("metric_sort");
        const target = sessionStorage.getItem("target");
        const method = sessionStorage.getItem("method");
        const listFeatureString = sessionStorage.getItem("list_feature");

        if (
          !choose ||
          !metric_sort ||
          !target ||
          !method ||
          !listFeatureString
        ) {
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
    }
  }, []);

  useEffect(() => {
    const trainModel = async () => {
      if (!config || !dataTrain) {
        setError("Thiếu dữ liệu để gửi yêu cầu.");
        return;
      }

      setLoading(true);
      try {
        const response = await axios.post(
          "http://localhost:9999/train-from-requestbody-json/",
          {
            data: dataTrain,
            config: config,
          }
        );

        setResult(response.data);
        setOrtherModel(response.data.orther_model_scores);
        // console.log(">> API response: ", response.data);
      } catch (err) {
        console.log(err);
        setError("Lỗi khi gửi request đến server.");
      } finally {
        setLoading(false);
      }
    };

    if (config && dataTrain) {
      trainModel();
    }
  }, [config, dataTrain]);

  // Chart data
  const chartData = otherModel?.map((model: any) => ({
    name: model.model_name,
    accuracy: model.scores.accuracy,
    f1: model.scores.f1,
    precision: model.scores.precision,
    recall: model.scores.recall,
  }));

  // chart config
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

  console.log(">> check show chart: ", showChart);

  return (
    <div className="p-6">
      {loading && (
        <div className="fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2 bg-white/80 p-4">
          <div className="flex items-center gap-2 text-blue-700">
            <LoaderCircle className="w-6 h-6 animate-spin" />
            <span className="text-lg font-medium">Đang tải...</span>
          </div>
        </div>
      )}
      {error && <p className="text-red-500">{error}</p>}
      {result && (
        <>
          <h2 className="text-xl font-bold text-center">Kết quả huấn luyện</h2>
          <p className="text-blue-900 font-semibold">
            Thông tin mô hình tốt nhất:{" "}
          </p>
        </>
      )}
      {result && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Best Model ID</TableHead>
              <TableHead>Best Model Name</TableHead>
              <TableHead>Best Score</TableHead>
              <TableHead>Best Params</TableHead>
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
      )}

      <br />
      {result && (
        <div className="flex justify-between mt-3">
          <p className="text-blue-900 font-semibold">Thông tin tất cả các mô hình: </p>

          <div>
            <Label htmlFor="view-switch" className="align-middle mr-2">
              {showChart ? "Hiển thị biểu đồ": "Hiển thị biểu đồ"}
            </Label>
            <Switch
              checked={showChart}
              onCheckedChange={setShowChart}
              id="view-switch"
            />
          </div>
        </div>
      )}
      {otherModel && (
        <>
          {!showChart ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Model</TableHead>
                  <TableHead>accuracy</TableHead>
                  <TableHead>f1</TableHead>
                  <TableHead>precision</TableHead>
                  <TableHead>recall</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {otherModel.map((model: any, index: number) => (
                  <TableRow key={index}>
                    <TableCell>{model.model_name}</TableCell>
                    <TableCell>{model.scores.accuracy}</TableCell>
                    <TableCell>{model.scores.f1}</TableCell>
                    <TableCell>{model.scores.precision}</TableCell>
                    <TableCell>{model.scores.recall}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
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
                  domain={[0.94, 0.98]}
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
          )}

          {/* Chart */}
        </>
      )}
    </div>
  );
};

export default Result;
