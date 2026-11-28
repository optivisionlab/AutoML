# `@automl/assets`

Thư viện tài nguyên media (hình ảnh, video) dùng chung cho cả **Web (`apps/web` - Next.js)** và **Mobile (`apps/mobile` - React Native / Expo)**.

## Cấu trúc thư mục

```txt
packages/assets/
  images/
    brand/           # Logo, wordmark, illustrations dùng chung
    achievements/    # Ảnh giải thưởng & hội nghị
    lab-carousel/    # Ảnh banner / carousel giới thiệu lab
    lab-members/     # Ảnh thành viên OptiVisionLab
  videos/
    hautoml-pipeline.mp4
  src/
    brand.ts         # Export nhóm brand (@automl/assets/brand)
    achievements.ts  # Export nhóm giải thưởng (@automl/assets/achievements)
    lab-carousel.ts  # Export nhóm carousel (@automl/assets/lab-carousel)
    lab-members.ts   # Export nhóm thành viên (@automl/assets/lab-members)
    videos.ts        # Export video (@automl/assets/videos)
    index.ts         # Re-export toàn bộ (@automl/assets)
```

## Quy ước tách tài nguyên giữa `packages/assets` và từng App

- **`packages/assets`**: chứa toàn bộ ảnh/video dùng chung giữa Web và Mobile.
- **`apps/web/public`**: chỉ giữ các tệp web-only bắt buộc nằm ở URL gốc `/` (favicon, `apple-touch-icon.png`, `android-chrome-*.png`, ảnh OpenGraph `image.png`, `robots.txt`, `sitemap.xml`).
- **`apps/mobile/assets`**: sau này chỉ giữ icon/splash đặc thù iOS & Android cho cấu hình `app.json` của Expo.

## Cách sử dụng

> **Khuyến nghị**: Ưu tiên import theo **subpath** (`@automl/assets/brand`, `@automl/assets/lab-members`, ...) thay vì import barrel gốc `@automl/assets`, giúp tránh bundle thừa ảnh không dùng trên ứng dụng Mobile.

### Web (Next.js)

```tsx
import Image from "next/image";
import { brandAssets } from "@automl/assets/brand";

export function BrandLogo() {
  return (
    <Image
      src={brandAssets.logoNoText}
      alt="HAutoML"
      width={32}
      height={32}
    />
  );
}
```

### Mobile (React Native / Expo)

```tsx
import { Image } from "react-native";
import { brandAssets } from "@automl/assets/brand";

export function BrandLogo() {
  return (
    <Image
      source={brandAssets.logoNoText}
      style={{ width: 32, height: 32 }}
      resizeMode="contain"
    />
  );
}
```
