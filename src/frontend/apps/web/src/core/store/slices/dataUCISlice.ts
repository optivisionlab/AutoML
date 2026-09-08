import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import axios from "axios";

interface UCIDataState {
  dataUCI: any; 
  status: "idle" | "loading" | "succeeded" | "failed";
  error: string | null;
}

const initialState: UCIDataState = {
  dataUCI: null,
  status: "idle",
  error: null,
};

// Async Thunk for fetching data from UCI by POST method
export const getDataUCIAsync = createAsyncThunk(
  "uciData/getData",
  async (_, thunkAPI) => {
    try {
      const response = await axios.post(`${process.env.NEXT_PUBLIC_BASE_API}/get-data-from-uci?id_data=53`);
      return response.data;
    } catch (error: any) {
      const message = error.response?.data?.message || "Lỗi khi lấy dữ liệu UCI";
      return thunkAPI.rejectWithValue(message);
    }
  }
);

const uciSlice = createSlice({
  name: "uciData",
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(getDataUCIAsync.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(getDataUCIAsync.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.dataUCI = action.payload;
      })
      .addCase(getDataUCIAsync.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload as string;
      });
  },
});

export default uciSlice.reducer;
