"use client";

import { useEffect } from "react";
import TrainCard from "@/features/training/components/cards/TrainCard";
import { useParams } from "next/navigation";
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
    : data?.dataName || "Đang tải...";

  useEffect(() => {
    sessionStorage.clear();
  }, []);

  return datasetID ? (
    <div className="h-[calc(100svh-8rem)] min-h-[580px]">
      <TrainCard datasetID={datasetID} datasetName={dataName} />
    </div>
  ) : (
    <div className="h-[calc(100svh-8rem)] min-h-[580px]">
      <div>Không tìm thấy ID dataset</div>
    </div>
  );
}
