import { baseApi } from "@/redux/api/baseApi";
import { authApi } from "@/redux/api/authApi";
import type { AppStartListening } from "./index";

export const addAuthListeners = (startListening: AppStartListening) => {
  startListening({
    matcher: authApi.endpoints.registerUser.matchFulfilled,
    effect: async (_action, listenerApi) => {
      listenerApi.dispatch(baseApi.util.invalidateTags(["Auth", "User"]));
    },
  });
};
