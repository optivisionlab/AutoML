import { UniversalFile } from "./common.types";

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

export type DatasetFormPayload = {
  userId?: string;
  datasetId?: string;
  dataName?: string;
  dataType?: string;
  file?: UniversalFile | null;
};
