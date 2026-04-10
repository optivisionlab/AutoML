import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import axiosClient from "@/api/axiosClient";

type FeatureMap = Record<string, boolean>;

interface DataTrainState {
  // trainData: any;
  listFeature: FeatureMap;
  selectedTarget: string | null;
  status: "idle" | "loading" | "succeeded" | "failed";
  error: string | null;
}

const initialState: DataTrainState = {
  // trainData: null,
  listFeature: {},
  selectedTarget: null,
  status: "idle",
  error: null,
};

// Async Thunk cho việc lấy dữ liệu từ API
export const fetchTrainData = createAsyncThunk(
  "dataTrain/fetchTrainData",
  async ({ datasetID, problemType }: { datasetID: string; problemType: string }, thunkAPI) => {
    try {
      // Thực hiện gọi API để lấy dữ liệu
      const response = await axiosClient.get(
        `/v2/auto/features?id_data=${datasetID}&problem_type=${problemType}`
      );
      return response.data;
    } catch (error: any) {
      const message =
        error.response?.data?.detail ||
        error.response?.data?.message || "Lỗi khi lấy dữ liệu huấn luyện";
      return thunkAPI.rejectWithValue(message);
    }
  }
);

const dataTrainSlice = createSlice({
  name: "dataTrain",
  initialState,
  reducers: {
    setSelectedTarget: (state, action: PayloadAction<string | null>) => {
      state.selectedTarget = action.payload;
    },
    resetTrainState: (state) => {
      state.listFeature = {};
      state.selectedTarget = null;
      state.status = "idle";
      state.error = null;
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchTrainData.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(fetchTrainData.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.listFeature = action.payload.features || {}; 
      })
      .addCase(fetchTrainData.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload as string;
      });
  },
});

export const { setSelectedTarget, resetTrainState } = dataTrainSlice.actions;

export default dataTrainSlice.reducer;

