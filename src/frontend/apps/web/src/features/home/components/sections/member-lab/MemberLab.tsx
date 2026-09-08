"use client";

import React, { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useLanguage } from "@/core/i18n/LanguageProvider";
import {
  ArrowRight,
  Award,
  Building2,
  Check,
  Copy,
  ExternalLink,
  Github,
  Grid3X3,
  Heart,
  Layers,
  Users,
} from "lucide-react";
import { FaGithub } from "react-icons/fa";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/shared/components/ui/carousel";

type MemberCategory =
  | "all"
  | "core-authors"
  | "systems"
  | "ai-data"
  | "frontend"
  | "students";

interface LabMember {
  name: string;
  position: string;
  image: string;
  category: MemberCategory[];
  company: string;
  isAuthor?: boolean;
}

interface Contributor {
  name: string;
  handle: string;
  avatar: string;
  role: string;
  commits: string;
  badge: string;
  url: string;
}

const LAB_MEMBERS: LabMember[] = [
  {
    name: "Đỗ Mạnh Quang (Founder)",
    position: "Giảng viên Khoa CNTT, SICT – ĐH Công nghiệp Hà Nội",
    image: "/lab-members/quang.png",
    category: ["all", "core-authors"],
    company: "HaUI SICT",
    isAuthor: true,
  },
  {
    name: "Chử Thị Ánh",
    position: "Data Engineer tại Samsung R&D Institute Vietnam",
    image: "/lab-members/chuanh.jpg",
    category: ["all", "core-authors", "ai-data"],
    company: "Samsung R&D",
    isAuthor: true,
  },
  {
    name: "Ngọ Công Bình",
    position: "Backend Developer tại Samsung Electronics Vietnam",
    image: "/lab-members/binh.jpeg",
    category: ["all", "core-authors", "systems"],
    company: "Samsung VN",
    isAuthor: true,
  },
  {
    name: "Bùi Huy Nam",
    position: "BrSE / Backend Developer tại FPT Software",
    image: "/lab-members/BuiHuyNam.jpg",
    category: ["all", "core-authors", "systems"],
    company: "FPT Software",
    isAuthor: true,
  },
  {
    name: "Nguyễn Thị Mỹ Khánh",
    position: "BA & Frontend Developer tại OptiVisionLab, SICT, HaUI",
    image: "/lab-members/mykhanh.jpg",
    category: ["all", "core-authors", "frontend"],
    company: "OptiVisionLab",
    isAuthor: true,
  },
  {
    name: "Nguyễn Thị Minh",
    position: "Business Analyst & Backend Developer tại FPT Telecom",
    image: "/lab-members/nguyenminh.JPG",
    category: ["all", "core-authors", "systems"],
    company: "FPT Telecom",
    isAuthor: true,
  },
  {
    name: "Lê Văn Anh",
    position: "Distributed Systems & Frontend Lead tại OptiVisionLab",
    image: "/lab-members/LeVanAnh.jpg",
    category: ["all", "systems", "frontend"],
    company: "OptiVisionLab",
  },
  {
    name: "Vũ Xuân Đông",
    position: "Backend & Storage Engineer tại OptiVisionLab, SICT, HaUI",
    image: "/lab-members/VuXuanDong.jpg",
    category: ["all", "systems", "students"],
    company: "OptiVisionLab",
  },
  {
    name: "Nguyễn Hồng Quân",
    position: "Application Security Engineer tại Techcombank",
    image: "/lab-members/NguyenHongQuan.jpg",
    category: ["all", "systems"],
    company: "Techcombank",
  },
  {
    name: "Nguyễn Thanh Long",
    position: "BrSE & AI Engineer tại FPT Software",
    image: "/lab-members/thanhlong.jpg",
    category: ["all", "ai-data"],
    company: "FPT Software",
  },
  {
    name: "Nguyễn Thị Lan",
    position: "Product Quality Assurance (PQA) tại NTQ Solution JSC",
    image: "/lab-members/nguyenlan.jpg",
    category: ["all", "ai-data"],
    company: "NTQ Solution",
  },
  {
    name: "Trần Xuân Đức",
    position: "Mobile & Backend Developer tại OptiVisionLab, SICT, HaUI",
    image: "/lab-members/TranXuanDuc_MobileDev.jpg",
    category: ["all", "frontend"],
    company: "OptiVisionLab",
  },
  {
    name: "Lưu Hoàng Phúc",
    position: "Student Research Assistant tại OptiVisionLab, SICT, HaUI",
    image: "/lab-members/LuuHoangPhuc.jpg",
    category: ["all", "students"],
    company: "OptiVisionLab",
  },
  {
    name: "Phan Đại Cương",
    position: "Student Research Assistant tại OptiVisionLab, SICT, HaUI",
    image: "/lab-members/PhanDaiCuong.jpg",
    category: ["all", "students"],
    company: "OptiVisionLab",
  },
  {
    name: "Nguyễn Thị Hải Quỳnh",
    position: "Student Research Assistant tại OptiVisionLab, SICT, HaUI",
    image: "/lab-members/haiquynh.jpg",
    category: ["all", "students"],
    company: "OptiVisionLab",
  },
  {
    name: "Nguyễn Thị Khánh Ly",
    position: "Student Research Assistant tại OptiVisionLab, SICT, HaUI",
    image: "/lab-members/khanhly.jpg",
    category: ["all", "students"],
    company: "OptiVisionLab",
  },
];

