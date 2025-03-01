import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import axios from "axios";

interface UserState {
  user: IUser | null;
  status: "idle" | "loading" | "succeeded" | "failed";
  error: string | null;
}

const initialState: UserState = {
  user: null,
  status: "idle",
  error: null,
};

export const registerAsync = createAsyncThunk(
  "register",
  async (payload: IUser, thunkAPI) => {
    try {
      const response = await axios.post(
        `http://127.0.0.1:9999/signup`,
        payload
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return thunkAPI.rejectWithValue(
          error.response?.data || "An unexpected error just happened"
        );
      }
      console.error("NETWORK ERROR:", error);
      return thunkAPI.rejectWithValue("NETWORK ERROR or unexpected error");
    }
  }
);

const registerSlice = createSlice({
  name: "register",
  initialState,
  reducers: {},
  extraReducers(builder) {
    builder
      .addCase(registerAsync.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(registerAsync.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.user = action.payload;
      })
      .addCase(registerAsync.rejected, (state, action) => {
        state.status = "failed";
        state.error = action?.error?.message ?? "Failed to register";
      });
  },
});

export default registerSlice.reducer;
