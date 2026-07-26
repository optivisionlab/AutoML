import { datasetApi } from "@/redux/api/datasetApi";
import type { AppStartListening } from "./index";

export const addDatasetListeners = (startListening: AppStartListening) => {
  startListening({
    matcher: datasetApi.endpoints.uploadDataset.matchFulfilled,
    effect: async () => {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("dataset:changed"));
      }
    },
  });
};
