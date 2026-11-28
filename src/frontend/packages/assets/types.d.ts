// Ambient asset module declarations for standalone typechecking of @automl/assets.
// Consuming apps (Next.js / React Native Expo) supply their own platform-specific
// asset module types (StaticImageData on Web, number/ImageRequireSource on Mobile).

type StaticMediaAsset =
  | string
  | number
  | {
      src: string;
      height: number;
      width: number;
      blurDataURL?: string;
    };

declare module "*.png" {
  const asset: StaticMediaAsset;
  export default asset;
}

declare module "*.jpg" {
  const asset: StaticMediaAsset;
  export default asset;
}

declare module "*.jpeg" {
  const asset: StaticMediaAsset;
  export default asset;
}

declare module "*.webp" {
  const asset: StaticMediaAsset;
  export default asset;
}

declare module "*.gif" {
  const asset: StaticMediaAsset;
  export default asset;
}

declare module "*.avif" {
  const asset: StaticMediaAsset;
  export default asset;
}

declare module "*.svg" {
  const asset: StaticMediaAsset;
  export default asset;
}

declare module "*.mp4" {
  const asset: string | number;
  export default asset;
}

declare module "*.webm" {
  const asset: string | number;
  export default asset;
}
