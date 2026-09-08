import { AxiosInstance } from "axios";
import { Dataset, DatasetFormPayload } from "@automl/domain";
import { buildDatasetFormData } from "../form-data";

export const createDatasetService = (client: AxiosInstance) => ({
  getDatasetsByUserId: async (id: string): Promise<Dataset[]> => {
    const res = await client.post<Dataset[]>("/get-list-data-by-userid", null, {
      params: { id },
    });
    return res.data;
  },

  getDatasetInfo: async (id: string): Promise<Dataset> => {
    const res = await client.get<Dataset>("/get-data-info", {
      params: { id },
    });
    return res.data;
  },

  getAllUserDatasets: async (): Promise<Dataset[]> => {
    const res = await client.get<Dataset[]>("/get-list-data-user");
    return res.data;
  },

  getDataFromUci: async (idData: number): Promise<unknown> => {
    const res = await client.post("/get-data-from-uci", null, {
      params: { id_data: idData },
    });
    return res.data;
  },

  uploadDataset: async (payload: DatasetFormPayload): Promise<unknown> => {
    const formData = buildDatasetFormData(payload);
    const res = await client.post("/upload-dataset", formData, {
      params: { user_id: payload.userId },
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },

  updateDataset: async (payload: DatasetFormPayload): Promise<unknown> => {
    const formData = buildDatasetFormData(payload);
    const res = await client.put(`/update-dataset/${payload.datasetId}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },

  deleteDataset: async (datasetId: string): Promise<unknown> => {
    const res = await client.delete(`/delete-dataset/${datasetId}`);
    return res.data;
  },
});