const TOP_CONTRIBUTORS: Contributor[] = [
  {
    name: "Nguyễn Xuân Đồng",
    handle: "xuanndong",
    avatar: "https://avatars.githubusercontent.com/u/104260381?v=4",
    role: "MinIO Object Storage & Async Worker API",
    commits: "164+ commits",
    badge: "Core Backend",
    url: "https://github.com/xuanndong",
  },
  {
    name: "Hoàng Việt Anh",
    handle: "vanhdz74",
    avatar: "https://avatars.githubusercontent.com/u/100125854?v=4",
    role: "Distributed Smart Scheduler & Frontend UI/UX",
    commits: "169+ commits",
    badge: "Core Lead",
    url: "https://github.com/vanhdz74",
  },
  {
    name: "Chử Thị Ánh",
    handle: "chuanh1214",
    avatar: "https://avatars.githubusercontent.com/u/108520857?v=4",
    role: "Data Science, Preprocessing & HPO Tuning",
    commits: "55+ commits",
    badge: "AI Engineering",
    url: "https://github.com/chuanh1214",
  },
  {
    name: "Nguyễn Khánh",
    handle: "nguyenkhanh0310",
    avatar: "https://avatars.githubusercontent.com/u/119934149?v=4",
    role: "Admin Dashboard, Pagination & Realtime Monitor",
    commits: "56+ commits",
    badge: "Frontend UI",
    url: "https://github.com/nguyenkhanh0310",
  },
  {
    name: "Ngô Công Bình",
    handle: "CongBinh05",
    avatar: "https://avatars.githubusercontent.com/u/110931210?v=4",
    role: "Training Pipeline Automation & Model Evaluation",
    commits: "25+ commits",
    badge: "Automation",
    url: "https://github.com/CongBinh05",
  },
  {
    name: "Bùi Huy Nam",
    handle: "BuiHuyNam",
    avatar: "https://avatars.githubusercontent.com/u/120610368?v=4",
    role: "FastAPI Engine & Apache Kafka Queue Integration",
    commits: "17+ commits",
    badge: "Backend API",
    url: "https://github.com/BuiHuyNam",
  },
  {
    name: "Đỗ Mạnh Quang",
    handle: "DoManhQuang",
    avatar: "https://avatars.githubusercontent.com/u/38743127?v=4",
    role: "Project Manager & MapReduce Architecture",
    commits: "12+ commits",
    badge: "Project Lead",
    url: "https://github.com/DoManhQuang",
  },
  {
    name: "l3eol3eo",
    handle: "l3eol3eo",
    avatar: "https://github.com/l3eol3eo.png",
    role: "Security Audit, Vulnerability Fixes & OAuth",
    commits: "Security",
    badge: "Security",
    url: "https://github.com/l3eol3eo",
  },
];

