import { automlApi } from "@/core/api/automlApi";
import type { AppStartListening } from "./index";

export const addTrainingListeners = (startListening: AppStartListening) => {
  startListening({
    matcher: automlApi.endpoints.startTrainingJob.matchFulfilled,
    effect: async (action) => {
      const payload: any = action.payload;
      const jobId = payload?.data?.job_id || payload?.job_id;
      if (typeof window !== "undefined" && jobId) {
        sessionStorage.setItem("latest_training_job_id", jobId);
      }
    },
  });
};
