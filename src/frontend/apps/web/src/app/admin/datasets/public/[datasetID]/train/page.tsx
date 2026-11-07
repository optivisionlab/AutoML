"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import TrainCard from "@/features/training/components/cards/TrainCard";
import { useGetDatasetInfoQuery } from "@/core/api/datasetApi";

export default function Page() {
  const params = useParams();
  const datasetID = Array.isArray(params?.datasetID)
    ? params.datasetID[0]
    : params?.datasetID;
  const { data, isError } = useGetDatasetInfoQuery(datasetID ?? "", {
    skip: !datasetID,
  });
  const dataName = isError
    ? "Không thể tải tên bộ dữ liệu"
    : data?.data?.dataName || (data as any)?.dataName || "Đang tải...";

  useEffect(() => {
    sessionStorage.clear();
  }, []);

  return datasetID ? (
    <div className="w-full min-h-[calc(100svh-7.5rem)] flex flex-col">
      <TrainCard datasetID={datasetID} datasetName={dataName} />
    </div>
  ) : (
    <div className="w-full min-h-[calc(100svh-7.5rem)] flex flex-col items-center justify-center p-6">
      <div className="text-sm font-bold text-slate-500">Không tìm thấy ID dataset</div>
    </div>
  );
}
