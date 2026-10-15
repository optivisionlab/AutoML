export interface FooterLinkItem {
  key: string;
  labelKey: string;
  href: string;
  badge?: string;
  external?: boolean;
}

export interface FooterColumn {
  id: string;
  titleKey: string;
  items: FooterLinkItem[];
}

export const footerNavigationColumns: FooterColumn[] = [
  {
    id: "product",
    titleKey: "productsTitle",
    items: [
      {
        key: "workflow",
        labelKey: "workflowCanvas",
        href: "/#workflow",
        badge: "Visual",
      },
      {
        key: "autotrain",
        labelKey: "autoTrain",
        href: "/#product",
        badge: "AutoML",
      },
      {
        key: "deploy",
        labelKey: "deployTest",
        href: "/#product",
        badge: "API",
      },
      {
        key: "preprocess",
        labelKey: "smartPreprocess",
        href: "/#introduction",
      },
    ],
  },
  {
    id: "solutions",
    titleKey: "solutionsTitle",
    items: [
      {
        key: "cv",
        labelKey: "computerVision",
        href: "/#product",
      },
      {
        key: "tabular",
        labelKey: "tabularData",
        href: "/#product",
      },
      {
        key: "marketplace",
        labelKey: "marketplace",
        href: "/market-place",
        badge: "Explore",
      },
      {
        key: "publicDatasets",
        labelKey: "publicDatasets",
        href: "/public-datasets",
      },
    ],
  },
  {
    id: "resources",
    titleKey: "resourcesTitle",
    items: [
      {
        key: "docs",
        labelKey: "docs",
        href: "/docs",
      },
      {
        key: "trainingHistory",
        labelKey: "trainingHistory",
        href: "/training-history",
      },
      {
        key: "quickstart",
        labelKey: "quickstart",
        href: "/docs?topic=quickstart",
      },
      {
        key: "architecture",
        labelKey: "architecture",
        href: "/docs?topic=architecture",
      },
    ],
  },
  {
    id: "research",
    titleKey: "researchTitle",
    items: [
      {
        key: "team",
        labelKey: "optivisionLab",
        href: "/team",
      },
      {
        key: "haui",
        labelKey: "haui",
        href: "https://haui.edu.vn",
        external: true,
      },
      {
        key: "openSource",
        labelKey: "githubRepo",
        href: "https://github.com/optivisionlab/AutoML",
        external: true,
      },
      {
        key: "community",
        labelKey: "community",
        href: "/team",
      },
    ],
  },
];

export const footerSocialLinks = [
  {
    key: "github",
    name: "GitHub",
    href: "https://github.com/optivisionlab/AutoML",
  },
  {
    key: "facebook",
    name: "Facebook",
    href: "https://www.facebook.com/meoluoiai",
  },
  {
    key: "youtube",
    name: "YouTube",
    href: "https://www.youtube.com/@meoluoiai",
  },
];

export const footerLabInfo = {
  name: "OptiVisionLab",
  institution: "SICT — Trường Đại học Công nghiệp Hà Nội (HaUI)",
  address: "Số 298 đường Cầu Diễn, phường Minh Khai, quận Bắc Từ Liêm, Hà Nội",
  email: "optivision.work@gmail.com",
  githubRepo: "https://github.com/optivisionlab/AutoML",
};
