import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import axios from "axios";

interface DataTrainState {
  trainData: any; 
  listFeature: string[];
  selectedTarget: string | null; 
  status: "idle" | "loading" | "succeeded" | "failed"; 
  error: string | null; 
}

const initialState: DataTrainState = {
  trainData: null,
  listFeature: [],
  selectedTarget: null,
  status: "idle",
  error: null,
};

// Async Thunk cho việc lấy dữ liệu từ API
export const fetchTrainData = createAsyncThunk(
  "dataTrain/fetchTrainData",
  async (datasetID: string, thunkAPI) => {
    try {
      // Thực hiện gọi API để lấy dữ liệu
      const response = await axios.post(
        `http://10.100.200.119:9999/get-data-from-mongodb-to-train?id=${datasetID}`
      );
      return response.data;
    } catch (error: any) {
      const message = error.response?.data?.message || "Lỗi khi lấy dữ liệu huấn luyện";
      return thunkAPI.rejectWithValue(message);
    }
  }
);

const dataTrainSlice = createSlice({
  name: "dataTrain",
  initialState,
  reducers: {
    setSelectedTarget: (state, action) => {
      state.selectedTarget = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchTrainData.pending, (state) => {
        state.status = "loading"; 
        state.error = null;
      })
      .addCase(fetchTrainData.fulfilled, (state, action) => {
        state.status = "succeeded"; 
        state.trainData = action.payload.data; 
        state.listFeature = action.payload.list_feature; 
      })
      .addCase(fetchTrainData.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload as string;
      });
  },
});

export const { setSelectedTarget } = dataTrainSlice.actions;

export default dataTrainSlice.reducer;
