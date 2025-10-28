"use client";

import { memo } from "react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

type Props = {
  datasetId: string;
  onEdit: () => void;
  onDelete: () => void;
};

const DatasetActions = ({ datasetId, onEdit, onDelete }: Props) => {
  const router = useRouter();

  return (
    <div className="flex justify-center gap-2">
      <Button
        className="bg-[#3a6df4] hover:bg-[#5b85f7] text-white text-sm px-4 py-2 rounded-md"
        onClick={() => router.push(`/my-datasets/${datasetId}/train`)}
      >
        Huấn luyện
      </Button>
      <Button
        className="bg-yellow-500 hover:bg-yellow-600 text-white text-sm px-4 py-2 rounded-md"
        onClick={onEdit}
      >
        Sửa
      </Button>
      <Button
        className="bg-red-500 hover:bg-red-600 text-white text-sm px-4 py-2 rounded-md"
        onClick={onDelete}
      >
        Xoá
      </Button>
    </div>
  );
};

// memo tránh re-render khi props không thay đổi
export default memo(DatasetActions);
