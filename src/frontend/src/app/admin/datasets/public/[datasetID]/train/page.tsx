"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import TrainCard from "@/components/publicDatasetUser/TrainCard";
import { useGetDatasetInfoQuery } from "@/redux/api/datasetApi";
import BackButton from "@/components/common/BackButton";

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
    <div className="space-y-4">
      <BackButton fallbackHref="/admin/datasets/public" />
      <TrainCard datasetID={datasetID} datasetName={dataName} />
    </div>
  ) : (
    <div className="space-y-4">
      <BackButton fallbackHref="/admin/datasets/public" />
      <div>Không tìm thấy ID dataset</div>
    </div>
  );
}
