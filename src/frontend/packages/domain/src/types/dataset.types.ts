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

export type ConnectDBPayload = {
  db_type: string;
  database: string;
  host?: string;
  port?: number | null;
  user?: string;
  password?: string;
  schema_name?: string;
  extra_params?: Record<string, unknown>;
};

export type ConnectDBResponse = {
  success: boolean;
  message: string;
  tables: string[];
};

export type ImportDatabaseTablePayload = {
  db_type: string;
  database: string;
  table_name: string;
  data_name: string;
  host?: string;
  port?: number | null;
  user?: string;
  password?: string;
  schema_name?: string;
  extra_params?: Record<string, unknown>;
};

export type ImportDatabaseTableResponse = {
  success: boolean;
  message: string;
  dataset?: Record<string, unknown>;
};
