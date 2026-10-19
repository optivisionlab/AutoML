"use client";

import { useSession } from "next-auth/react";
import TrainingWizard from "@/features/training/components/wizard/TrainingWizard";

interface TrainMyDataCardProps {
  datasetID?: string;
  datasetName: string;
}

const TrainMyDataCard = ({ datasetID, datasetName }: TrainMyDataCardProps) => {
  const { data: session } = useSession();
  const backHref =
    session?.user?.role === "admin" ? "/admin/datasets/users" : "/my-datasets";

  return (
    <TrainingWizard
      datasetID={datasetID}
      datasetName={datasetName}
      backHref={backHref}
      resultHref={`/my-datasets/${datasetID}/result`}
      initialChoose="new_model"
      featureErrorMessage="Không tìm thấy bộ dữ liệu."
    />
  );
};

export default TrainMyDataCard;

