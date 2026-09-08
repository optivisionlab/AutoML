# HAutoML Mobile

Thư mục này dành cho ứng dụng di động trong tương lai của HAutoML.

## Ngăn Xếp Công Nghệ Đề Xuất (Recommended Tech Stack)

- **Framework**: React Native với Expo (SDK mới nhất).
- **Ngôn ngữ**: TypeScript.
- **Tái sử dụng tầng dùng chung**:
  - DTOs / Types / Schemas từ `@automl/domain` (nằm trong `packages/domain`).
  - Universal API Client & Pure Services từ `@automl/api` (nằm trong `packages/api`).
- **Lưu trữ bảo mật Auth**: `expo-secure-store`.

## Hướng Dẫn Tái Sử Dụng API Từ `@automl/api` & `@automl/domain`

Lớp API dùng chung đã được thiết kế hoàn toàn độc lập với web browser và `next-auth/react`. Mobile có thể tích hợp dễ dàng như sau:

### 1. Khởi Tạo API Client Cho Mobile

```typescript
// apps/mobile/src/services/api.ts
import {
  createApiClient,
  createAuthService,
  createDatasetService,
  createAutoMLService,
  createJobService,
  createUserService,
  createInferenceService,
} from "@automl/api";
import * as SecureStore from "expo-secure-store";

// Base URL có thể lấy từ biến môi trường của Expo (EXPO_PUBLIC_BASE_API)
// hoặc cấu hình động để test mạng LAN với máy dev (ví dụ: http://192.168.1.50:8000)
const BASE_URL = process.env.EXPO_PUBLIC_BASE_API || "http://10.0.2.2:8000";

export const mobileApiClient = createApiClient({
  baseUrl: () => BASE_URL,
  getToken: async () => {
    return await SecureStore.getItemAsync("access_token");
  },
});

// Khởi tạo các services cho mobile
export const authService = createAuthService(mobileApiClient);
export const datasetService = createDatasetService(mobileApiClient);
export const automlService = createAutoMLService(mobileApiClient);
export const jobService = createJobService(mobileApiClient);
export const userService = createUserService(mobileApiClient);
export const inferenceService = createInferenceService(mobileApiClient);
```

### 2. Sử Dụng Các Types & Services Trong Screen Hoặc Hook

```typescript
// apps/mobile/src/screens/DatasetsScreen.tsx
import React, { useEffect, useState } from "react";
import { View, Text, FlatList } from "react-native";
import { datasetService } from "../services/api";
import type { Dataset } from "@automl/domain";

export const DatasetsScreen = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);

  useEffect(() => {
    const fetchDatasets = async () => {
      try {
        const data = await datasetService.getAllUserDatasets();
        setDatasets(data);
      } catch (error) {
        console.error("Lỗi khi tải datasets:", error);
      }
    };
    fetchDatasets();
  }, []);

  return (
    <View>
      <FlatList
        data={datasets}
        keyExtractor={(item) => item._id}
        renderItem={({ item }) => <Text>{item.dataName}</Text>}
      />
    </View>
  );
};
```

### 3. Upload Tệp Từ Mobile (Universal File Descriptor)

Khi upload dataset hoặc avatar từ mobile (ví dụ qua `expo-document-picker` hoặc `expo-image-picker`), truyền descriptor theo chuẩn:

```typescript
await datasetService.uploadDataset({
  userId: "user_123",
  dataName: "Mobile_Dataset",
  dataType: "tabular",
  file: {
    uri: asset.uri,
    name: asset.name,
    type: asset.mimeType,
  },
});
```
Hàm `buildDatasetFormData` và `appendUniversalFile` trong `@automl/api` sẽ tự động xử lý tương thích với `FormData` của React Native.
