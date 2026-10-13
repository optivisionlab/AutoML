# HAutoML Frontend Architecture

Tài liệu này mô tả kiến trúc frontend HAutoML theo hướng monorepo nhẹ. Mục tiêu là giữ Next.js web app dễ debug, dễ mở rộng theo feature, đồng thời tách sẵn không gian cho mobile để sau này có thể chia sẻ business logic mà không phải viết lại toàn bộ.

## Mục Tiêu

- Tách rõ `route`, `feature`, `shared UI`, `state`, `api`, `types`, `utils`.
- Mỗi feature lớn có thư mục riêng, dễ tìm code theo nghiệp vụ.
- Shared component chỉ chứa phần thật sự dùng lại nhiều nơi.
- Tối thiểu hóa import chéo khó kiểm soát.
- Tách rõ `apps/web`, `apps/mobile`, và `packages` dùng chung.
- Giúp AI/dev mới đọc repo nhanh, biết file mới nên đặt ở đâu.

## Nguyên Tắc Chung

- `apps/web/src/app` chỉ nên chứa route, layout, page shell, metadata, server actions gắn với route.
- Logic nghiệp vụ không đặt trực tiếp trong `page.tsx` nếu vượt quá phần điều phối.
- Component theo nghiệp vụ web đặt trong `apps/web/src/features/<feature-name>`.
- Component dùng lại toàn web app đặt trong `apps/web/src/shared`.
- API client, Redux slices, hooks fetching nên gom theo feature hoặc trong `apps/web/src/core/api`.
- Type dùng riêng feature đặt trong feature; type dùng toàn web app đặt trong `apps/web/src/shared/types`.
- Không để thư mục theo tên vai trò cũ như `myDatasetUser`, `publicDatasetUser` phát triển thêm. Nên gom theo domain `datasets`, `training`, `marketplace`.

## Kiến Trúc Đề Xuất

```txt
apps/
  web/
    src/
      app/
        (auth)/
        admin/
        dashboard/
        datasets/
        marketplace/
        training-history/
        layout.tsx
        page.tsx

      features/
        auth/
        home/
        datasets/
        training/
        marketplace/
        deployment/
        account/

      shared/
        components/
          ui/
          layout/
          feedback/
          forms/
          data-display/
        hooks/
        lib/
        types/
        utils/
        constants/

      core/
        api/
        store/
        auth/
        i18n/
        theme/

      messages/
        en.json
        vi.json

      assets/
        images/

  mobile/
    README.md

packages/
  domain/
  ui/
  config/
```

## Vai Trò Từng Vùng

### `apps/web/src/app`

Chỉ quản lý routing của Next.js App Router.

Nên có:
- `page.tsx`
- `layout.tsx`
- `loading.tsx`
- `error.tsx`
- route-level server actions nếu thật sự gắn với route

Không nên có:
- component UI phức tạp
- Redux logic
- gọi API phức tạp
- constant nghiệp vụ lớn

Ví dụ:

```tsx
// apps/web/src/app/my-datasets/[datasetID]/train/page.tsx
import { TrainingPage } from "@/features/training";

export default function Page() {
  return <TrainingPage source="my-dataset" />;
}
```

### `apps/web/src/features`

Mỗi feature là một domain nghiệp vụ có thể phát triển độc lập.

Một feature nên gồm:
- `components/`: component chỉ dùng trong feature đó
- `hooks/`: hook nghiệp vụ
- `services/`: adapter gọi API hoặc mapping dữ liệu
- `store/`: slice/listener local theo feature nếu cần
- `types.ts`: type riêng của feature
- `constants.ts`: constant riêng của feature
- `index.ts`: public export duy nhất của feature

Quy tắc:
- Feature khác không import sâu vào `components/internal`.
- Nếu cần dùng lại, export qua `index.ts`.
- Không import ngược từ `shared` vào `features` là được; `features` được phép import `shared`, nhưng `shared` không import `features`.

### `apps/web/src/shared`

Chứa phần không thuộc nghiệp vụ cụ thể.

Nên có:
- button, dialog, table base, input base
- layout primitive
- loading/empty/error state
- hook generic như `useDebounce`
- util pure function

Không nên có:
- chữ nghiệp vụ như "dataset", "training", "AutoML strategy"
- gọi API backend
- logic session theo feature

