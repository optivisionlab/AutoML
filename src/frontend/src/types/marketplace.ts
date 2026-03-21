export interface ModelPricing {
  name: string;
  price: string;
  description: string;
  highlight?: boolean;
}

export interface ModelSpec {
  label: string;
  value: string;
}

export interface MarketplaceModelDetail {
  id: string;
  slug: string;
  name: string;
  img: string;
  shortDescription: string;
  description: string;
  category: string;
  provider: string;
  tags: string[];
  supportedFormats: string[];
  features: string[];
  specs: ModelSpec[];
  pricing: ModelPricing[];
}
