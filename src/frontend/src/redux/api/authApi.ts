import { IUser } from "@/types/user/user.types";
import { baseApi } from "./baseApi";

type RegisterUserPayload = IUser;
type ApiMessageResponse = {
  detail?: string;
  message?: string;
  password?: string;
};

// Các api auth
export const authApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // API đăng ký tài khoản.
    // mutation<Response, Request>
    registerUser: builder.mutation<ApiMessageResponse, RegisterUserPayload>({
      /*
        payload là dữ liệu được truyền vào khi gọi:
        registerUser({email: "...", password: "...",})
       */
      query: (payload) => ({
        url: "/signup",
        method: "POST",
        // data <-> body vì dùng axios custom
        data: payload,
      }),

      /*
        Sau khi đăng ký thành công, đánh dấu cache Auth và User đã hết hạn.
        Các query đang providesTags tương ứng có thể được gọi lại để lấy dữ liệu mới.
       */

      // mutation này làm dữ liệu thuộc tag nào bị cũ.
      invalidatesTags: ["Auth", "User"],
    }),

    // API lấy thông tin người dùng đang đăng nhập.
    getCurrentUser: builder.query<ApiMessageResponse, void>({
      query: () => ({
        url: "/me",
      }),

      /*
        Dữ liệu trả về từ /me được gắn tag Auth.
        Khi một mutation invalidates tag Auth, query này có thể tự động fetch lại.
       */
      // query này cung cấp dữ liệu thuộc tag nào.
      providesTags: ["Auth"],
    }),

    // API yêu cầu gửi email đặt lại mật khẩu.
    forgotPassword: builder.mutation<ApiMessageResponse, { email: string }>({
      query: (payload) => ({
        url: "/forgot-password",
        method: "POST",
        data: payload,
      }),
    }),

    // API đặt lại mật khẩu.
    resetPassword: builder.mutation<ApiMessageResponse, unknown>({
      query: (payload) => ({
        url: "/reset-password",
        method: "POST",
        data: payload,
      }),
    }),

    // API xác thực mã OTP.
    verifyEmailToken: builder.mutation<ApiMessageResponse, { token: string }>({
      query: (payload) => ({
        url: "/auth/verifications",
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Auth"],
    }),

    resendVerificationEmail: builder.mutation<
      ApiMessageResponse,
      { email: string }
    >({
      query: (payload) => ({
        url: "/auth/token/verifications",
        method: "POST",
        data: payload,
      }),
    }),

    verifyOtp: builder.mutation<
      ApiMessageResponse,
      { email: string; otp: string }
    >({
      query: (payload) => ({
        url: "/auth/verify-otp",
        method: "POST",
        data: payload,
      }),
    }),

    sendOtpVerification: builder.mutation<ApiMessageResponse, { email: string }>({
      query: (payload) => ({
        url: "/auth/otp/verifications",
        method: "POST",
        data: payload,
      }),
    }),
  }),
});

export const {
  // use + ForgotPassword + Mutation
  useForgotPasswordMutation,
  useGetCurrentUserQuery,
  useRegisterUserMutation,
  useResendVerificationEmailMutation,
  useResetPasswordMutation,
  useSendOtpVerificationMutation,
  useVerifyEmailTokenMutation,
  useVerifyOtpMutation,
} = authApi;
