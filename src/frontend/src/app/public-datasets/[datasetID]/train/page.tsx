"use client";

import { useEffect, useState } from "react";
import TrainCard from "@/components/publicDatasetUser/TrainCard";
import { useParams } from "next/navigation";
import { useApi } from "@/hooks/useApi";

export default function Page() {
  const { get } = useApi();

  const params = useParams();
  const datasetID = Array.isArray(params?.datasetID)
    ? params.datasetID[0]
    : params?.datasetID;

  const [dataName, setDataName] = useState<string>("Đang tải...");

  useEffect(() => {
    sessionStorage.clear();

    // 31. Lấy dữ liệu dataset theo datasetID chọn
    const fetchData = async () => {
      try {
        const data = await get(`/get-data-info?id=${datasetID}`);

        setDataName(data.dataName || "Không rõ");
      } catch (error) {
        console.error("Lỗi lấy dữ liệu:", error);
        setDataName("Không thể tải tên bộ dữ liệu");
      }
    };

    if (datasetID) {
      fetchData();
    }
  }, [datasetID]);

  return datasetID ? (
    <TrainCard datasetID={datasetID} datasetName={dataName} />
  ) : (
    <div>Không tìm thấy ID dataset</div>
  );
}
