import AvailableDataset from "@/components/availableDataset/AvailableDataset";
import React from "react";

const DataSetPage = () => {
  const datasetSample = [
    {
      id: "001",
      dataName: "iris data",
      dataType: "table",
      role: "Admin",
      dataFile: "iris.data.csv",
      lastestUpdate: "2021-09-01",
      createdDate: "2021-09-01",
      attributes: [
        "sepal_length",
        "sepal_width",
        "petal_length",
        "petal_width",
      ],
      target: "class",
    },
    {
      id: "002",
      dataName: "flowers_datasets",
      dataType: "image",
      role: "Admin",
      dataFile: "flowers_datasets.zip",
      lastestUpdate: "2021-09-01",
      createdDate: "2021-09-01",
      attributes: [
        "sepal_length",
        "sepal_width",
        "petal_length",
        "petal_width",
      ],
      target: "class",
    },
  ];

  return (
    <>
      <h2 className="text-red-700 text-xl">Bộ dữ liệu</h2>
      <div className="mb-100">
        <AvailableDataset datasets={datasetSample} />
      </div>
    </>
  );
};

export default DataSetPage;
