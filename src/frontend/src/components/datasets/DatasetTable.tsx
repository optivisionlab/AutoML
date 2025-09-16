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
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <th>Tên bộ dữ liệu</th>
          <th>Kiểu dữ liệu</th>
          <th>Ngày tạo</th>
          <th>Lần cập nhật mới nhất</th>
          <th className="text-center">Người dùng</th>
          <th className="text-center">Chức năng</th>
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
