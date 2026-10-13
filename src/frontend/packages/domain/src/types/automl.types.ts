export type FeatureMap = Record<string, boolean>;
export type MetricMap = Record<string, string>;

export interface FeaturesResponse {
  features: FeatureMap;
}

export interface MetricsResponse {
  metrics: MetricMap;
}

export interface DataPreviewResponse {
  rows: number;
  data: Record<string, unknown>[];
}
