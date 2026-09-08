import { UniversalFile } from "./common.types";

export type PredictionFile = {
  blob: Blob;
  fileName: string;
};

export type InferencePayload = {
  jobId: string;
  file: UniversalFile;
};

export type ActivateModelPayload = {
  jobId: string;
  activate?: 0 | 1;
};
