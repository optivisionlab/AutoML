"use client";

import React, { PointerEvent, WheelEvent, useMemo, useState } from "react";
import {
  AlertTriangle,
  Award,
  Check,
  CheckCircle2,
  Clock3,
  Cpu,
  Database,
  Layers,
  Maximize2,
  Minimize2,
  Minus,
  Move,
  Network,
  Plus,
  RotateCcw,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { cn } from "@/shared/lib/utils";
import { useTranslations } from "next-intl";
import {
  ProgressMapNode,
  ProgressMapPipeline,
  progressMapSample,
} from "@/features/training/constants/progressMapSample";
import { formatPipelineValue, GraphViewMode } from "@/features/training/utils/pipelineGraphBuilder";
import {
  ModelDetailModal,
  type ModelDetailData,
} from "@/features/training/components/modal/ModelDetailModal";


type ProgressMapProps = {
  pipeline?: ProgressMapPipeline;
  className?: string;
  viewMode?: GraphViewMode;
  onViewModeChange?: (mode: GraphViewMode) => void;
};

const statusNodeStyles: Record<ProgressMapNode["status"], { ring: string; badge: string; icon: string }> = {
  done: {
    ring: "border-2 border-emerald-500 bg-emerald-500 text-white shadow-md shadow-emerald-500/30",
    badge: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    icon: "text-emerald-600 dark:text-emerald-400",
  },
  running: {
    ring: "border-2 border-cyan-400 bg-cyan-500 text-white shadow-xl shadow-cyan-400/50 ring-4 ring-cyan-400/30 animate-pulse",
    badge: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20",
    icon: "text-cyan-600 dark:text-cyan-400",
  },
  pending: {
    ring: "border-2 border-slate-300 bg-white text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500",
    badge: "bg-slate-500/10 text-slate-500 dark:text-slate-400 border-slate-500/20",
    icon: "text-slate-400 dark:text-slate-500",
  },
  failed: {
    ring: "border-2 border-red-500 bg-red-500 text-white shadow-lg shadow-red-500/30",
    badge: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
    icon: "text-red-600 dark:text-red-400",
  },
};

const MAP_WIDTH = 1160;
const MAP_HEIGHT = 440;
const NODE_RADIUS = 13;
const MIN_ZOOM = 0.6;
const MAX_ZOOM = 1.9;

export default function ProgressMap({
  pipeline = progressMapSample,
  className,
  viewMode,
  onViewModeChange,
}: ProgressMapProps) {
  const t = useTranslations("ProgressMap");
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const [selectedNodeId, setSelectedNodeId] = useState<string>(
    () =>
      pipeline.nodes.find((node) => node.status === "running")?.id ||
      pipeline.nodes.find((node) => node.isBestModel)?.id ||
      pipeline.nodes[0]?.id ||
      "",
  );

  const [selectedDetailModel, setSelectedDetailModel] = useState<ModelDetailData | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragStart, setDragStart] = useState<{
    pointerId: number;
    x: number;
    y: number;
    panX: number;
    panY: number;
  } | null>(null);

  // Cập nhật selectedNode khi pipeline thay đổi
  const selectedNode = useMemo(() => {
    const found = pipeline.nodes.find((node) => node.id === selectedNodeId);
    return found || pipeline.nodes[0];
  }, [pipeline.nodes, selectedNodeId]);

  const nodeById = useMemo(
    () => new Map(pipeline.nodes.map((node) => [node.id, node])),
    [pipeline.nodes],
  );

  const edges = useMemo(
    () =>
      pipeline.nodes.flatMap((node) =>
        (node.parentIds || [])
          .map((parentId) => {
            const parent = nodeById.get(parentId);
            if (!parent) return null;
            return { from: parent, to: node };
          })
          .filter(Boolean),
      ) as Array<{ from: ProgressMapNode; to: ProgressMapNode }>,
    [nodeById, pipeline.nodes],
  );

  const clampZoom = (nextZoom: number) =>
    Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(nextZoom.toFixed(2))));

  const updateZoom = (nextZoom: number) => {
    setZoom(clampZoom(nextZoom));
  };

  const resetViewport = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragStart({
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      panX: pan.x,
      panY: pan.y,
    });
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragStart || dragStart.pointerId !== event.pointerId) return;

    setPan({
      x: dragStart.panX + event.clientX - dragStart.x,
      y: dragStart.panY + event.clientY - dragStart.y,
    });
  };

  const handlePointerUp = (event: PointerEvent<HTMLDivElement>) => {
    if (dragStart?.pointerId === event.pointerId) {
      setDragStart(null);
    }
  };

  const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
    if (!event.ctrlKey && !event.metaKey) return;

    event.preventDefault();
    event.stopPropagation();

    const nextZoom = clampZoom(zoom - event.deltaY * 0.002);
    if (nextZoom === zoom) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const cursorX = event.clientX - rect.left;
    const cursorY = event.clientY - rect.top;
    const zoomRatio = nextZoom / zoom;

    setPan((currentPan) => ({
      x: cursorX - (cursorX - currentPan.x) * zoomRatio,
      y: cursorY - (cursorY - currentPan.y) * zoomRatio,
    }));
    setZoom(nextZoom);
  };

  const mapContent = (
    <div
      className={cn(
        "overflow-hidden rounded-[22px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] shadow-sm",
        isFullscreen && "fixed inset-0 z-50 flex h-full flex-col rounded-none border-0 bg-white dark:bg-[#08111f]",
        className,
      )}
    >
      {/* Header Toolbar */}
      <div className="flex flex-col gap-3 border-b border-[var(--automl-data-card-border)] px-5 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-500/10 text-automl-blue dark:bg-cyan-500/10 dark:text-cyan-400">
              <Network className="h-4 w-4" />
            </span>
            <h2 className="text-lg font-extrabold tracking-tight text-[var(--automl-data-text)]">
              {pipeline.title || t("title")}
            </h2>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {pipeline.nodes.length} nodes
            </span>
          </div>
          <p className="mt-1 text-xs font-semibold text-[var(--automl-data-muted)]">
            {t("predictionColumn", { column: pipeline.predictionColumn || "—" })} · {t("rankBy", { metric: pipeline.rankBy || "—" })}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {onViewModeChange && (
            <div className="flex items-center rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-0.5">
              <button
                type="button"
                onClick={() => onViewModeChange("expanded")}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-bold transition-all",
                  viewMode === "expanded"
                    ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-cyan-300"
                    : "text-[var(--automl-data-muted)] hover:text-[var(--automl-data-text)]",
                )}
              >
                <Cpu className="h-3.5 w-3.5" />
                Mở rộng mô hình
              </button>
              <button
                type="button"
                onClick={() => onViewModeChange("compact")}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-bold transition-all",
                  viewMode === "compact"
                    ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-cyan-300"
                    : "text-[var(--automl-data-muted)] hover:text-[var(--automl-data-text)]",
                )}
              >
                <Layers className="h-3.5 w-3.5" />
                Thu gọn giai đoạn
              </button>
            </div>
          )}

          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-8 w-8 rounded-xl border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] shadow-none"
            onClick={() => setIsFullscreen((value) => !value)}
            title={isFullscreen ? t("exitFullscreen") : t("openFullscreen")}
          >
            {isFullscreen ? (
              <Minimize2 className="h-4 w-4" />
            ) : (
              <Maximize2 className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Main Canvas & Side Inspector */}
      <div
        className={cn(
          "grid min-h-[460px] grid-cols-1 lg:grid-cols-[1fr_320px] xl:grid-cols-[1fr_360px]",
          isFullscreen && "min-h-0 flex-1 lg:grid-cols-[1fr_380px]",
        )}
      >
        {/* SVG Interactive Canvas */}
        <div
          className={cn(
            "relative min-h-[460px] overflow-hidden overscroll-contain bg-slate-50/60 dark:bg-[#070e1b]",
            dragStart ? "cursor-grabbing" : "cursor-grab",
          )}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onWheel={handleWheel}
        >
          {/* Zoom Controls Overlay */}
          <div
            className="absolute left-4 top-4 z-20 flex items-center gap-1 rounded-2xl border border-slate-200/90 bg-white/95 p-1 shadow-sm backdrop-blur dark:border-white/10 dark:bg-slate-900/90"
            onPointerDown={(event) => event.stopPropagation()}
          >
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-7 w-7 rounded-lg text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10"
              onClick={(event) => {
                event.stopPropagation();
                updateZoom(zoom - 0.1);
              }}
              title={t("zoomOut")}
            >
              <Minus className="h-3.5 w-3.5" />
            </Button>
            <span className="min-w-10 text-center text-xs font-black text-slate-700 dark:text-slate-200">
              {Math.round(zoom * 100)}%
            </span>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-7 w-7 rounded-lg text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10"
              onClick={(event) => {
                event.stopPropagation();
                updateZoom(zoom + 0.1);
              }}
              title={t("zoomIn")}
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-7 w-7 rounded-lg text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10"
              onClick={(event) => {
                event.stopPropagation();
                resetViewport();
              }}
              title={t("resetView")}
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          </div>

          <div className="absolute bottom-4 left-4 z-20 inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/95 px-3 py-1 text-[11px] font-bold text-slate-600 shadow-sm backdrop-blur dark:border-white/10 dark:bg-slate-900/90 dark:text-slate-300">
            <Move className="h-3 w-3 text-automl-blue dark:text-cyan-400" />
            {t("panHint")}
          </div>

          {/* Canvas Wrapper */}
          <div
            className="relative h-[440px] w-[1160px] origin-top-left select-none transition-transform duration-75"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            }}
          >
            <svg
              className="pointer-events-none absolute inset-0 z-0 h-full w-full"
              viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
            >
              <defs>
                <pattern
                  id="pipeline-grid"
                  width="36"
                  height="36"
                  patternUnits="userSpaceOnUse"
                >
                  <circle
                    cx="2"
                    cy="2"
                    r="1"
                    fill={isDark ? "rgba(255, 255, 255, 0.07)" : "rgba(0, 0, 0, 0.04)"}
                  />
                </pattern>

                <linearGradient id="edge-gradient-active" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#2563eb" />
                  <stop offset="100%" stopColor="#06b6d4" />
                </linearGradient>
              </defs>

              <rect width="100%" height="100%" fill="url(#pipeline-grid)" />

              {/* Dynamic Edges Derived Directly from depends_on */}
              {edges.map(({ from, to }) => {
                const fromX = (from.x / 100) * MAP_WIDTH;
                const fromY = (from.y / 100) * MAP_HEIGHT;
                const toX = (to.x / 100) * MAP_WIDTH;
                const toY = (to.y / 100) * MAP_HEIGHT;
                const direction = toX >= fromX ? 1 : -1;
                const startX = fromX + NODE_RADIUS * direction;
                const endX = toX - NODE_RADIUS * direction;
                const hasCurve = Math.abs(fromY - toY) > 8;
                const bend = Math.min(88, Math.max(36, Math.abs(endX - startX) * 0.46));
                const path = hasCurve
                  ? `M ${startX} ${fromY} C ${startX + bend * direction} ${fromY}, ${endX - bend * direction} ${toY}, ${endX} ${toY}`
                  : `M ${startX} ${fromY} L ${endX} ${toY}`;

                const isPending = to.status === "pending";
                const isFailed = to.status === "failed";
                const isRunning = to.status === "running" || from.status === "running";

                const outerStroke = isPending
                  ? isDark
                    ? "rgba(148, 163, 184, 0.1)"
                    : "#f1f5f9"
                  : isFailed
                    ? "rgba(239, 68, 68, 0.15)"
                    : isRunning
                      ? isDark
                        ? "rgba(6, 182, 212, 0.25)"
                        : "#cffafe"
                      : isDark
                        ? "rgba(56, 189, 248, 0.2)"
                        : "#dbeafe";

                const innerStroke = isPending
                  ? isDark
                    ? "#334155"
                    : "#cbd5e1"
                  : isFailed
                    ? "#ef4444"
                    : isRunning
                      ? "#06b6d4"
                      : isDark
                        ? "#38bdf8"
                        : "#2563eb";

                return (
                  <g key={`${from.id}-${to.id}`}>
                    <path
                      d={path}
                      fill="none"
                      stroke={outerStroke}
                      strokeLinecap="round"
                      strokeWidth="10"
                      vectorEffect="non-scaling-stroke"
                    />
                    <path
                      d={path}
                      fill="none"
                      stroke={innerStroke}
                      strokeDasharray={isPending ? "6 6" : isRunning ? "8 4" : undefined}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={isRunning ? "3.5" : "3"}
                      vectorEffect="non-scaling-stroke"
                      className={isRunning ? "animate-pulse" : undefined}
                    />
                  </g>
                );
              })}
            </svg>

            {/* Pipeline Nodes */}
            {pipeline.nodes.map((node) => {
              const selected = selectedNode?.id === node.id;
              const styles = statusNodeStyles[node.status] || statusNodeStyles.pending;

              return (
                <button
                  key={node.id}
                  type="button"
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelectedNodeId(node.id);
                  }}
                  className="group absolute z-10 flex w-36 -translate-x-1/2 cursor-pointer flex-col items-center text-center outline-none"
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                  title={`${node.label} (${t(`status.${node.status}`)})`}
                >
                  {/* Status Ring Icon */}
                  <span
                    className={cn(
                      "relative z-20 flex h-7 w-7 items-center justify-center rounded-full transition-all duration-200",
                      "-translate-y-1/2",
                      styles.ring,
                      selected && "ring-4 ring-blue-400/70 dark:ring-cyan-300/80 scale-115 shadow-xl",
                    )}
                  >
                    {node.status === "done" ? (
                      <Check className="h-4 w-4 stroke-[3] text-white" />
                    ) : node.status === "running" ? (
                      <Clock3 className="h-4 w-4 text-white animate-spin [animation-duration:2.5s]" />
                    ) : node.status === "failed" ? (
                      <XCircle className="h-4 w-4 text-white" />
                    ) : (
                      <span className="h-2 w-2 rounded-full bg-slate-400 dark:bg-slate-500" />
                    )}
                  </span>

                  {/* Node Label Box */}
                  <span
                    className={cn(
                      "relative z-10 mt-2.5 max-w-[144px] truncate rounded-xl px-2.5 py-1 text-xs font-black leading-tight shadow-sm transition-all duration-150",
                      selected
                        ? "bg-blue-600 text-white shadow-md ring-2 ring-blue-400/50 dark:bg-cyan-500 dark:text-slate-950 dark:ring-cyan-300/60"
                        : "border border-slate-200/90 bg-white/95 text-slate-800 shadow-xs hover:border-slate-400 dark:border-slate-700/90 dark:bg-[#0c1626]/95 dark:text-slate-100 dark:hover:border-cyan-500/50",
                    )}
                  >
                    {node.label}
                  </span>

                  {/* Subtitle / Category Badge */}
                  {node.isBestModel ? (
                    <span className="relative z-10 mt-1 inline-flex items-center gap-1 rounded-md bg-amber-500/15 px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-amber-600 dark:text-amber-400 border border-amber-500/30 shadow-xs">
                      <Sparkles className="h-2.5 w-2.5" /> Best Model
                    </span>
                  ) : node.subtitle ? (
                    <span
                      className={cn(
                        "relative z-10 mt-1 max-w-[130px] truncate rounded-md px-2 py-0.5 text-[10px] font-black uppercase tracking-wider transition-all",
                        selected
                          ? "bg-blue-100 text-blue-700 dark:bg-cyan-950 dark:text-cyan-300"
                          : "border border-slate-200/60 bg-slate-100/95 text-slate-500 dark:border-cyan-900/40 dark:bg-slate-950/90 dark:text-cyan-400",
                      )}
                    >
                      {node.subtitle}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>

        {/* Node Inspector Sidebar */}
        <aside className="flex flex-col border-t border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-5 lg:border-t-0 lg:border-l overflow-y-auto max-h-[580px]">
          {selectedNode ? (
            <div className="space-y-5">
              {/* Header Info */}
              <div className="rounded-2xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-[10px] font-black uppercase tracking-wider text-automl-blue dark:text-cyan-400">
                      {selectedNode.kind ? selectedNode.kind.replace(/_/g, " ") : "Pipeline Step"}
                    </span>
                    <h3 className="mt-0.5 truncate text-lg font-extrabold text-[var(--automl-data-text)]">
                      {selectedNode.label}
                    </h3>
                  </div>
                  {selectedNode.isBestModel && (
                    <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30">
                      <Award className="mr-1 h-3 w-3" /> Best
                    </Badge>
                  )}
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-2">
                    <span className="text-[10px] font-bold text-[var(--automl-data-muted)]">Trạng thái</span>
                    <div className="mt-0.5 flex items-center gap-1.5 font-extrabold">
                      {selectedNode.status === "done" && (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                      )}
                      {selectedNode.status === "running" && (
                        <Clock3 className="h-3.5 w-3.5 text-cyan-500 animate-spin" />
                      )}
                      {selectedNode.status === "failed" && (
                        <XCircle className="h-3.5 w-3.5 text-red-500" />
                      )}
                      {selectedNode.status === "pending" && (
                        <span className="h-2 w-2 rounded-full bg-slate-400" />
                      )}
                      <span>{t(`status.${selectedNode.status}`)}</span>
                    </div>
                  </div>

                  <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-2">
                    <span className="text-[10px] font-bold text-[var(--automl-data-muted)]">Thời gian</span>
                    <p className="mt-0.5 truncate font-extrabold text-[var(--automl-data-text)]">
                      {selectedNode.elapsed || "—"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Error Alert Banner */}
              {selectedNode.error && (
                <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-3.5 text-xs text-red-600 dark:text-red-400">
                  <div className="flex items-center gap-2 font-bold text-red-700 dark:text-red-300">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span>Lỗi thực thi</span>
                  </div>
                  <p className="mt-1 font-mono text-[11px] leading-relaxed break-words">
                    {selectedNode.error}
                  </p>
                </div>
              )}

              {/* Training Models Suite (if selecting train stage) */}
              {selectedNode.modelsList && Object.keys(selectedNode.modelsList).length > 0 && (
                <div>
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
                      Các mô hình huấn luyện
                    </h4>
                    <span className="text-xs font-bold text-automl-blue">
                      {Object.keys(selectedNode.modelsList).length} models
                    </span>
                  </div>
                  <div className="mt-2 space-y-2">
                    {Object.entries(selectedNode.modelsList).map(([modelName, modelInfo]) => {
                      const isBest = pipeline.rawPipeline?.select_best?.output?.best_model === modelName;
                      return (
                        <div
                          key={modelName}
                          onClick={() =>
                            setSelectedDetailModel({
                              model_name: modelName,
                              status: modelInfo.status,
                              error: modelInfo.error,
                              scores: modelInfo.scores,
                              best_params: modelInfo.best_params,
                            })
                          }
                          className={cn(
                            "group rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-3 text-xs transition-all cursor-pointer hover:border-blue-400 dark:hover:border-cyan-400 shadow-2xs",
                            isBest && "ring-1 ring-amber-400/70 bg-amber-500/5",
                          )}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-extrabold text-[var(--automl-data-text)] group-hover:text-automl-blue dark:group-hover:text-cyan-300 transition-colors">
                              {modelName}
                            </span>
                            <div className="flex items-center gap-1.5">
                              {isBest && (
                                <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-0 text-[10px] py-0 px-1.5 font-bold">
                                  Best
                                </Badge>
                              )}
                              <span className="text-[10px] font-bold text-[var(--automl-data-muted)] group-hover:text-automl-blue dark:group-hover:text-cyan-300">
                                Xem ➔
                              </span>
                            </div>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1 text-[11px]">
                            {modelInfo.scores && Object.keys(modelInfo.scores).length > 0 ? (
                              Object.entries(modelInfo.scores).map(([sKey, sVal]) => (
                                <span
                                  key={sKey}
                                  className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200/60 dark:border-slate-700/60"
                                >
                                  {sKey.toUpperCase()}: {formatPipelineValue(sVal)}
                                </span>
                              ))
                            ) : (
                              <span className="text-[11px] text-[var(--automl-data-muted)]">
                                Chưa có điểm số (—)
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Params Block */}
              <FormattedObjectBlock
                title={t("params")}
                data={selectedNode.rawParams || (selectedNode.params as Record<string, unknown>)}
                icon={Database}
              />

              {/* Output Block */}
              <FormattedObjectBlock
                title={t("result")}
                data={selectedNode.rawOutput || (selectedNode.result as Record<string, unknown>)}
                icon={Layers}
              />
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-6 text-center text-sm font-semibold text-[var(--automl-data-muted)]">
              {t("emptyData")}
            </div>
          )}
        </aside>
      </div>

      {/* Model Detail Modal */}
      <ModelDetailModal
        open={Boolean(selectedDetailModel)}
        onOpenChange={(open) => !open && setSelectedDetailModel(null)}
        model={selectedDetailModel}
        isBestModel={
          selectedDetailModel?.model_name ===
          pipeline.rawPipeline?.select_best?.output?.best_model
        }
        metricSort={pipeline.rankBy?.toLowerCase() || "r2"}
      />
    </div>
  );

  return mapContent;
}


const FormattedObjectBlock = ({
  title,
  data,
  icon: Icon,
}: {
  title: string;
  data?: Record<string, unknown>;
  icon?: React.ComponentType<{ className?: string }>;
}) => {
  const t = useTranslations("ProgressMap");

  if (!data || Object.keys(data).length === 0) {
    return (
      <div>
        <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
          {Icon && <Icon className="h-3.5 w-3.5" />}
          <span>{title}</span>
        </div>
        <p className="mt-1.5 text-xs font-semibold text-[var(--automl-data-muted)]">
          {t("emptyData")}
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
        {Icon && <Icon className="h-3.5 w-3.5" />}
        <span>{title}</span>
      </div>

      <div className="mt-2 space-y-1.5">
        {Object.entries(data).map(([key, value]) => {
          // Xử lý nested objects
          if (value !== null && typeof value === "object" && !Array.isArray(value)) {
            const nestedEntries = Object.entries(value as Record<string, unknown>);
            return (
              <div
                key={key}
                className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-2.5 text-xs"
              >
                <span className="font-bold text-slate-500 dark:text-slate-400">{key}</span>
                {nestedEntries.length > 0 ? (
                  <div className="mt-1.5 space-y-1 pl-2 border-l-2 border-[var(--automl-data-card-border)]">
                    {nestedEntries.map(([nKey, nVal]) => (
                      <div key={nKey} className="flex items-center justify-between text-[11px]">
                        <span className="text-[var(--automl-data-muted)] font-medium">{nKey}</span>
                        <span className="font-mono font-bold text-[var(--automl-data-text)]">
                          {formatPipelineValue(nVal)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className="text-right font-mono font-bold text-[var(--automl-data-text)] block">
                    —
                  </span>
                )}
              </div>
            );
          }

          return (
            <div
              key={key}
              className="flex items-center justify-between gap-3 rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-3 py-2 text-xs"
            >
              <span className="font-bold text-slate-500 dark:text-slate-400">{key}</span>
              <span className="text-right font-mono font-bold text-[var(--automl-data-text)] max-w-[180px] truncate">
                {formatPipelineValue(value)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
