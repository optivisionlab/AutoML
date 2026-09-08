/**
 * Universal file type supporting both browser Web (File, Blob)
 * and React Native / Mobile file descriptors ({ uri, name, type }).
 */
export type UniversalFile =
  | Blob
  | {
      uri: string;
      name?: string;
      type?: string;
    };

export type ApiMessageResponse = {
  detail?: string;
  message?: string;
  password?: string;
};

export type ApiErrorData = {
  status?: number;
  data: unknown;
};
