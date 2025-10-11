"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useEffect, useState, useCallback } from "react";
import { AlertCircle, CheckCircle, LoaderCircle } from "lucide-react";
import { type ChartConfig } from "@/components/ui/chart";
import { useSession } from "next-auth/react";
import React from "react";
import { useRouter } from "next/navigation";

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
  const { data: session } = useSession();
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const router = useRouter();

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
          `${process.env.NEXT_PUBLIC_BASE_API}/get-data-from-mongodb-to-train?id=${datasetID}`,
          {
            method: "POST",
            headers: { accept: "application/json" },
            body: "",
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
    } catch (err) {
      console.log(err);
      setError("Lỗi khi parse dữ liệu từ sessionStorage.");
    }
  }, [isClient]);

  // Gửi dataTrain và config tới API tiếp theo
  useEffect(() => {
    const trainModel = async () => {
      if (!dataTrain.length || !config || !session?.user?.id || !datasetID) {
        return;
      }

      // body gửi lên sv
      const requestBody = {
        id_data: datasetID,
        id_user: session.user.id,
        config: {
          choose: config.choose,
          metric_sort: config.metric_sort,
          list_feature: config.list_feature,
          target: config.target,
        },
      };

      setIsLoading(true);
      setError(null);

      // api 33 -> gửi dữ liệu lên tiến hành train
      try {
        console.log(JSON.stringify(requestBody));
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_BASE_API}/v2/auto/jobs/training`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              accept: "application/json",
            },
            body: JSON.stringify(requestBody),
          }
        );

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Lỗi API: ${response.status} - ${errorText}`);
        }

        const resultData = await response.json();
        setResult(resultData);
        setJobStatus(resultData.status || null);
      } catch (err: any) {
        console.log("Lỗi khi gọi API train:", err);
        setError(
          "Có lỗi xảy ra trong quá trình huấn luyện, vui lòng xem lại cấu hình thuộc tính."
        );
      } finally {
        setIsLoading(false);
      }
    };

    trainModel();
  }, [dataTrain, config]);

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen ">
        <Card className="w-full max-w-md shadow-md border border-red-300 bg-white">
          <CardHeader className="flex flex-row items-center gap-3 border-b border-red-100 pb-2">
            <AlertCircle className="text-red-500 w-5 h-5" />
            <CardTitle className="text-red-600 text-base font-semibold">
              Đã xảy ra lỗi
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            <p className="text-sm text-gray-700 leading-relaxed">{error}</p>
            <button
              onClick={() => router.back()}
              className="inline-block px-4 py-2 bg-blue-100 text-blue-600 text-sm rounded hover:bg-blue-200 transition"
            >
              ← Quay lại trang trước
            </button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="relative p-6">
      {/* Hiển thị loading bao trùm toàn màn hình */}
      {isLoading ? (
        <div className="fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2">
          <Card className="w-[360px] bg-white shadow-2xl rounded-3xl border-0">
            <CardContent className="flex items-center gap-4 p-6 text-blue-700">
              <LoaderCircle className="h-6 w-6 animate-spin text-blue-700" />
              <span className="text-base font-semibold tracking-wide">
                Đang tải dữ liệu vào hàng chờ...
              </span>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-[#0f0f0f]">
          <Card className="w-full max-w-md bg-white dark:bg-[#171717] border border-green-200 dark:border-green-800 shadow-lg rounded-xl">
            <CardHeader className="flex items-center gap-3 border-b border-green-100 dark:border-green-800 py-3 px-4">
              <CheckCircle className="text-green-500 w-5 h-5" />
              <CardTitle className="text-green-600 dark:text-green-400 text-base font-semibold">
                Đã tải dữ liệu vào hàng chờ thành công
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 py-5 px-4">
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                {error}
              </p>
              <button
                onClick={() => {
                  router.push("/training-history");
                }}
                className="w-full text-center py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded-md transition duration-200"
              >
                ← Về trang lịch sử huấn luyện
              </button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ResultPage;
