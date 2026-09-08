import { automlApi } from "@/core/api/automlApi";
import type { AppStartListening } from "./index";

export const addTrainingListeners = (startListening: AppStartListening) => {
  startListening({
    matcher: automlApi.endpoints.startTrainingJob.matchFulfilled,
    effect: async (action) => {
      if (typeof window !== "undefined" && action.payload.job_id) {
        sessionStorage.setItem("latest_training_job_id", action.payload.job_id);
      }
    },
  });
};
