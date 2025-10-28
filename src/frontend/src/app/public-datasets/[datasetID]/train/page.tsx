"use client";

import { useEffect, useState } from "react";
import TrainCard from "@/components/publicDatasetUser/TrainCard";
import { useParams } from "next/navigation";

export default function Page() {
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
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_BASE_API}/get-data-info?id=${datasetID}`,
          {
            method: "POST",
            headers: {
              Accept: "application/json",
            },
            body: "",
            cache: "no-store",
          }
        );

        if (!res.ok) throw new Error("Lỗi khi gọi API");

        const data = await res.json();
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
