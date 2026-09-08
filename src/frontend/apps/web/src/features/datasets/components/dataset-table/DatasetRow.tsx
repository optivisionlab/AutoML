"use client";

import { memo } from "react";
import { TableRow, TableCell } from "@/shared/components/ui/table";
import DatasetActions from "./DatasetAction";

export type Dataset = {
  _id: string;
  dataName: string;
  dataType: string;
  createDate: number;
  latestUpdate?: number;
  lastestUpdate?: number;
  userId: string;
  username?: string;
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
  return (
    <TableRow tabIndex={0} className="transition-all outline-none">
      <TableCell className="font-bold text-[var(--automl-data-text)]">
        {dataset.dataName || "Không có tên"}
      </TableCell>
      <TableCell>{dataset.dataType || "Chưa rõ"}</TableCell>
      <TableCell>{formatDate(dataset.createDate)}</TableCell>
      <TableCell>{formatDate(dataset.latestUpdate || dataset.lastestUpdate)}</TableCell>
      <TableCell className="text-center">{dataset.username || "Hệ thống"}</TableCell>
      <TableCell className="text-center">
        <DatasetActions
          datasetId={dataset._id}
          onEdit={() => onEdit(dataset)}
          onDelete={() => onDelete(dataset._id)}
        />
      </TableCell>
    </TableRow>
  );
};

export default memo(DatasetRow);
