"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useEffect, useRef, useState } from "react";
import { AlertCircle, CheckCircle } from "lucide-react";
import { useSession } from "next-auth/react";
import React from "react";
import { useStartTrainingJobMutation } from "@/redux/api/automlApi";
import { getApiErrorMessage } from "@/redux/api/baseApi";
import AppLoading from "@/components/common/AppLoading";
import BackButton from "@/components/common/BackButton";
import { useTranslations } from "next-intl";

type Props = {
  params: Promise<{
    datasetID: string;
  }>;
};

const ResultPage = ({ params }: Props) => {
  const common = useTranslations("Common");
  const [startTrainingJob, { isLoading }] = useStartTrainingJobMutation();
  const hasSubmittedRef = useRef(false);

  const [datasetID, setDatasetID] = useState<string | null>(null);
  const [config, setConfig] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);
  const [isPending, setIsPending] = useState(true);
  const { data: session } = useSession();

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

  // Lấy cấu hình từ sessionStorage và chuẩn bị config
  useEffect(() => {
    if (!isClient) return;

    try {
      const choose = sessionStorage.getItem("choose");
      const metric_sort = sessionStorage.getItem("metric_sort");
      const target = sessionStorage.getItem("target");
      const method = sessionStorage.getItem("method");
      const listFeatureString = sessionStorage.getItem("list_feature");
      const problemType = sessionStorage.getItem("problem_type");

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
        problemType
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
      // Kiểm tra đầy đủ trước khi gọi API

      if (!config || !session?.user?.id || !datasetID || hasSubmittedRef.current) {
        return;
      }
      hasSubmittedRef.current = true;

      // body gửi lên sv
      const requestBody = {
        id_data: datasetID,
        id_user: session.user.id,
        config: {
          choose: config.choose,
          metric_sort: config.metric_sort,
          list_feature: config.list_feature,
          target: config.target,
          problem_type: config.problemType
        },
      };

      setIsPending(true);
      setError(null); // Reset lỗi trước khi gọi mới

      try {
        await startTrainingJob(requestBody).unwrap();
      } catch (err: any) {
        console.log("Lỗi khi gọi API train:", err);
        setError(
          getApiErrorMessage(
            err,
            "Có lỗi xảy ra khi huấn luyện mô hình, vui lòng xem lại cấu hình thuộc tính.",
          ),
        );
      } finally {
        setIsPending(false);
      }
    };

    trainModel();
  }, [config, session?.user?.id, datasetID, startTrainingJob]);

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
            <BackButton
              fallbackHref="/my-datasets"
              label={common("backToPrevious")}
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="relative p-6">
      {/* Hiển thị loading bao trùm toàn màn hình */}
      {isPending || isLoading ? (
<AppLoading variant="page" label="Đang tải dữ liệu vào hàng chờ..." />
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
              <BackButton
                fallbackHref="/training-history"
                label={common("backToTrainingHistory")}
                variant="primary"
                className="w-full justify-center"
              />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ResultPage;
