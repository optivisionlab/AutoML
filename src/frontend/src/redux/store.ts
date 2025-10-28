import { configureStore } from '@reduxjs/toolkit';
import registerSlice from "./slices/registerSlice";
import dataTrainSlice from "./slices/dataTrainSlice";
import getDataUCISlice from "./slices/dataUCISlice";

export const store = configureStore({
  reducer: {
    register: registerSlice,
    dataTrain: dataTrainSlice, 
    getDataUCI: getDataUCISlice,
  },
})

// lấy kiểu dispatch từ store
export type AppDispatch = typeof store.dispatch;

// lấy kiểu state từ store
export type RootState = ReturnType<typeof store.getState>;