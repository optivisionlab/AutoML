import { UniversalFile, DatasetUploadPayload, DatasetUpdatePayload } from "@automl/domain";

/**
 * Appends a file to FormData in a way that works seamlessly
 * on both Web (Browser File/Blob) and Mobile (React Native { uri, name, type }).
 */
export const appendUniversalFile = (
  formData: FormData,
  fieldName: string,
  file: UniversalFile
): void => {
  (formData as unknown as { append: (name: string, value: unknown, fileName?: string) => void }).append(
    fieldName,
    file as unknown as Blob
  );
};

export const buildDatasetUploadFormData = (payload: DatasetUploadPayload): FormData => {
  const formData = new FormData();

  if (payload.file) {
    appendUniversalFile(formData, "file", payload.file);
  }
  if (payload.dataName) {
    formData.append("dataName", payload.dataName);
  }
  if (payload.dataType) {
    formData.append("dataType", payload.dataType);
  }
  if (payload.description !== undefined && payload.description !== null) {
    formData.append("description", payload.description);
  }
  if (payload.public !== undefined) {
    formData.append("public", String(payload.public));
  }
  if (payload.thumbnail_file) {
    appendUniversalFile(formData, "thumbnail_file", payload.thumbnail_file);
  }

  return formData;
};

export const buildDatasetUpdateFormData = (payload: DatasetUpdatePayload): FormData => {
  const formData = new FormData();

  if (payload.dataName) {
    formData.append("dataName", payload.dataName);
  }
  if (payload.description !== undefined && payload.description !== null) {
    formData.append("description", payload.description);
  }
  if (payload.public !== undefined) {
    formData.append("public", String(payload.public));
  }
  if (payload.thumbnail_file) {
    appendUniversalFile(formData, "thumbnail_file", payload.thumbnail_file);
  }

  return formData;
};

// Legacy compatibility
export const buildDatasetFormData = (payload: any): FormData => {
  const formData = new FormData();
  if (payload.dataName || payload.data_name) {
    formData.append("dataName", payload.dataName || payload.data_name);
  }
  if (payload.dataType || payload.data_type) {
    formData.append("dataType", payload.dataType || payload.data_type);
  }
  if (payload.description) {
    formData.append("description", payload.description);
  }
  if (payload.public !== undefined) {
    formData.append("public", String(payload.public));
  }
  if (payload.file || payload.file_data) {
    appendUniversalFile(formData, "file", (payload.file || payload.file_data) as UniversalFile);
  }
  if (payload.thumbnail_file) {
    appendUniversalFile(formData, "thumbnail_file", payload.thumbnail_file as UniversalFile);
  }
  return formData;
};
