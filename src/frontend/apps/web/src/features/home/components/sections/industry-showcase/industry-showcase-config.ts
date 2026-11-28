import type { StaticImageData } from "next/image";
import { achievementImages } from "@automl/assets/achievements";

export interface IndustryCard {
  id: string;
  image: StaticImageData | string;
}

export interface AwardItem {
  id: string;
  title: string;
  titleEn: string;
  subtitle: string;
  subtitleEn: string;
  iconType: "trophy" | "award" | "users" | "zap";
  badge: string;
  badgeEn?: string;
  image: StaticImageData | string;
}

export const AWARDS_DATA: AwardItem[] = [
  {
    id: "giai-nhat-nckh",
    title: "Giải nhất sinh viên nghiên cứu khoa học 2025 - 2026",
    titleEn: "1st Prize Student Scientific Research 2025 - 2026",
    subtitle: "Hội nghị và trao giải NCKH Sinh viên lần thứ XVII - HaUI",
    subtitleEn: "17th Student Scientific Research Conference & Award - HaUI",
    iconType: "trophy",
    badge: "Giải Nhất",
    badgeEn: "1st Prize",
    image: achievementImages.giaiNhatNckh20252026,
  },
  {
    id: "giai-nhi-startup-mindset",
    title: "Giải nhì Sinh viên với ý tưởng khởi nghiệp sáng tạo Haui - Starup Midset 2025",
    titleEn: "2nd Prize Student Innovative Startup Ideas HaUI - Startup Mindset 2025",
    subtitle: "Chung kết Cuộc thi HaUI - Startup Mindset 2025",
    subtitleEn: "HaUI - Startup Mindset 2025 Competition Finals",
    iconType: "award",
    badge: "Giải Nhì",
    badgeEn: "2nd Prize",
    image: achievementImages.giaiNhiStartupMindset2025,
  },
  {
    id: "giai-khuyen-khich-sv-startup",
    title: "Giải Khuyến khích Ngày hội khởi nghiệp Quốc gia của học sinh, sinh viên lần thứ VIII",
    titleEn: "Consolation Prize - 8th National Student Startup Festival",
    subtitle: "SV.STARTUP - Bộ GD&ĐT phối hợp Bộ KH&CN tổ chức",
    subtitleEn: "SV.STARTUP - National Innovation Startup Festival (MOET & MOST)",
    iconType: "trophy",
    badge: "Cấp Quốc Gia",
    badgeEn: "National",
    image: achievementImages.giaiKhuyenKhichSvStartupLan8,
  },
  {
    id: "giai-trien-vong-nextgen",
    title: "Giải triển vọng cuộc thi sinh viên với ý tưởng khởi nghiệp sáng tạo Next Gen",
    titleEn: "Promising Award - NextGen Student Innovative Startup Challenge",
    subtitle: "NextGen Entrepreneurship Challenge - HaUI",
    subtitleEn: "NextGen Entrepreneurship Challenge - HaUI",
    iconType: "zap",
    badge: "Triển Vọng",
    badgeEn: "Promising",
    image: achievementImages.giaiTrienVongNextgen,
  },
  {
    id: "giai-khuyen-khich-doi-moi-sang-tao",
    title: "Giải Khuyến khích ngày hội đổi mới sáng tạo",
    titleEn: "Consolation Prize - HaUI Innovation Day",
    subtitle: "HaUI Innovation Day 2025 – Vòng thi Pitching",
    subtitleEn: "HaUI Innovation Day 2025 – Pitching Competition",
    iconType: "award",
    badge: "Đổi Mới Sáng Tạo",
    badgeEn: "Innovation",
    image: achievementImages.giaiKhuyenKhichDoiMoiSangTao,
  },
];

export const INDUSTRY_ROW_1: IndustryCard[] = [
  {
    id: "row1-giai-nhat-nckh",
    image: achievementImages.giaiNhatNckh20252026,
  },
  {
    id: "row1-giai-nhi-startup",
    image: achievementImages.giaiNhiStartupMindset2025,
  },
  {
    id: "row1-giai-khuyen-khich-sv-startup",
    image: achievementImages.giaiKhuyenKhichSvStartupLan8,
  },
  {
    id: "row1-icisn-springer",
    image: achievementImages.icisnSpringer2025,
  },
  {
    id: "row1-giai-trien-vong-nextgen",
    image: achievementImages.giaiTrienVongNextgen,
  },
  {
    id: "row1-team-work",
    image: achievementImages.optivisionTeamWork,
  },
];

export const INDUSTRY_ROW_2: IndustryCard[] = [
  {
    id: "row2-giai-khuyen-khich-dmst",
    image: achievementImages.giaiKhuyenKhichDoiMoiSangTao,
  },
  {
    id: "row2-giai-trien-vong-nextgen",
    image: achievementImages.giaiTrienVongNextgen,
  },
  {
    id: "row2-giai-nhat-nckh",
    image: achievementImages.giaiNhatNckh20252026,
  },
  {
    id: "row2-giai-khuyen-khich-sv-startup",
    image: achievementImages.giaiKhuyenKhichSvStartupLan8,
  },
  {
    id: "row2-icta-conference",
    image: achievementImages.icta2024Conference,
  },
  {
    id: "row2-giai-nhi-startup",
    image: achievementImages.giaiNhiStartupMindset2025,
  },
];
