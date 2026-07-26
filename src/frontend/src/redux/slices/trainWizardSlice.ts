import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { FeatureMap, MetricMap } from "@/redux/api/automlApi";

type TrainWizardState = {
  step: number;
  selectedOption: string;
  method: string;
  problemType: string;
  selectedTarget: string;
  selectedFeatures: string[];
  listFeature: FeatureMap;
  metrics: MetricMap;
};

const initialState: TrainWizardState = {
  step: 1,
  selectedOption: "",
  method: "",
  problemType: "",
  selectedTarget: "",
  selectedFeatures: [],
  listFeature: {},
  metrics: {},
};

const trainWizardSlice = createSlice({
  name: "trainWizard",
  initialState,
  reducers: {
    setStep: (state, action: PayloadAction<number>) => {
      state.step = action.payload;
    },
    setSelectedOption: (state, action: PayloadAction<string>) => {
      state.selectedOption = action.payload;
    },
    setMethod: (state, action: PayloadAction<string>) => {
      state.method = action.payload;
    },
    setProblemType: (state, action: PayloadAction<string>) => {
      state.problemType = action.payload;
    },
    setSelectedTarget: (state, action: PayloadAction<string>) => {
      state.selectedTarget = action.payload;
      state.selectedFeatures = state.selectedFeatures.filter(
        (feature) => feature !== action.payload,
      );
    },
    setSelectedFeatures: (state, action: PayloadAction<string[]>) => {
      state.selectedFeatures = action.payload;
    },
    setListFeature: (state, action: PayloadAction<FeatureMap>) => {
      state.listFeature = action.payload;
    },
    setMetrics: (state, action: PayloadAction<MetricMap>) => {
      state.metrics = action.payload;
    },
    resetTrainWizard: () => initialState,
  },
});

export const {
  resetTrainWizard,
  setListFeature,
  setMethod,
  setMetrics,
  setProblemType,
  setSelectedFeatures,
  setSelectedOption,
  setSelectedTarget,
  setStep,
} = trainWizardSlice.actions;

export default trainWizardSlice.reducer;