### `apps/web/src/core`

Chứa hạ tầng ứng dụng.

Nên có:
- Redux store root
- API client chung
- auth/session setup
- i18n provider/config
- theme provider

Không nên có:
- UI nghiệp vụ
- component page
- logic feature cụ thể

## Mapping Từ Cấu Trúc Hiện Tại

| Hiện tại | Đề xuất |
|---|---|
| `apps/web/src/components/home/hero` | `apps/web/src/features/home/components/hero` |
| `apps/web/src/components/training/TrainingWizard.tsx` | `apps/web/src/features/training/components/wizard/TrainingWizard.tsx` |
| `apps/web/src/components/training/ProgressMap.tsx` | `apps/web/src/features/training/components/progress-map/ProgressMap.tsx` |
| `apps/web/src/components/publicDatasetUser` | `apps/web/src/features/datasets` hoặc `apps/web/src/features/training` tùy component |
| `apps/web/src/components/myDatasetUser` | `apps/web/src/features/datasets` hoặc `apps/web/src/features/training` |
| `apps/web/src/components/marketplace` | `apps/web/src/features/marketplace/components` |
| `apps/web/src/components/common` | `apps/web/src/shared/components` |
| `apps/web/src/components/ui` | `apps/web/src/shared/components/ui` |
| `apps/web/src/redux/api` | `apps/web/src/core/api` hoặc `apps/web/src/features/<feature>/services` |
| `apps/web/src/redux/slices` | `apps/web/src/core/store` hoặc `apps/web/src/features/<feature>/store` |
| `apps/web/src/i18n` | `apps/web/src/core/i18n` |
| `apps/web/src/hooks` | `apps/web/src/shared/hooks` hoặc `apps/web/src/features/<feature>/hooks` |
| `apps/web/src/types` | `apps/web/src/shared/types` hoặc `apps/web/src/features/<feature>/types.ts` |
| `apps/web/src/utils` | `apps/web/src/shared/utils` |

## Quy Ước Đặt Tên

- Feature folder: kebab-case, ví dụ `training-history`, `marketplace`.
- Component file: PascalCase, ví dụ `TrainingWizard.tsx`.
- Hook file: camelCase với tiền tố `use`, ví dụ `useTrainingConfig.ts`.
- Type file riêng feature: `types.ts`.
- Constant file riêng feature: `constants.ts`.
- Service file: `<domain>.service.ts`, ví dụ `training.service.ts`.
- Store slice: `<domain>.slice.ts`.
- Test nếu thêm sau này: đặt cạnh file hoặc trong `__tests__`.

## Quy Tắc Import

Ưu tiên import theo tầng:

```txt
app -> features -> shared -> core
features -> shared/core
shared -> shared only
core -> core/shared-utils only
```

Không nên:

```tsx
// Không import xuyên vào internal component của feature khác
import X from "@/features/training/components/wizard/internal/X";
```

Nên:

```tsx
// Export qua public API
import { TrainingWizard } from "@/features/training";
```

## i18n

Hiện dự án dùng `next-intl` với:

```txt
apps/web/src/messages/en.json
apps/web/src/messages/vi.json
```

Quy ước đề xuất:

```json
{
  "Training": {
    "wizard": {
      "stepMode": "Chế độ",
      "summaryTitle": "Tóm tắt cấu hình"
    }
  }
}
```

Không hardcode text nghiệp vụ trong component mới. Với component đang tồn tại, migrate dần khi chạm vào file.

## Styling

Hiện dự án dùng Tailwind, shadcn-style UI, Radix, dark mode.

Khuyến nghị:
- Global CSS chỉ dùng cho token, theme, reset, animation cấp app.
- UI component nên ưu tiên Tailwind class tại component.
- Animation lớn như hero 3D nên tách file CSS/module hoặc component folder riêng.
- Không để `globals.css` phình mãi với nhiều block không còn dùng.

Đề xuất cho hero:

```txt
apps/web/src/features/home/components/hero/
  HeroSection.tsx
  HeroContent.tsx
  HeroBackground.tsx
  AIModelScene.tsx
  ModelMetrics.tsx
  hero.css hoặc hero.styles.ts
```

## State Management

Hiện có Redux Toolkit. Đề xuất:

