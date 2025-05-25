"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import TrainCard from "@/components/publicDatasetUser/TrainCard";

export default function Page() {
  const params = useParams();
  const datasetID = Array.isArray(params?.datasetID)
    ? params.datasetID[0]
    : params?.datasetID;

  const [dataName, setDataName] = useState<string>("Đang tải...");

  useEffect(() => {
    sessionStorage.clear();
    
    const fetchData = async () => {
      try {
        const res = await fetch(
          `http://10.100.200.119:9999/get-data-info?id=${datasetID}`,
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
        console.log("Lỗi lấy dữ liệu:", error);
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