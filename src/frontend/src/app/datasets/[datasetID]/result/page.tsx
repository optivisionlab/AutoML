"use client";
import React, { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import { RootState } from "@/redux/store";
import axios from "axios";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const Result = () => {
  const data = useSelector((state: RootState) => state.getDataUCI); // Lấy data từ Redux
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<any>(null);

  const dataTrain = data.dataUCI.data;

  useEffect(() => {
    if (typeof window !== "undefined") {
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
        console.error(err);
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
        const response = await axios.post("http://localhost:9999/train-from-requestbody-json/", {
          data: dataTrain,
          config: config,
        });

        setResult(response.data);
        // console.log(">> API response: ", response.data);
      } catch (err) {
        console.error(err);
        setError("Lỗi khi gửi request đến server.");
      } finally {
        setLoading(false);
      }
    };

    if (config && dataTrain) {
      trainModel(); 
    }
  }, [config, dataTrain]); 

  console.log(">> Check result:", result);

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold text-center">Kết quả huấn luyện</h2>
      {loading && <p>Đang tải...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {result && (<p className="text-blue-900 font-semibold">Best model information: </p>)}
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
      {result && (<p className="text-blue-900 font-semibold">All model scores: </p>)}
      {result && (
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
            {result.orther_model_scores.map((model: any, index: number) => (
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
      )}

    </div>
  );
};

export default Result;