- Global app state: auth/session-derived state, sidebar, theme preference nếu cần.
- Server state: ưu tiên RTK Query hoặc service hook theo feature.
- Form state: local state hoặc React Hook Form.
- Wizard state: local reducer/hook trong feature, chỉ persist phần cần qua URL/sessionStorage.

Ví dụ training:

```txt
apps/web/src/features/training/
  hooks/
    useTrainingWizard.ts
  store/
    training.slice.ts
  services/
    training.service.ts
```

## API Layer

Đề xuất chia làm hai lớp:

```txt
core/api/
  axios-client.ts
  base-query.ts
  endpoints.ts

features/training/services/
  training.api.ts
  training.mapper.ts
```

`core/api` không biết UI. `features/*/services` biết domain và chuyển đổi dữ liệu backend thành model frontend.

## Web / Mobile Split

Repo hiện đã tách cấp app:

```txt
apps/
  web/
    src/
  mobile/
    src/

packages/
  domain/
    training/
    datasets/
    marketplace/
  ui/
    web/
    mobile/
  config/
    eslint/
    typescript/
```

`apps/web` là Next.js app hiện tại. `apps/mobile` hiện là placeholder có README, chưa có React Native/Expo implementation để tránh tạo app giả hoặc kéo thêm dependency khi chưa cần.

Mục tiêu khi có mobile:
- Business logic dùng chung đặt trong `packages/domain`.
- API client dùng chung nếu backend giống nhau.
- UI web/mobile tách riêng vì interaction khác nhau.
- Không ép component React DOM chạy trên mobile.
- Type, schema, mapper, constants có thể share.

Hiện tại, để chuẩn bị cho mobile:

- Không phụ thuộc business logic vào DOM.
- Không để logic tính toán nằm trong component UI.
- Tách mapper/API/type ra khỏi React component.
- Với wizard/training flow, nên có hook/use-case thuần:

```txt
apps/web/src/features/training/
  domain/
    training-config.ts
    training-validation.ts
  hooks/
    useTrainingWizard.ts
```

Sau này mobile có thể dùng lại phần thuần ở `packages/domain`, còn UI viết lại bằng React Native.

## Kế Hoạch Migration An Toàn

Không nên refactor toàn repo trong một PR lớn. Làm theo từng bước:

1. Tạo `apps/web/src/features`, `apps/web/src/shared`, `apps/web/src/core`.
2. Move feature mới hoặc file đang sửa vào kiến trúc mới.
3. Với mỗi feature, tạo `index.ts` export public API.
4. Chuyển `components/common` và `components/ui` sang `shared` sau cùng.
5. Chuyển `redux/api` theo domain khi có thời gian.
6. Dọn import alias bằng `rg`.
7. Chạy `npm run typecheck` và `npm run build`.

Ưu tiên migrate trước:

1. `features/training`: vì wizard đang lớn, dễ cần debug.
2. `features/home`: vì hero 3D/animation đang nhiều file.
3. `features/datasets`: vì dùng ở public/my/admin.
4. `features/marketplace`.

## Checklist Khi Tạo Feature Mới

- [ ] Feature có thư mục riêng trong `apps/web/src/features`.
- [ ] Không đặt component nghiệp vụ mới vào `apps/web/src/components` trừ khi đang migrate dở.
- [ ] Có `types.ts` nếu data shape không trivial.
- [ ] Text UI đi qua `messages/*.json`.
- [ ] API call nằm trong `services` hoặc RTK Query domain.
- [ ] Page route chỉ import component cấp feature.
- [ ] Không import sâu vào internal của feature khác.
- [ ] Component lớn hơn khoảng 250-300 dòng nên tách nhỏ.

## Ghi Chú Cho AI/Dev Sau

- Trước khi sửa UI, tìm feature liên quan bằng `rg`.
- Không refactor toàn bộ khi chỉ sửa bug nhỏ.
- Nếu file đã quá lớn, tách theo hướng feature-local trước.
- Không xoá code cũ nếu chưa xác nhận không còn route/import dùng.
- Khi chạm vào training wizard, ưu tiên tách `useTrainingWizard`, `StepProgress`, `SummaryPanel`, `ChoiceCard` ra file riêng.
- Khi chạm vào home hero, giữ 3D scene client-only và không đưa Three.js vào server component.
