import {
  Workflow,
  Sparkles,
  Rocket,
  Wand2,
  Eye,
  Table2,
  Store,
  Database,
  BookOpen,
  History,
  Users,
  Code2,
  type LucideIcon,
} from "lucide-react";

export interface NavDropdownItem {
  key: string;
  titleKey: string;
  descKey: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  external?: boolean;
}

export interface NavDropdownCategory {
  id: "products" | "solutions" | "resources";
  labelKey: string;
  items: NavDropdownItem[];
  callout: {
    titleKey: string;
    descKey: string;
    btnKey: string;
    href: string;
    external?: boolean;
    gradient: string;
  };
}

export interface NavDirectLink {
  key: string;
  labelKey: string;
  href: string;
}

export const headerDropdownCategories: NavDropdownCategory[] = [
  {
    id: "products",
    labelKey: "products",
    items: [
      {
        key: "workflow",
        titleKey: "workflowTitle",
        descKey: "workflowDesc",
        href: "/#workflow",
        icon: Workflow,
        badge: "Visual Canvas",
      },
      {
        key: "autotrain",
        titleKey: "autoTrainTitle",
        descKey: "autoTrainDesc",
        href: "/#product",
        icon: Sparkles,
        badge: "Smart AutoML",
      },
      {
        key: "deploy",
        titleKey: "deployTitle",
        descKey: "deployDesc",
        href: "/#product",
        icon: Rocket,
        badge: "1-Click API",
      },
      {
        key: "preprocess",
        titleKey: "preprocessTitle",
        descKey: "preprocessDesc",
        href: "/#introduction",
        icon: Wand2,
      },
    ],
    callout: {
      titleKey: "calloutProductTitle",
      descKey: "calloutProductDesc",
      btnKey: "calloutProductBtn",
      href: "/register",
      gradient: "from-blue-600/30 via-indigo-600/20 to-purple-600/20",
    },
  },
  {
    id: "solutions",
    labelKey: "solutions",
    items: [
      {
        key: "cv",
        titleKey: "cvTitle",
        descKey: "cvDesc",
        href: "/#product",
        icon: Eye,
      },
      {
        key: "tabular",
        titleKey: "tabularTitle",
        descKey: "tabularDesc",
        href: "/#product",
        icon: Table2,
      },
      {
        key: "marketplace",
        titleKey: "marketplaceTitle",
        descKey: "marketplaceDesc",
        href: "/market-place",
        icon: Store,
        badge: "Hot",
      },
      {
        key: "publicData",
        titleKey: "publicDataTitle",
        descKey: "publicDataDesc",
        href: "/market-place",
        icon: Database,
      },
    ],
    callout: {
      titleKey: "calloutSolutionTitle",
      descKey: "calloutSolutionDesc",
      btnKey: "calloutSolutionBtn",
      href: "/#about-us",
      gradient: "from-emerald-600/30 via-teal-600/20 to-cyan-600/20",
    },
  },
  {
    id: "resources",
    labelKey: "resources",
    items: [
      {
        key: "docs",
        titleKey: "docsTitle",
        descKey: "docsDesc",
        href: "/docs",
        icon: BookOpen,
      },
      {
        key: "history",
        titleKey: "historyTitle",
        descKey: "historyDesc",
        href: "/training-history",
        icon: History,
      },
      {
        key: "community",
        titleKey: "communityTitle",
        descKey: "communityDesc",
        href: "https://github.com/optivisionlab/AutoML",
        icon: Code2,
        external: true,
      },
      {
        key: "aboutUs",
        titleKey: "aboutUsTitle",
        descKey: "aboutUsDesc",
        href: "/team",
        icon: Users,
      },
    ],
    callout: {
      titleKey: "calloutResourceTitle",
      descKey: "calloutResourceDesc",
      btnKey: "calloutResourceBtn",
      href: "https://github.com/optivisionlab/AutoML",
      external: true,
      gradient: "from-cyan-600/30 via-sky-600/20 to-blue-600/20",
    },
  },
];

export const headerDirectLinks: NavDirectLink[] = [
  {
    key: "docs",
    labelKey: "docs",
    href: "/docs",
  },
  {
    key: "team",
    labelKey: "team",
    href: "/team",
  },
];