const CATEGORY_TABS = [
  { id: "all" as MemberCategory, label: "Tất cả thành viên", labelEn: "All Members" },
  { id: "core-authors" as MemberCategory, label: "Tác giả Springer ISINC", labelEn: "Springer ISINC Authors" },
  { id: "systems" as MemberCategory, label: "Hệ thống & Phân tán", labelEn: "Systems & Distributed" },
  { id: "ai-data" as MemberCategory, label: "AI & Dữ liệu", labelEn: "AI & Data Science" },
  { id: "frontend" as MemberCategory, label: "Frontend & UI/UX", labelEn: "Frontend & UI/UX" },
  { id: "students" as MemberCategory, label: "Sinh viên Nghiên cứu", labelEn: "Student Researchers" },
];

export default function MemberLab() {
  const { locale } = useLanguage();
  const isEn = locale === "en";
  const [selectedCategory, setSelectedCategory] =
    useState<MemberCategory>("all");
  const [isGridView, setIsGridView] = useState(false);
  const [isCopiedBibtex, setIsCopiedBibtex] = useState(false);

  const filteredMembers =
    selectedCategory === "all"
      ? LAB_MEMBERS
      : LAB_MEMBERS.filter((m) => m.category.includes(selectedCategory));

  const copyBibtex = () => {
    const bibtex = `@InProceedings{Do2026HAutoML,
  author="Do, Manh Quang and Chu, Thi Anh and Ngo, Cong Binh and Bui, Huy Nam and Nguyen, Thi My Khanh and Nguyen, Thi Minh and Vu, Viet Thang",
  title="HAutoML: Open-Source for Automated Machine Learning",
  booktitle="Proceedings of the Fifth International Conference on Intelligent Systems and Networks (ISINC 2026)",
  year="2026",
  publisher="Springer Nature Singapore",
  pages="415--423",
  doi="10.1007/978-981-95-1746-6_46"
}`;
    navigator.clipboard.writeText(bibtex);
    setIsCopiedBibtex(true);
    setTimeout(() => setIsCopiedBibtex(false), 2000);
  };

  return (
    <div className="space-y-16">
      {/* 1. Lab Highlight Metrics & Badges */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200/80 bg-white/70 p-4 text-center backdrop-blur-xl shadow-sm dark:border-white/10 dark:bg-[#0B0F19]/60">
          <Building2 className="h-5 w-5 text-blue-600 dark:text-cyan-400 mb-1.5" />
          <span className="text-xl font-black text-slate-900 dark:text-white">
            SICT – HaUI
          </span>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">
            {isEn ? "Research Institute" : "Đơn vị nghiên cứu"}
          </span>
        </div>

        <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200/80 bg-white/70 p-4 text-center backdrop-blur-xl shadow-sm dark:border-white/10 dark:bg-[#0B0F19]/60">
          <Award className="h-5 w-5 text-indigo-600 dark:text-indigo-400 mb-1.5" />
          <span className="text-xl font-black text-slate-900 dark:text-white">
            Springer ISINC
          </span>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">
            {isEn ? "International Publication" : "Công bố quốc tế 2026"}
          </span>
        </div>

        <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200/80 bg-white/70 p-4 text-center backdrop-blur-xl shadow-sm dark:border-white/10 dark:bg-[#0B0F19]/60">
          <Users className="h-5 w-5 text-blue-600 dark:text-cyan-400 mb-1.5" />
          <span className="text-xl font-black text-slate-900 dark:text-white">
            {isEn ? "16+ Members" : "16+ Thành viên"}
          </span>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">
            {isEn ? "Researchers & Engineers" : "Nghiên cứu & Kỹ sư"}
          </span>
        </div>

        <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200/80 bg-white/70 p-4 text-center backdrop-blur-xl shadow-sm dark:border-white/10 dark:bg-[#0B0F19]/60">
          <Heart className="h-5 w-5 text-rose-500 mb-1.5" />
          <span className="text-xl font-black text-slate-900 dark:text-white">
            {isEn ? "20+ Contributors" : "20+ Đóng góp"}
          </span>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">
            {isEn ? "GitHub Community" : "Cộng đồng GitHub"}
          </span>
        </div>
      </div>

      {/* 2. Members Section Header & Filter Tabs */}
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-2xl font-black text-slate-900 sm:text-3xl dark:text-white flex items-center gap-2.5">
              <Users className="h-6 w-6 text-blue-600 dark:text-cyan-400" />
              {isEn ? "OptiVisionLab Research Members" : "Thành viên phòng nghiên cứu OptiVisionLab"}
            </h3>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
              {isEn ? "Faculty advisors, researchers, and core students developing HAutoML." : "Đội ngũ giảng viên, nghiên cứu sinh và sinh viên nòng cốt tham gia phát triển HAutoML."}
            </p>
          </div>

          {/* Grid vs Carousel toggle button */}
          <button
            type="button"
            onClick={() => setIsGridView((prev) => !prev)}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10 self-start sm:self-auto"
          >
            {isGridView ? (
              <>
                <Layers className="h-3.5 w-3.5 text-blue-500" />
                <span>{isEn ? "Carousel View" : "Xem trượt (Carousel)"}</span>
              </>
            ) : (
              <>
                <Grid3X3 className="h-3.5 w-3.5 text-blue-500" />
                <span>{isEn ? "Grid View" : "Xem tất cả (Lưới)"}</span>
              </>
            )}
          </button>
        </div>

        {/* Filter categories pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
          {CATEGORY_TABS.map((tab) => {
            const isActive = selectedCategory === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setSelectedCategory(tab.id)}
                className={`rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all whitespace-nowrap ${
                  isActive
                    ? "bg-blue-600 text-white shadow-[0_0_16px_rgba(37,99,255,0.35)]"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10"
                }`}
              >
                {isEn ? tab.labelEn : tab.label}
              </button>
            );
          })}
        </div>

        {/* Render Members: Grid or Carousel */}
        {isGridView ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {filteredMembers.map((member) => (
              <MemberCard key={member.name} member={member} />
            ))}
          </div>
        ) : (
          <div className="relative px-2">
            <Carousel opts={{ align: "start", loop: true }} className="w-full">
              <CarouselContent className="-ml-3">
                {filteredMembers.map((member) => (
                  <CarouselItem
                    key={member.name}
                    className="pl-3 sm:basis-1/2 md:basis-1/3 lg:basis-1/4"
                  >
                    <div className="h-full py-2">
                      <MemberCard member={member} />
                    </div>
                  </CarouselItem>
                ))}
              </CarouselContent>
              <CarouselPrevious className="-left-3 h-9 w-9 border-slate-200 bg-white/90 shadow-md backdrop-blur dark:border-white/10 dark:bg-[#0B0F19]/90 text-slate-700 dark:text-white" />
              <CarouselNext className="-right-3 h-9 w-9 border-slate-200 bg-white/90 shadow-md backdrop-blur dark:border-white/10 dark:bg-[#0B0F19]/90 text-slate-700 dark:text-white" />
            </Carousel>
          </div>
        )}
      </div>

      {/* 3. Contributors Showcase with Real Avatars */}
      <div className="rounded-3xl border border-slate-200/80 bg-white/70 p-6 sm:p-8 backdrop-blur-xl shadow-sm dark:border-white/10 dark:bg-[#0B0F19]/60 space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200/80 pb-4 dark:border-white/10">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-bold text-rose-600 dark:bg-rose-950/60 dark:text-rose-400">
              <Heart className="h-3.5 w-3.5" />
              {isEn ? "Open-Source Community" : "Cộng đồng mã nguồn mở"}
            </div>
            <h3 className="mt-2 text-2xl font-black text-slate-900 dark:text-white">
              {isEn ? "GitHub Contributors Profile" : "Ảnh & Hồ sơ các thành viên đóng góp (Contributors)"}
            </h3>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
              {isEn ? "Honoring engineers and students who contributed code, features, and security fixes to HAutoML." : "Vinh danh các kỹ sư, sinh viên đã trực tiếp đóng góp mã nguồn, tính năng và bảo mật cho repository HAutoML."}
            </p>
          </div>

          <a
            href="https://github.com/optivisionlab/AutoML/graphs/contributors"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-blue-500"
          >
            <FaGithub className="h-3.5 w-3.5" />
            <span>GitHub Contributors</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        {/* Top Contributors Grid with Photos */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {TOP_CONTRIBUTORS.map((c) => (
            <a
              key={c.handle}
              href={c.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-3 rounded-2xl border border-slate-200/70 bg-white/90 p-3.5 shadow-sm backdrop-blur transition-all duration-200 hover:-translate-y-1 hover:border-blue-400/60 hover:shadow-[0_12px_28px_rgba(37,99,255,0.12)] dark:border-white/10 dark:bg-[#061021]/80 dark:hover:border-blue-500/50"
            >
              {/* Contributor Avatar */}
              <div className="relative shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={c.avatar}
                  alt={c.name}
                  className="h-12 w-12 rounded-xl object-cover ring-2 ring-blue-500/30 transition-transform duration-200 group-hover:scale-105 group-hover:ring-blue-500"
                />
                <span className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-slate-900 text-[9px] text-white">
                  <FaGithub className="h-2.5 w-2.5" />
                </span>
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between">
                  <span className="truncate text-xs font-black text-slate-900 group-hover:text-blue-600 dark:text-white dark:group-hover:text-cyan-300">
                    {c.name}
                  </span>
                  <span className="shrink-0 rounded bg-blue-50 px-1 py-0.2 text-[9px] font-bold text-blue-700 dark:bg-blue-950 dark:text-cyan-300">
                    {c.commits}
                  </span>
                </div>

                <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                  @{c.handle}
                </p>

                <p className="mt-1 line-clamp-1 text-[11px] text-slate-600 dark:text-slate-300">
                  {c.role}
                </p>
              </div>
            </a>
          ))}
        </div>

        {/* Dynamic Contrib.rocks Avatar Wall */}
        <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-5 text-center dark:border-white/10 dark:bg-[#061021]/60">
          <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-3">
            Bức tường tất cả các thành viên đóng góp qua commit trên GitHub:
          </p>

          <div className="flex justify-center overflow-hidden py-2">
            <a
              href="https://github.com/optivisionlab/AutoML/graphs/contributors"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="https://contrib.rocks/image?repo=optivisionlab/AutoML"
                alt="HAutoML Contributors Wall"
                className="max-w-full rounded-xl transition hover:opacity-90 shadow-sm"
              />
            </a>
          </div>

          <div className="mt-4 flex flex-wrap justify-center gap-3 text-xs font-bold">
            <a
              href="https://github.com/optivisionlab/AutoML"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-white shadow transition hover:bg-slate-800 dark:bg-white/10 dark:hover:bg-white/20"
            >
              <Github className="h-3.5 w-3.5" />
              <span>Gửi Pull Request trên GitHub</span>
              <ArrowRight className="h-3 w-3" />
            </a>

            <Link
              href="/docs?topic=team-community"
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-slate-700 shadow-sm transition hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
            >
              <span>Xem hồ sơ chi tiết tại Docs</span>
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </div>
      </div>

      {/* 4. Springer Nature International Publication Spotlight */}
      <div className="rounded-3xl border border-blue-200/80 bg-gradient-to-br from-blue-50/90 via-indigo-50/40 to-cyan-50/60 p-6 sm:p-8 dark:border-blue-900/40 dark:from-blue-950/30 dark:via-[#061021] dark:to-cyan-950/20 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2 max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 px-3 py-0.5 text-[11px] font-bold text-white shadow-sm">
                <Award className="h-3.5 w-3.5" />
                Công bố khoa học quốc tế (ISINC 2026)
              </span>
              <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-[11px] font-semibold text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                Springer Nature Singapore
              </span>
            </div>

            <h4 className="text-xl font-black text-slate-900 sm:text-2xl dark:text-white">
              HAutoML: Open-Source for Automated Machine Learning
            </h4>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              <strong>{isEn ? "Authors:" : "Tác giả:"}</strong> Đỗ Mạnh Quang, Chu Thị Ánh, Ngô Công
              Bình, Bùi Huy Nam, Nguyễn Thị Mỹ Khánh, Nguyễn Thị Minh, và TS. Vũ
              Việt Thắng.
            </p>

            <p className="text-xs text-slate-500 dark:text-slate-400">
              {isEn ? "Published in Proceedings of the 5th International Conference on Intelligent Systems and Networks (ISINC 2026), pp. 415–423, ISBN 978-981-95-1746-6." : "Xuất bản tại Tuyển tập Hội thảo Quốc tế về Hệ thống Thông minh và Mạng truyền thông (ISINC 2026), trang 415–423, ISBN 978-981-95-1746-6."}
            </p>
          </div>

          <div className="flex shrink-0 flex-wrap gap-2 sm:flex-col">
            <button
              type="button"
              onClick={copyBibtex}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-blue-500"
            >
              {isCopiedBibtex ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  <span>{isEn ? "Copied BibTeX" : "Đã chép BibTeX"}</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>{isEn ? "Copy BibTeX" : "Sao chép BibTeX"}</span>
                </>
              )}
            </button>

            <a
              href="https://doi.org/10.1007/978-981-95-1746-6_46"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
            >
              <span>{isEn ? "View Paper (DOI)" : "Xem bài báo (DOI)"}</span>
              <ExternalLink className="h-3 w-3 text-slate-400" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

// Subcomponent: Individual Member Card with Modern Styling
function MemberCard({ member }: { member: LabMember }) {
  const { locale } = useLanguage();
  const isEn = locale === "en";

  return (
    <div className="group relative flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-white/90 shadow-sm backdrop-blur-xl transition-all duration-300 hover:-translate-y-1.5 hover:border-blue-400/60 hover:shadow-[0_16px_36px_rgba(37,99,255,0.18)] dark:border-white/10 dark:bg-[#0B0F19]/80 dark:hover:border-blue-500/50">
      {/* Member Photo */}
      <div className="relative aspect-[4/4.8] w-full overflow-hidden bg-slate-100 dark:bg-slate-900">
        <Image
          src={member.image}
          alt={member.name}
          fill
          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
          className="object-cover object-top transition-transform duration-500 group-hover:scale-105"
        />

        {/* Soft bottom gradient */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />

        {/* Company / Institution Badge */}
        <div className="absolute top-3 left-3">
          <span className="inline-flex items-center gap-1 rounded-lg bg-black/60 px-2 py-0.5 text-[10px] font-bold text-white backdrop-blur-md border border-white/15">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
            {member.company}
          </span>
        </div>

        {/* Author badge */}
        {member.isAuthor && (
          <div className="absolute top-3 right-3">
            <span className="rounded-lg bg-blue-600/90 px-2 py-0.5 text-[10px] font-extrabold text-white shadow backdrop-blur-md">
              {isEn ? "ISINC Author" : "Tác giả ISINC"}
            </span>
          </div>
        )}

        {/* Name overlay on image bottom */}
        <div className="absolute bottom-2.5 left-3 right-3">
          <h4 className="text-sm font-black text-white drop-shadow-md group-hover:text-cyan-300 transition-colors">
            {member.name}
          </h4>
        </div>
      </div>

      {/* Member Info Content */}
      <div className="flex flex-1 flex-col justify-between p-3.5">
        <p className="line-clamp-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          {member.position}
        </p>

        <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2 text-[11px] font-semibold text-blue-600 dark:border-white/5 dark:text-cyan-400">
          <span>OptiVisionLab</span>
          <span className="text-[10px] text-slate-400">HaUI SICT</span>
        </div>
      </div>
    </div>
  );
}
