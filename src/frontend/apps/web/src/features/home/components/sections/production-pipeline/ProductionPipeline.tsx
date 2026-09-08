"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Pause,
  Play,
  RotateCcw,
  Server,
  Volume2,
  VolumeX,
  Zap,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/shared/lib/utils";
import {
  DEMO_VIDEO_URL,
  PIPELINE_STEPS,
  type PipelineStep,
} from "./pipeline-steps-config";

export default function ProductionPipeline() {
  const t = useTranslations("Home");

  // Tổng thời gian của toàn bộ quy trình (tính theo endTime của bước cuối cùng)
  const totalDuration = useMemo(() => {
    if (PIPELINE_STEPS.length === 0) return 15;
    return PIPELINE_STEPS[PIPELINE_STEPS.length - 1].endTime;
  }, []);

  const [currentTime, setCurrentTime] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [isMuted, setIsMuted] = useState<boolean>(true);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Tự động play video khi component mount
  useEffect(() => {
    if (DEMO_VIDEO_URL && videoRef.current) {
      videoRef.current.play().catch(() => {});
    }
  }, []);

  // Xác định bước đang kích hoạt dựa trên currentTime
  const activeStepIndex = useMemo(() => {
    const foundIndex = PIPELINE_STEPS.findIndex(
      (s) => currentTime >= s.startTime && currentTime < s.endTime
    );
    if (foundIndex !== -1) return foundIndex;
    // Nếu currentTime vượt qua endTime cuối, trỏ về bước cuối
    if (currentTime >= totalDuration) return PIPELINE_STEPS.length - 1;
    return 0;
  }, [currentTime, totalDuration]);

  const activeStep: PipelineStep = PIPELINE_STEPS[activeStepIndex] || PIPELINE_STEPS[0];

  // Tính % tiến trình hoàn thành của bước hiện tại (0% -> 100%)
  const currentStepProgress = useMemo(() => {
    const stepDuration = activeStep.endTime - activeStep.startTime;
    if (stepDuration <= 0) return 0;
    const elapsedInStep = currentTime - activeStep.startTime;
    return Math.min(100, Math.max(0, (elapsedInStep / stepDuration) * 100));
  }, [currentTime, activeStep]);

  // Bộ đếm thời gian tự động dự phòng khi không có video thật
  useEffect(() => {
    if (!isPlaying) return;
    if (DEMO_VIDEO_URL && videoRef.current) return;

    const intervalTime = 40; // 40ms một lần cập nhật (~25 fps)
    const stepIncrement = intervalTime / 1000;

    const timer = setInterval(() => {
      setCurrentTime((prev) => {
        const nextTime = prev + stepIncrement;
        if (nextTime >= totalDuration) {
          return 0;
        }
        return nextTime;
      });
    }, intervalTime);

    return () => clearInterval(timer);
  }, [isPlaying, totalDuration]);

  // Xử lý khi có video thật cập nhật currentTime
  const handleVideoTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleVideoEnded = () => {
    setCurrentTime(0);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(() => {});
    }
  };

  const handleStepClick = (step: PipelineStep) => {
    setCurrentTime(step.startTime);
    setIsPlaying(true);

    if (videoRef.current) {
      videoRef.current.currentTime = step.startTime;
      videoRef.current.play().catch(() => {});
    }
  };

  const togglePlayPause = () => {
    if (isPlaying) {
      setIsPlaying(false);
      if (videoRef.current) videoRef.current.pause();
    } else {
      setIsPlaying(true);
      if (videoRef.current) videoRef.current.play().catch(() => {});
    }
  };

  const toggleMute = () => {
    setIsMuted((prev) => {
      const next = !prev;
      if (videoRef.current) {
        videoRef.current.muted = next;
      }
      return next;
    });
  };

  const restartPipeline = () => {
    setCurrentTime(0);
    setIsPlaying(true);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(() => {});
    }
  };

  const handleScrubberClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    const newTime = ratio * totalDuration;
    setCurrentTime(newTime);
    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
      if (!isPlaying) {
        setIsPlaying(true);
        videoRef.current.play().catch(() => {});
      }
    }
  };

  // Định dạng thời gian dạng 0:02.83
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const millis = Math.floor((seconds % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, "0")}.${millis
      .toString()
      .padStart(2, "0")}`;
  };

  // Định dạng khoảng thời gian bước dạng 00:00 – 00:08
  const formatStepTimeRange = (start: number, end: number) => {
    const formatSec = (s: number) => {
      const m = Math.floor(s / 60);
      const sec = Math.floor(s % 60);
      return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
    };
    return `${formatSec(start)} – ${formatSec(end)}`;
  };

  return (
    <section
      id="pipeline-showcase"
      className="relative w-full overflow-hidden border-y border-slate-200/70 bg-slate-50/80 pt-16 pb-24 text-automl-ink transition-colors dark:border-white/10 dark:bg-[#060b16] sm:pt-20 sm:pb-32"
    >
      {/* Ánh sáng ambient glow chuyển tiếp liền kề giữa Hero và Pipeline */}
      <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-56 w-[800px] rounded-full bg-blue-500/15 blur-[120px] dark:bg-blue-600/20" />
      <div className="pointer-events-none absolute -bottom-20 right-10 h-[450px] w-[550px] rounded-full bg-indigo-500/10 blur-[120px] dark:bg-indigo-600/10" />

      {/* Đường hairline mờ dần 2 đầu tạo sự phân định tinh tế không bị vệt ngăn cách thô */}
      <div className="pointer-events-none absolute top-0 inset-x-0 flex justify-center">
        <div className="h-[1px] w-full max-w-4xl bg-gradient-to-r from-transparent via-blue-500/25 via-cyan-400/20 to-transparent" />
      </div>

      <div className="mx-auto max-w-[1360px] px-4 sm:px-6 lg:px-8">
        {/* Header Section */}
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-3xl font-black tracking-tight text-slate-900 sm:text-4xl lg:text-5xl dark:text-white">
            {t("pipeline.title")}
          </h2>

          <p className="mt-3.5 text-base font-semibold leading-relaxed text-slate-600 sm:text-lg dark:text-slate-300">
            {t("pipeline.subtitle")}
          </p>
        </div>

        {/* 2-Column Showcase Grid */}
        <div className="mt-12 grid gap-10 lg:grid-cols-12 lg:items-center xl:gap-14">
          {/* CỘT TRÁI: Player Preview (Interactive Video / AI Detection Canvas) */}
          <div className="lg:col-span-7 xl:col-span-7">
            <div className="group relative rounded-[2rem] border border-slate-200/90 bg-white p-2.5 shadow-2xl shadow-slate-200/50 transition-all duration-300 sm:p-3 dark:border-white/10 dark:bg-slate-950/80 dark:shadow-black/50 backdrop-blur-xl">
              {/* macOS Window Controls Topbar */}
              <div className="mb-2.5 flex items-center justify-between px-2 pt-1">
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-rose-500/80 ring-1 ring-rose-500/30" />
                  <span className="h-3 w-3 rounded-full bg-amber-500/80 ring-1 ring-amber-500/30" />
                  <span className="h-3 w-3 rounded-full bg-emerald-500/80 ring-1 ring-emerald-500/30" />
                  <span className="ml-2 hidden text-[11px] font-bold text-slate-400 sm:inline-block">
                    HAutoML Engine • Pipeline Interactive Demo & Execution Player
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    LIVE
                  </span>
                  <span className="rounded-lg border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] font-extrabold text-slate-700 dark:border-white/10 dark:bg-white/10 dark:text-slate-300">
                    FPS: 60.0
                  </span>
                </div>
              </div>

              {/* Main Media Canvas (Video OR Simulated Visual Scene) */}
              <div className="relative aspect-[16/10] w-full overflow-hidden rounded-2xl bg-slate-950 shadow-inner sm:aspect-[16/9.5]">
                {DEMO_VIDEO_URL ? (
                  /* KHI BẠN CUNG CẤP VIDEO */
                  <video
                    ref={videoRef}
                    src={DEMO_VIDEO_URL}
                    playsInline
                    muted={isMuted}
                    autoPlay
                    loop
                    onTimeUpdate={handleVideoTimeUpdate}
                    onEnded={handleVideoEnded}
                    className="h-full w-full object-contain bg-slate-950"
                  />
                ) : (
                  /* MÔ PHỎNG TRỰC QUAN KHI CHƯA CÓ VIDEO */
                  <div className="relative h-full w-full select-none overflow-hidden">
                    {/* Scene 1: Lựa chọn & Tinh chỉnh mô hình (Computer Vision Object Detection như mẫu ảnh) */}
                    {activeStep.visualType === "model_selection" && (
                      <div className="relative h-full w-full">
                        {/* Background Airport & Aircraft Setup */}
                        <div className="absolute inset-0 bg-gradient-to-tr from-slate-900 via-slate-800 to-sky-950">
                          {/* Sky / Runway Graphic Simulation */}
                          <div className="absolute inset-0 opacity-40 bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:16px_16px]" />
                        </div>

                        {/* Silhouette / Mockup of Aircraft in Center */}
                        <div className="absolute inset-0 flex items-center justify-center p-6">
                          <div className="relative flex h-full w-full items-center justify-center">
                            {/* Bounding Box 1: Airplane / Main Body */}
                            <div className="absolute left-[15%] top-[18%] h-[68%] w-[68%] rounded-xl border-2 border-cyan-400 bg-cyan-500/10 backdrop-blur-[1px] transition-all duration-300">
                              <span className="absolute -top-3.5 left-2 rounded-md bg-cyan-500 px-2 py-0.5 text-[10px] font-extrabold uppercase text-slate-950 shadow">
                                AIRCRAFT A380 • 99.4%
                              </span>
                            </div>

                            {/* Bounding Box 2: Person (Ground Crew) */}
                            <div className="absolute left-[20%] top-[48%] h-[24%] w-[12%] rounded-lg border-2 border-blue-400 bg-blue-500/15 backdrop-blur-[1px]">
                              <span className="absolute -top-3 left-1 rounded bg-blue-500 px-1.5 py-0.5 text-[9px] font-bold text-white">
                                person 98.2%
                              </span>
                            </div>

                            {/* Bounding Box 3: Person 2 */}
                            <div className="absolute left-[36%] top-[50%] h-[22%] w-[10%] rounded-lg border-2 border-blue-400 bg-blue-500/15 backdrop-blur-[1px]">
                              <span className="absolute -top-3 left-1 rounded bg-blue-500 px-1.5 py-0.5 text-[9px] font-bold text-white">
                                person 97.9%
                              </span>
                            </div>

                            {/* Bounding Box 4: Cargo Container (Pink/Magenta like screenshot) */}
                            <div className="absolute left-[40%] top-[56%] h-[26%] w-[16%] rounded-lg border-2 border-pink-500 bg-pink-500/20 backdrop-blur-[1px]">
                              <span className="absolute -top-3 left-1 rounded bg-pink-500 px-1.5 py-0.5 text-[9px] font-bold text-white">
                                cargo 96.5%
                              </span>
                            </div>

                            {/* Bounding Box 5: Cargo Box 2 */}
                            <div className="absolute left-[54%] top-[54%] h-[28%] w-[14%] rounded-lg border-2 border-pink-500 bg-pink-500/20 backdrop-blur-[1px]">
                              <span className="absolute -top-3 left-1 rounded bg-pink-500 px-1.5 py-0.5 text-[9px] font-bold text-white">
                                cargo 95.8%
                              </span>
                            </div>

                            {/* Scanning laser beam animation */}
                            <div className="pointer-events-none absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_15px_#22d3ee] animate-pulse" />
                          </div>
                        </div>

                        {/* Top Overlay Bar */}
                        <div className="absolute left-3 top-3 flex items-center gap-2 rounded-lg border border-white/15 bg-black/60 px-2.5 py-1 text-xs text-white backdrop-blur">
                          <Activity className="h-3.5 w-3.5 text-cyan-400 animate-spin" />
                          <span className="font-bold">YOLOv11-AutoML • Foundation Fine-Tuning</span>
                        </div>
                      </div>
                    )}

                    {/* Scene 2: Huấn luyện phân tán thông minh (Distributed Cluster Nodes) */}
                    {activeStep.visualType === "distributed_training" && (
                      <div className="relative h-full w-full bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-6 flex flex-col justify-between">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-bold text-indigo-300">
                            <Server className="h-4 w-4 text-indigo-400" />
                            <span>Distributed Ray Cluster • 4 Nodes Active</span>
                          </div>
                          <span className="text-xs font-black text-emerald-400">
                            Epoch 48/50 (96%)
                          </span>
                        </div>

                        {/* 4 Node cards grid */}
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 my-auto">
                          {[1, 2, 3, 4].map((node) => (
                            <div
                              key={node}
                              className="rounded-xl border border-white/10 bg-white/5 p-3 backdrop-blur"
                            >
                              <div className="flex items-center justify-between text-[11px] font-bold text-slate-300">
                                <span>Worker {node}</span>
                                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                              </div>
                              <p className="mt-2 text-xs font-black text-white">GPU RTX 4090</p>
                              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                                <div
                                  className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-300"
                                  style={{ width: `${85 + node * 3}%` }}
                                />
                              </div>
                              <p className="mt-1 text-[10px] text-slate-400">Load: {85 + node * 3}%</p>
                            </div>
                          ))}
                        </div>

                        {/* Training Metrics Footer */}
                        <div className="flex items-center justify-between border-t border-white/10 pt-3 text-xs text-slate-300">
                          <span>Loss: <strong>0.0382</strong></span>
                          <span>mAP@50: <strong>94.8%</strong></span>
                          <span>Sync Latency: <strong>1.2ms</strong></span>
                        </div>
                      </div>
                    )}

                    {/* Scene 3: Triển khai & Kiểm thử tức thì (1-Click API Deployment) */}
                    {activeStep.visualType === "api_deployment" && (
                      <div className="relative h-full w-full bg-gradient-to-br from-slate-950 via-slate-900 to-emerald-950 p-6 flex flex-col justify-between">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-400">
                            <Zap className="h-4 w-4 text-emerald-400" />
                            <span>1-Click REST API Gateway • Live Production</span>
                          </div>
                          <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs font-black text-emerald-300">
                            Status: 200 OK
                          </span>
                        </div>

                        {/* Code API Snippet Mock */}
                        <div className="my-auto rounded-xl border border-white/10 bg-black/60 p-4 font-mono text-xs text-slate-200">
                          <div className="text-slate-400">{"// Ready-to-use API Endpoint"}</div>
                          <div className="mt-1 text-cyan-300">
                            POST <span className="text-white">https://api.hautoml.fit-haui.edu.vn/v1/predict</span>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-4 text-[11px] text-slate-300">
                            <div>Latency: <span className="font-bold text-emerald-400">8.4ms</span></div>
                            <div>Throughput: <span className="font-bold text-blue-400">1,250 req/s</span></div>
                            <div>Availability: <span className="font-bold text-indigo-300">99.99%</span></div>
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-xs text-slate-400">
                          <span>Docker & Kubernetes Ready</span>
                          <span className="text-emerald-400 font-bold">Auto-scaling Enabled</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Bottom Video Controls Overlay (Timecode, Play/Pause, Progress Bar) */}
                <div className="absolute inset-x-0 bottom-0 z-20 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-3 pt-6">
                  <div className="flex items-center justify-between gap-3 text-xs text-white">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={togglePlayPause}
                        className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/20 hover:bg-white/30 text-white transition backdrop-blur active:scale-95"
                        aria-label={isPlaying ? t("pipeline.pause") : t("pipeline.play")}
                      >
                        {isPlaying ? <Pause className="h-3.5 w-3.5 fill-white" /> : <Play className="h-3.5 w-3.5 fill-white ml-0.5" />}
                      </button>

                      <button
                        type="button"
                        onClick={restartPipeline}
                        className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition backdrop-blur active:scale-95"
                        title={t("pipeline.restart")}
                        aria-label={t("pipeline.restart")}
                      >
                        <RotateCcw className="h-3 w-3" />
                      </button>

                      <button
                        type="button"
                        onClick={toggleMute}
                        className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition backdrop-blur active:scale-95"
                        title={isMuted ? "Bật âm thanh" : "Tắt âm thanh"}
                        aria-label={isMuted ? "Unmute" : "Mute"}
                      >
                        {isMuted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
                      </button>

                      {/* Timecode Badge */}
                      <span className="rounded-md bg-black/60 px-2 py-0.5 font-mono text-[11px] font-bold text-slate-200 border border-white/10">
                        {formatTime(currentTime)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold text-slate-300">
                        {activeStep.badge}
                      </span>
                      <span className="rounded bg-blue-600 px-1.5 py-0.5 text-[10px] font-extrabold text-white">
                        {activeStep.stepNumber}
                      </span>
                    </div>
                  </div>

                  {/* Scrubber track across bottom of preview (Interactive Click-to-seek) */}
                  <div
                    onClick={handleScrubberClick}
                    className="group/track mt-2.5 flex h-3 cursor-pointer items-center"
                    title="Nhấn để tua đến thời điểm này"
                  >
                    <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-white/20 transition-all group-hover/track:h-2">
                      <div
                        className="h-full bg-gradient-to-r from-blue-500 via-indigo-400 to-cyan-400 transition-all duration-75"
                        style={{ width: `${(currentTime / totalDuration) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* CỘT PHẢI: Interactive Steps List (Theo sát mẫu giao diện 01, 02, 03) */}
          <div className="space-y-4 lg:col-span-5 xl:col-span-5">
            <div className="divide-y divide-slate-200 dark:divide-white/10">
              {PIPELINE_STEPS.map((step, idx) => {
                const isActive = idx === activeStepIndex;

                return (
                  <div
                    key={step.id}
                    onClick={() => handleStepClick(step)}
                    className={cn(
                      "group cursor-pointer py-6 transition-all duration-200 select-none",
                      isActive ? "opacity-100" : "opacity-75 hover:opacity-100"
                    )}
                  >
                    <div className="flex items-start justify-between gap-4">
                      {/* Tiêu đề bước & Thời lượng */}
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              "inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[11px] font-bold transition-colors",
                              isActive
                                ? "bg-blue-500/10 text-blue-600 dark:bg-cyan-500/15 dark:text-cyan-300"
                                : "bg-slate-200/70 text-slate-600 dark:bg-white/10 dark:text-slate-400"
                            )}
                          >
                            {formatStepTimeRange(step.startTime, step.endTime)}
                          </span>
                        </div>
                        <h3
                          className={cn(
                            "text-lg font-black transition-colors sm:text-xl",
                            isActive
                              ? "text-slate-900 dark:text-white"
                              : "text-slate-600 dark:text-slate-400 group-hover:text-slate-900 dark:group-hover:text-white"
                          )}
                        >
                          {t(`pipeline.${step.titleKey}`)}
                        </h3>
                      </div>

                      {/* Số thứ tự bước (01, 02, 03, 04) */}
                      <span
                        className={cn(
                          "font-mono text-base font-black transition-colors sm:text-lg",
                          isActive
                            ? "text-blue-600 dark:text-cyan-400"
                            : "text-slate-400 dark:text-slate-500 group-hover:text-slate-600 dark:group-hover:text-slate-400"
                        )}
                      >
                        {step.stepNumber}
                      </span>
                    </div>

                    {/* Nội dung mô tả (chỉ hiển thị chi tiết khi kích hoạt) */}
                    <div
                      className={cn(
                        "grid transition-all duration-300",
                        isActive
                          ? "grid-rows-[1fr] opacity-100 mt-2.5"
                          : "grid-rows-[0fr] opacity-0"
                      )}
                    >
                      <div className="overflow-hidden">
                        <p className="text-sm font-semibold leading-relaxed text-slate-600 dark:text-slate-300">
                          {t(`pipeline.${step.descKey}`)}
                        </p>

                        {/* Thanh Progress Bar dưới bước đang active (như trong ảnh mẫu) */}
                        <div className="mt-4 h-1 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-white/15">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-blue-600 to-indigo-500 transition-all duration-75 ease-linear"
                            style={{ width: `${currentStepProgress}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Quick Action Button */}
            <div className="pt-4">
              <Link
                href="/register"
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/25 transition-all duration-200 hover:scale-[1.02] hover:bg-blue-500 active:scale-[0.98]"
              >
                <span>{t("startFree")}</span>
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
