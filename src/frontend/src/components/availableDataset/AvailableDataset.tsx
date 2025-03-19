"use client";
import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Link from "next/link";

interface Dataset {
  id: string;
  dataName: string;
  dataType: string;
  role: string;
  dataFile: string;
  lastestUpdate: string;
  createdDate: string;
  attributes: string[];
  target: string;
}

interface AvailableDatasetProps {
  datasets: Dataset[];
}

const AvailableDataset: React.FC<AvailableDatasetProps> = ({ datasets }) => {
  // const [datasetID, setDatasetID] = useState<string>('001');

  // console.log(datasets);

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[100px]">ID</TableHead>
            <TableHead>Tên bộ dữ liệu</TableHead>
            <TableHead>Kiểu dữ liệu</TableHead>
            <TableHead className="text-right">Chức năng</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {datasets.map((dataset) => (
            <TableRow key={dataset.id}>
              <TableCell className="font-medium">{dataset.id}</TableCell>
              <TableCell>{dataset.dataName}</TableCell>
              <TableCell>{dataset.dataType}</TableCell>
              <TableCell className="text-right">
                <Link
                  className="hover:text-violet-500"
                  href={`/datasets/${dataset.id}/training-model`}
                >
                  Huấn luyện
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
};

export default AvailableDataset;
