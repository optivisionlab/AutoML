"use client";

import { memo } from "react";
import { TableRow, TableCell } from "@/components/ui/table";
import { useRouter } from "next/navigation";
import DatasetActions from "./DatasetAction";

export type Dataset = {
  _id: string;
  dataName: string;
  dataType: string;
  createDate: number;
  latestUpdate?: number;
  lastestUpdate?: number;
  username: string;
};

type Props = {
  dataset: Dataset;
  onEdit: (dataset: Dataset) => void;
  onDelete: (id: string) => void;
};

const formatDate = (timestamp?: number) => {
  if (!timestamp) return "Không có dữ liệu";
  return new Date(timestamp * 1000).toLocaleDateString("vi-VN");
};

const DatasetRow = ({ dataset, onEdit, onDelete }: Props) => {
  const router = useRouter();

  return (
    <TableRow className="hover:bg-muted/50 transition">
      <TableCell className="py-3 px-4 font-medium text-gray-800">
        {dataset.dataName || "Không có tên"}
      </TableCell>
      <TableCell className="py-3 px-4 text-gray-700">
        {dataset.dataType || "Chưa rõ"}
      </TableCell>
      <TableCell className="py-3 px-4 text-gray-600">
        {formatDate(dataset.createDate)}
      </TableCell>
      <TableCell className="py-3 px-4 text-gray-600">
        {formatDate(dataset.latestUpdate || dataset.lastestUpdate)}
      </TableCell>
      <TableCell className="py-3 px-4 text-gray-700">
        {dataset.username}
      </TableCell>
      <TableCell className="py-3 px-4 text-center space-x-2">
        <TableCell className="py-3 px-4 text-center">
          <DatasetActions
            datasetId={dataset._id}
            onEdit={() => onEdit(dataset)}
            onDelete={() => onDelete(dataset._id)}
          />
        </TableCell>
      </TableCell>
    </TableRow>
  );
};

export default memo(DatasetRow);
