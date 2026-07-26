"use client";

import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import DatasetRow from "./DatasetRow";

import { Dataset } from "./DatasetRow";

type Props = {
  datasets: Dataset[];
  onEdit: (dataset: Dataset) => void;
  onDelete: (id: string) => void;
};

const DatasetTable = ({ datasets, onEdit, onDelete }: Props) => {
  if (datasets.length === 0) {
    return <div className="automl-state-panel">Không có bộ dữ liệu nào.</div>;
  }

  return (
    <Table className="automl-data-table">
      <TableHeader>
        <TableRow>
          <TableHead>Tên bộ dữ liệu</TableHead>
          <TableHead>Kiểu dữ liệu</TableHead>
          <TableHead>Ngày tạo</TableHead>
          <TableHead>Lần cập nhật mới nhất</TableHead>
          <TableHead className="text-center">Người dùng</TableHead>
          <TableHead className="text-center">Tác vụ</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {datasets.map((dataset) => (
          <DatasetRow
            key={dataset._id}
            dataset={dataset}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
      </TableBody>
    </Table>
  );
};

export default DatasetTable;
