"use client";

import TrainingWizard from "@/components/training/TrainingWizard";

interface TrainCardProps {
  datasetID?: string;
  datasetName: string;
}

const TrainCard = ({ datasetID, datasetName }: TrainCardProps) => (
  <TrainingWizard
    datasetID={datasetID}
    datasetName={datasetName}
    backHref="/public-datasets"
    resultHref={`/public-datasets/${datasetID}/result`}
  />
);

export default TrainCard;

