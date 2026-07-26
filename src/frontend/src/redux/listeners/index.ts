import { createListenerMiddleware } from "@reduxjs/toolkit";
import type { TypedStartListening } from "@reduxjs/toolkit";
import type { AppDispatch, RootState } from "@/redux/store";
import { addAuthListeners } from "./auth.listener";
import { addDatasetListeners } from "./dataset.listener";
import { addTrainingListeners } from "./training.listener";

export const listenerMiddleware = createListenerMiddleware();

export type AppStartListening = TypedStartListening<RootState, AppDispatch>;

const startAppListening =
  listenerMiddleware.startListening as AppStartListening;

addAuthListeners(startAppListening);
addDatasetListeners(startAppListening);
addTrainingListeners(startAppListening);
