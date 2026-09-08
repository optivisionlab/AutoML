import { UniversalFile, DatasetFormPayload } from "@automl/domain";

/**
 * Appends a file to FormData in a way that works seamlessly
 * on both Web (Browser File/Blob) and Mobile (React Native { uri, name, type }).
 */
export const appendUniversalFile = (
  formData: FormData,
  fieldName: string,
  file: UniversalFile
): void => {
  // In React Native, FormData accepts an object with uri, name, and type:
  // formData.append(name, { uri, name, type } as any);
  // In web browsers, FormData accepts a Blob or File.
  (formData as unknown as { append: (name: string, value: unknown, fileName?: string) => void }).append(
    fieldName,
    file as unknown as Blob
  );
};

export const buildDatasetFormData = ({
  dataName,
  dataType,
  file,
}: DatasetFormPayload): FormData => {
  const formData = new FormData();

  if (dataName) formData.append("data_name", dataName);
  if (dataType) formData.append("data_type", dataType);
  if (file) appendUniversalFile(formData, "file_data", file);

  return formData;
};
