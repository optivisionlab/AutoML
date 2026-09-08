export interface IndustryCard {
  id: string;
  image: string;
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
  image: string;
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
    image: "/achievements/giai_nhat_nckh_2025_2026.jpg",
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
    image: "/achievements/giai_nhi_startup_mindset_2025.jpg",
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
    image: "/achievements/giai_khuyen_khich_sv_startup_lan_8.jpg",
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
    image: "/achievements/giai_trien_vong_nextgen.jpg",
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
    image: "/achievements/giai_khuyen_khich_doi_moi_sang_tao.jpg",
  },
];

export const INDUSTRY_ROW_1: IndustryCard[] = [
  {
    id: "row1-giai-nhat-nckh",
    image: "/achievements/giai_nhat_nckh_2025_2026.jpg",
  },
  {
    id: "row1-giai-nhi-startup",
    image: "/achievements/giai_nhi_startup_mindset_2025.jpg",
  },
  {
    id: "row1-giai-khuyen-khich-sv-startup",
    image: "/achievements/giai_khuyen_khich_sv_startup_lan_8.jpg",
  },
  {
    id: "row1-icisn-springer",
    image: "/achievements/icisn_springer_2025.png",
  },
  {
    id: "row1-giai-trien-vong-nextgen",
    image: "/achievements/giai_trien_vong_nextgen.jpg",
  },
  {
    id: "row1-team-work",
    image: "/achievements/optivision_team_work.png",
  },
];

export const INDUSTRY_ROW_2: IndustryCard[] = [
  {
    id: "row2-giai-khuyen-khich-dmst",
    image: "/achievements/giai_khuyen_khich_doi_moi_sang_tao.jpg",
  },
  {
    id: "row2-giai-trien-vong-nextgen",
    image: "/achievements/giai_trien_vong_nextgen.jpg",
  },
  {
    id: "row2-giai-nhat-nckh",
    image: "/achievements/giai_nhat_nckh_2025_2026.jpg",
  },
  {
    id: "row2-giai-khuyen-khich-sv-startup",
    image: "/achievements/giai_khuyen_khich_sv_startup_lan_8.jpg",
  },
  {
    id: "row2-icta-conference",
    image: "/achievements/icta_2024_conference.png",
  },
  {
    id: "row2-giai-nhi-startup",
    image: "/achievements/giai_nhi_startup_mindset_2025.jpg",
  },
];
