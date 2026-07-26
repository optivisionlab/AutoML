"use client";

import { memo } from "react";
import { useRouter } from "next/navigation";
import RowActionMenu from "@/components/common/RowActionMenu";

type Props = {
  datasetId: string;
  onEdit: () => void;
  onDelete: () => void;
};

const DatasetActions = ({ datasetId, onEdit, onDelete }: Props) => {
  const router = useRouter();

  return (
    <div className="flex justify-center">
      <RowActionMenu
        label="Mở tác vụ bộ dữ liệu"
        items={[
          {
            label: "Huấn luyện",
            onClick: () => router.push(`/my-datasets/${datasetId}/train`),
          },
          { label: "Sửa", onClick: onEdit },
          { label: "Xoá", onClick: onDelete, destructive: true },
        ]}
      />
    </div>
  );
};

export default memo(DatasetActions);
