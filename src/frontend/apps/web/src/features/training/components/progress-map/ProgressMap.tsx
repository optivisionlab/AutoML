"use client";

import React, {
  PointerEvent,
  WheelEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AlertTriangle,
  Award,
  Check,
  CheckCircle2,
  Clock3,
  Cpu,
  Database,
  Eye,
  FlaskConical,
  GitBranch,
  Layers,
  Maximize2,
  Minimize2,
  Minus,
  Move,
  Network,
  Plus,
  RotateCcw,
  ShieldCheck,
  SkipForward,
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
import {
  formatPipelineValue,
  GraphViewMode,
  normalizeNodeStatus,
  resolveModelBestParams,
  resolveModelHoldoutScores,
  resolveModelScores,
  resolveModelTrialStats,
} from "@/features/training/utils/pipelineGraphBuilder";
import {
  ModelDetailModal,
  type ModelDetailData,
} from "@/features/training/components/modal/ModelDetailModal";

type ProgressMapProps = {
  pipeline?: ProgressMapPipeline;
  className?: string;
  viewMode?: GraphViewMode;
  onViewModeChange?: (mode: GraphViewMode) => void;
  statusBadge?: React.ReactNode;
};

const statusNodeStyles: Record<
  ProgressMapNode["status"],
  { ring: string; card: string; badge: string; icon: string }
> = {
  done: {
    ring: "border-2 border-emerald-500 bg-emerald-500 text-white shadow-md shadow-emerald-500/30",
    card: "border-emerald-500/70 bg-emerald-50/95 text-slate-900 dark:border-emerald-500/60 dark:bg-emerald-950/60 dark:text-emerald-100",
    badge: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    icon: "text-emerald-600 dark:text-emerald-400",
  },
  running: {
    ring: "border-2 border-blue-500 bg-blue-500 text-white shadow-lg shadow-blue-500/50 ring-4 ring-blue-500/30 animate-pulse",
    card: "border-blue-500 bg-blue-50/95 text-blue-950 ring-4 ring-blue-500/30 shadow-lg shadow-blue-500/40 animate-pulse dark:border-cyan-400 dark:bg-cyan-950/80 dark:text-cyan-50 dark:ring-cyan-400/30",
    badge: "bg-blue-500/10 text-blue-600 dark:text-cyan-400 border-blue-500/20",
    icon: "text-blue-600 dark:text-cyan-400",
  },
  pending: {
    ring: "border-2 border-slate-300 bg-white text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500",
    card: "border-slate-200/90 bg-white/95 text-slate-800 hover:border-slate-400 dark:border-slate-700/90 dark:bg-[#0c1626]/95 dark:text-slate-100 dark:hover:border-cyan-500/50",
    badge: "bg-slate-500/10 text-slate-500 dark:text-slate-400 border-slate-500/20",
    icon: "text-slate-400 dark:text-slate-500",
  },
  failed: {
    ring: "border-2 border-red-500 bg-red-500 text-white shadow-lg shadow-red-500/30",
    card: "border-red-500 bg-red-50/95 text-red-950 dark:border-red-500/70 dark:bg-red-950/60 dark:text-red-100",
    badge: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
    icon: "text-red-600 dark:text-red-400",
  },
  skipped: {
    ring: "border-2 border-dashed border-slate-400 bg-slate-200 text-slate-500 opacity-70 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400",
    card: "border-slate-300 bg-slate-100/90 text-slate-500 opacity-60 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-400",
    badge: "bg-slate-500/10 text-slate-500 dark:text-slate-400 border-slate-400/30",
    icon: "text-slate-400 dark:text-slate-500",
  },
};

const DEFAULT_MAP_WIDTH = 1160;
const DEFAULT_MAP_HEIGHT = 480;
const NODE_RADIUS = 13;
const MIN_ZOOM = 0.32;
const MAX_ZOOM = 2.0;

const formatTimestampShort = (val?: string | null): string | null => {
  if (!val) return null;
  const num = Number(val);
  const date = !Number.isNaN(num) && /^\d+(\.\d+)?$/.test(val)
    ? new Date(num > 1e12 ? num : num * 1000)
    : new Date(val);
  if (Number.isNaN(date.getTime())) return val;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

export default function ProgressMap({
  pipeline = progressMapSample,
  className,
  viewMode,
  onViewModeChange,
  statusBadge,
}: ProgressMapProps) {
  const t = useTranslations("ProgressMap");
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const canvasViewportRef = useRef<HTMLDivElement | null>(null);
  const mapWidth = pipeline.canvasWidth || DEFAULT_MAP_WIDTH;
  const mapHeight = pipeline.canvasHeight || DEFAULT_MAP_HEIGHT;

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

  const clampZoom = useCallback(
    (nextZoom: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(nextZoom.toFixed(2)))),
    [],
  );

  // Automatically fit & center the entire branching DAG inside the available viewport
  const fitToView = useCallback(() => {
    const viewport = canvasViewportRef.current;
    if (!viewport) return;
    const rect = viewport.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const padX = 36;
    const padTop = 54;
    const padBottom = 46;
    const availW = Math.max(200, rect.width - padX * 2);
    const availH = Math.max(200, rect.height - padTop - padBottom);

    const nextZoom = clampZoom(Math.min(availW / mapWidth, availH / mapHeight, 1.05));
    const nextPanX = Math.round((rect.width - mapWidth * nextZoom) / 2);
    const nextPanY = Math.round(padTop + (availH - mapHeight * nextZoom) / 2);

    setZoom(nextZoom);
    setPan({ x: nextPanX, y: nextPanY });
  }, [clampZoom, mapHeight, mapWidth]);

  // Refit whenever pipeline layout dimensions, view mode, fullscreen, or container size changes
  useEffect(() => {
    const rafId = window.requestAnimationFrame(() => fitToView());
    return () => window.cancelAnimationFrame(rafId);
  }, [fitToView, pipeline.id, pipeline.nodes.length, viewMode, isFullscreen]);

  useEffect(() => {
    const viewport = canvasViewportRef.current;
    if (!viewport || typeof ResizeObserver === "undefined") return;
    let first = true;
    const observer = new ResizeObserver(() => {
      if (first) {
        first = false;
        fitToView();
      }
    });
    observer.observe(viewport);
    return () => observer.disconnect();
  }, [fitToView]);

  const selectedNode = useMemo(() => {
    const found = pipeline.nodes.find((node) => node.id === selectedNodeId);
    return (
      found ||
      pipeline.nodes.find((node) => node.status === "running") ||
      pipeline.nodes.find((node) => node.isBestModel) ||
      pipeline.nodes[0]
    );
  }, [pipeline.nodes, selectedNodeId]);

  const nodeById = useMemo(
    () => new Map(pipeline.nodes.map((node) => [node.id, node])),
    [pipeline.nodes],
  );

  const getNodeXY = useCallback(
    (node: ProgressMapNode) => ({
      x: node.px ?? (node.x / 100) * mapWidth,
      y: node.py ?? (node.y / 100) * mapHeight,
    }),
    [mapHeight, mapWidth],
  );

  const edges = useMemo(() => {
    const list: Array<{ from: ProgressMapNode; to: ProgressMapNode; isHoldoutEdge?: boolean }> = [];
    for (const node of pipeline.nodes) {
      for (const parentId of node.parentIds || []) {
        const parent = nodeById.get(parentId);
        if (parent) list.push({ from: parent, to: node });
      }
      for (const dashedParentId of node.dashedParentIds || []) {
        const parent = nodeById.get(dashedParentId);
        if (parent) list.push({ from: parent, to: node, isHoldoutEdge: true });
      }
    }
    return list;
  }, [nodeById, pipeline.nodes]);

  const updateZoom = (nextZoom: number) => {
    setZoom(clampZoom(nextZoom));
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

  const getStatusLabel = (status: ProgressMapNode["status"]) => {
    switch (status) {
      case "done":
        return t("status.done");
      case "running":
        return t("status.running");
      case "failed":
        return t("status.failed");
      case "skipped":
        return t("status.skipped");
      default:
        return t("status.pending");
    }
  };

  const metricsConfig = pipeline.rawPipeline?.model_selection?.params?.metrics;
  const bestModelName = pipeline.rawPipeline?.select_best?.output?.best_model;

  const openModelModalByName = (modelName: string, fallbackNode?: ProgressMapNode) => {
    const rawModel = pipeline.rawPipeline?.train?.output?.models?.[modelName];
    const resolvedScores = rawModel
      ? resolveModelScores(rawModel)
      : (fallbackNode?.rawOutput as Record<string, number | null>) || {};
    const resolvedParams = rawModel
      ? resolveModelBestParams(rawModel)
      : fallbackNode?.rawParams || null;
    const resolvedHoldout = rawModel
      ? resolveModelHoldoutScores(rawModel)
      : fallbackNode?.holdoutScores || null;
    const stats = rawModel
      ? resolveModelTrialStats(rawModel)
      : {
          nTrials: fallbackNode?.nTrials ?? null,
          nPruned: fallbackNode?.nPruned ?? null,
          bestTrial: fallbackNode?.bestTrial ?? null,
        };
    setSelectedDetailModel({
      model_name: modelName,
      status: rawModel?.status ?? fallbackNode?.status,
      error: rawModel?.error ?? fallbackNode?.error ?? null,
      scores: resolvedScores,
      best_params: resolvedParams,
      holdout_scores: resolvedHoldout,
      trials: rawModel?.trials ?? fallbackNode?.trials ?? null,
      best_trial: stats.bestTrial,
      n_trials: stats.nTrials,
      n_pruned: stats.nPruned,
    });
  };

  const branchCount = useMemo(
    () => pipeline.nodes.filter((n) => Boolean(n.branch)).length,
    [pipeline.nodes],
  );

  return (
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
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-500/10 text-automl-blue dark:bg-cyan-500/10 dark:text-cyan-400">
              <Network className="h-4 w-4" />
            </span>
            <h2 className="text-lg font-extrabold tracking-tight text-[var(--automl-data-text)]">
              {pipeline.title || t("title")}
            </h2>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {pipeline.nodes.length} nodes
              {branchCount > 0 ? ` · ${branchCount} nhánh` : ""}
            </span>
            {statusBadge}
          </div>
          <p className="mt-1 text-xs font-semibold text-[var(--automl-data-muted)]">
            {t("predictionColumn", { column: pipeline.predictionColumn || "—" })} ·{" "}
            {t("rankBy", { metric: pipeline.rankBy || "—" })}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {onViewModeChange && (
            <div className="flex flex-wrap items-center rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-0.5">
              <button
                type="button"
                onClick={() => onViewModeChange("detailed")}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-bold transition-all",
                  viewMode === "detailed"
                    ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-cyan-300"
                    : "text-[var(--automl-data-muted)] hover:text-[var(--automl-data-text)]",
                )}
              >
                <GitBranch className="h-3.5 w-3.5" />
                Chi tiết nhánh
              </button>
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
                Rẽ nhánh mô hình
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
                Thu gọn
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
          "grid min-h-[540px] grid-cols-1 lg:grid-cols-[1fr_350px] xl:grid-cols-[1fr_390px]",
          isFullscreen && "min-h-0 flex-1 lg:grid-cols-[1fr_420px]",
        )}
      >
        {/* SVG Interactive Canvas */}
        <div
          ref={canvasViewportRef}
          className={cn(
            "relative min-h-[540px] overflow-hidden overscroll-contain bg-slate-50/60 dark:bg-[#070e1b]",
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
                fitToView();
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

          {/* Dynamic Canvas Wrapper */}
          <div
            className="relative origin-top-left select-none transition-transform duration-100"
            style={{
              width: `${mapWidth}px`,
              height: `${mapHeight}px`,
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            }}
          >
            <svg
              className="pointer-events-none absolute inset-0 z-0 h-full w-full"
              viewBox={`0 0 ${mapWidth} ${mapHeight}`}
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
              </defs>

              <rect width="100%" height="100%" fill="url(#pipeline-grid)" />

              {/* Dynamic Edges Derived Directly from depends_on */}
              {edges.map(({ from, to, isHoldoutEdge }) => {
                const { x: fromX, y: fromY } = getNodeXY(from);
                const { x: toX, y: toY } = getNodeXY(to);

                if (isHoldoutEdge) {
                  // Route holdout evaluation branch cleanly underneath the training branches
                  const arcY = mapHeight - 18;
                  const path = `M ${fromX} ${fromY + NODE_RADIUS} C ${fromX} ${arcY}, ${toX} ${arcY}, ${toX} ${toY + NODE_RADIUS}`;
                  const labelX = (fromX + toX) / 2;
                  const labelY = arcY - 10;
                  return (
                    <g key={`holdout-${from.id}-${to.id}`}>
                      <path
                        d={path}
                        fill="none"
                        stroke={isDark ? "rgba(16, 185, 129, 0.25)" : "#a7f3d0"}
                        strokeWidth="6"
                        strokeLinecap="round"
                        vectorEffect="non-scaling-stroke"
                      />
                      <path
                        d={path}
                        fill="none"
                        stroke={isDark ? "#34d399" : "#059669"}
                        strokeDasharray="7 5"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        vectorEffect="non-scaling-stroke"
                      />
                      <rect
                        x={labelX - 58}
                        y={labelY - 12}
                        width="116"
                        height="20"
                        rx="10"
                        fill={isDark ? "#064e3b" : "#ecfdf5"}
                        stroke={isDark ? "#10b981" : "#6ee7b7"}
                        strokeWidth="1"
                      />
                      <text
                        x={labelX}
                        y={labelY + 2}
                        textAnchor="middle"
                        fontSize="10"
                        fontWeight="800"
                        fill={isDark ? "#6ee7b7" : "#047857"}
                      >
                        Holdout Evaluation
                      </text>
                    </g>
                  );
                }

                const direction = toX >= fromX ? 1 : -1;
                const startX = fromX + NODE_RADIUS * direction;
                const endX = toX - NODE_RADIUS * direction;
                const hasCurve = Math.abs(fromY - toY) > 8;
                const bend = Math.min(96, Math.max(40, Math.abs(endX - startX) * 0.48));
                const path = hasCurve
                  ? `M ${startX} ${fromY} C ${startX + bend * direction} ${fromY}, ${endX - bend * direction} ${toY}, ${endX} ${toY}`
                  : `M ${startX} ${fromY} L ${endX} ${toY}`;

                const isPending = to.status === "pending";
                const isSkipped = to.status === "skipped" || from.status === "skipped";
                const isFailed = to.status === "failed";
                const isRunning = to.status === "running" || from.status === "running";

                const outerStroke = isPending
                  ? isDark
                    ? "rgba(148, 163, 184, 0.1)"
                    : "#f1f5f9"
                  : isSkipped
                    ? isDark
                      ? "rgba(148, 163, 184, 0.08)"
                      : "#f8fafc"
                    : isFailed
                      ? "rgba(239, 68, 68, 0.15)"
                      : isRunning
                        ? isDark
                          ? "rgba(59, 130, 246, 0.28)"
                          : "#dbeafe"
                        : isDark
                          ? "rgba(16, 185, 129, 0.18)"
                          : "#d1fae5";

                const innerStroke =
                  isPending || isSkipped
                    ? isDark
                      ? "#334155"
                      : "#cbd5e1"
                    : isFailed
                      ? "#ef4444"
                      : isRunning
                        ? "#3b82f6"
                        : isDark
                          ? "#34d399"
                          : "#10b981";

                return (
                  <g key={`${from.id}-${to.id}`} opacity={isSkipped ? 0.6 : 1}>
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
                      strokeDasharray={
                        isPending ? "6 6" : isSkipped ? "4 5" : isRunning ? "8 4" : undefined
                      }
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
              const { x: nodePx, y: nodePy } = getNodeXY(node);

              return (
                <button
                  key={node.id}
                  type="button"
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelectedNodeId(node.id);
                  }}
                  className={cn(
                    "group absolute z-10 flex w-44 -translate-x-1/2 cursor-pointer flex-col items-center text-center outline-none transition-opacity duration-300",
                    node.status === "skipped" && "opacity-65",
                  )}
                  style={{ left: `${nodePx}px`, top: `${nodePy}px` }}
                  title={`${node.label} (${getStatusLabel(node.status)})`}
                >
                  {/* Status Ring Icon */}
                  <span
                    className={cn(
                      "relative z-20 flex h-7 w-7 items-center justify-center rounded-full transition-all duration-300",
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
                    ) : node.status === "skipped" ? (
                      <SkipForward className="h-3.5 w-3.5 text-slate-500 dark:text-slate-300" />
                    ) : (
                      <span className="h-2 w-2 rounded-full bg-slate-400 dark:bg-slate-500" />
                    )}
                  </span>

                  {/* Node Label & Inline Metric Box */}
                  <span
                    className={cn(
                      "relative z-10 mt-1.5 flex max-w-[168px] flex-col items-center rounded-xl border px-2.5 py-1.5 text-xs font-black leading-tight shadow-sm transition-all duration-300",
                      selected
                        ? "border-blue-600 bg-blue-600 text-white shadow-md ring-2 ring-blue-400/50 dark:border-cyan-400 dark:bg-cyan-500 dark:text-slate-950 dark:ring-cyan-300/60"
                        : styles.card,
                    )}
                  >
                    <span className="max-w-[152px] truncate">{node.label}</span>
                    {node.metricBadge && (
                      <span
                        className={cn(
                          "mt-0.5 max-w-[152px] truncate rounded px-1.5 py-0.5 font-mono text-[10px] font-bold",
                          selected
                            ? "bg-white/20 text-white dark:bg-slate-950/20 dark:text-slate-950"
                            : "bg-black/5 text-slate-700 dark:bg-white/10 dark:text-slate-200",
                        )}
                      >
                        {node.metricBadge}
                      </span>
                    )}
                  </span>

                  {/* Subtitle / Best Model Badge */}
                  {node.isBestModel && node.kind === "model_training" ? (
                    <span className="relative z-10 mt-1 inline-flex items-center gap-1 rounded-md bg-amber-500/15 px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-amber-600 dark:text-amber-400 border border-amber-500/30 shadow-xs">
                      <Sparkles className="h-2.5 w-2.5" /> Best Model
                    </span>
                  ) : node.subtitle ? (
                    <span
                      className={cn(
                        "relative z-10 mt-1 max-w-[164px] truncate rounded-md px-2 py-0.5 text-[10px] font-bold transition-all",
                        selected
                          ? "bg-blue-100 text-blue-700 dark:bg-cyan-950 dark:text-cyan-300"
                          : "border border-slate-200/60 bg-slate-100/95 text-slate-600 dark:border-cyan-900/40 dark:bg-slate-950/90 dark:text-cyan-400",
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
        <aside className="flex flex-col border-t border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-5 lg:border-t-0 lg:border-l overflow-y-auto max-h-[760px]">
          {selectedNode ? (
            <div className="space-y-5">
              {/* Header Info */}
              <div className="rounded-2xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] font-black uppercase tracking-wider text-automl-blue dark:text-cyan-400">
                        {selectedNode.kind ? selectedNode.kind.replace(/_/g, " ") : "Pipeline Step"}
                      </span>
                      {selectedNode.branch && (
                        <span className="rounded-md bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-bold text-automl-blue dark:bg-cyan-500/10 dark:text-cyan-300">
                          {selectedNode.branch}
                        </span>
                      )}
                    </div>
                    <h3 className="mt-1 break-words text-lg font-extrabold text-[var(--automl-data-text)]">
                      {selectedNode.label}
                    </h3>
                  </div>
                  {selectedNode.isBestModel && (
                    <Badge className="shrink-0 bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30">
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
                        <Clock3 className="h-3.5 w-3.5 text-blue-500 animate-spin" />
                      )}
                      {selectedNode.status === "failed" && (
                        <XCircle className="h-3.5 w-3.5 text-red-500" />
                      )}
                      {selectedNode.status === "skipped" && (
                        <SkipForward className="h-3.5 w-3.5 text-slate-400" />
                      )}
                      {selectedNode.status === "pending" && (
                        <span className="h-2 w-2 rounded-full bg-slate-400" />
                      )}
                      <span>{getStatusLabel(selectedNode.status)}</span>
                    </div>
                  </div>

                  <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-2">
                    <span className="text-[10px] font-bold text-[var(--automl-data-muted)]">Thời gian</span>
                    <p className="mt-0.5 truncate font-extrabold text-[var(--automl-data-text)]">
                      {selectedNode.elapsed || "—"}
                    </p>
                  </div>
                </div>

                {(selectedNode.startedAt || selectedNode.finishedAt) && (
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-[var(--automl-data-muted)]">
                    {selectedNode.startedAt && (
                      <span>Bắt đầu: {formatTimestampShort(selectedNode.startedAt)}</span>
                    )}
                    {selectedNode.finishedAt && (
                      <span>Kết thúc: {formatTimestampShort(selectedNode.finishedAt)}</span>
                    )}
                  </div>
                )}

                {/* Quick Action to open ModelDetailModal for model or HPO node */}
                {selectedNode.modelName && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-3 h-8 w-full rounded-xl text-xs font-bold border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] hover:bg-blue-50 hover:text-automl-blue dark:hover:bg-cyan-950/50 dark:hover:text-cyan-300"
                    onClick={() => openModelModalByName(selectedNode.modelName!, selectedNode)}
                  >
                    <Eye className="mr-1.5 h-3.5 w-3.5" />
                    Mở bảng chi tiết Trials & Tham số
                  </Button>
                )}

                {/* Jump to Best Model node from select_best */}
                {selectedNode.id === "select_best" && bestModelName && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-3 h-8 w-full rounded-xl text-xs font-bold border-amber-500/30 bg-amber-500/10 text-amber-700 hover:bg-amber-500/20 dark:text-amber-300"
                    onClick={() => {
                      const targetId = `model_${bestModelName}`;
                      if (nodeById.has(targetId)) {
                        setSelectedNodeId(targetId);
                      } else {
                        openModelModalByName(bestModelName);
                      }
                    }}
                  >
                    <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                    Xem nhánh mô hình tốt nhất ({bestModelName})
                  </Button>
                )}
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

              {/* Holdout Scores Card (for model, HPO, or select_best node) */}
              {selectedNode.holdoutScores && Object.keys(selectedNode.holdoutScores).length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    <span>Holdout Scores</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-1.5">
                    {Object.entries(selectedNode.holdoutScores).map(([hKey, hVal]) => (
                      <div
                        key={hKey}
                        className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 px-2.5 py-2 text-xs"
                      >
                        <span className="block font-mono text-[10px] font-black uppercase text-emerald-700 dark:text-emerald-300">
                          {hKey}
                        </span>
                        <span className="font-mono font-extrabold text-[var(--automl-data-text)]">
                          {formatPipelineValue(hVal)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Inline Trials Preview for Model / HPO Branch Nodes */}
              {(Array.isArray(selectedNode.trials) && selectedNode.trials.length > 0) ||
              selectedNode.nTrials !== undefined && selectedNode.nTrials !== null ? (
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
                      <FlaskConical className="h-3.5 w-3.5 text-automl-blue dark:text-cyan-400" />
                      <span>Chi tiết Trials</span>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] font-bold">
                      {selectedNode.nTrials !== null && selectedNode.nTrials !== undefined && (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                          {selectedNode.nTrials} trials
                        </span>
                      )}
                      {selectedNode.bestTrial !== null && selectedNode.bestTrial !== undefined && (
                        <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-amber-700 dark:text-amber-300">
                          Best #{selectedNode.bestTrial}
                        </span>
                      )}
                    </div>
                  </div>

                  {Array.isArray(selectedNode.trials) && selectedNode.trials.length > 0 ? (
                    <div className="mt-2 space-y-1.5 max-h-80 overflow-y-auto pr-0.5">
                      {selectedNode.trials.map((trial, idx) => {
                        const tIdx = trial.trial_id ?? trial.number ?? idx;
                        const isBest =
                          typeof selectedNode.bestTrial === "number" &&
                          (idx === selectedNode.bestTrial || tIdx === selectedNode.bestTrial);
                        const isPruned = String(trial.status || "").toLowerCase() === "pruned";
                        const scores = trial.scores ?? trial.cv_scores ?? {};

                        return (
                          <div
                            key={`sidebar-trial-${idx}`}
                            className={cn(
                              "rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-2.5 text-[11px]",
                              isBest && "border-amber-400/60 bg-amber-500/5",
                              isPruned && "opacity-70",
                            )}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono font-extrabold text-[var(--automl-data-text)]">
                                Trial #{tIdx}
                                {isBest && (
                                  <span className="ml-1.5 rounded bg-amber-500/20 px-1 py-0.5 text-[9px] font-black text-amber-700 dark:text-amber-300">
                                    BEST
                                  </span>
                                )}
                              </span>
                              <span
                                className={cn(
                                  "rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase",
                                  isPruned
                                    ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
                                    : normalizeNodeStatus(trial.status) === "done"
                                      ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                                      : normalizeNodeStatus(trial.status) === "failed"
                                        ? "bg-red-500/15 text-red-700 dark:text-red-300"
                                        : "bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
                                )}
                              >
                                {trial.status || "—"}
                              </span>
                            </div>
                            {Object.keys(scores).length > 0 && (
                              <div className="mt-1.5 flex flex-wrap gap-1">
                                {Object.entries(scores).map(([sKey, sVal]) => (
                                  <span
                                    key={sKey}
                                    className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                  >
                                    {sKey}: {formatPipelineValue(sVal)}
                                  </span>
                                ))}
                              </div>
                            )}
                            {trial.params && Object.keys(trial.params).length > 0 && (
                              <p className="mt-1 break-words font-mono text-[10px] text-[var(--automl-data-muted)]">
                                {formatPipelineValue(trial.params)}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="mt-1.5 text-[11px] font-medium text-[var(--automl-data-muted)]">
                      Chi tiết từng trial sẽ hiển thị sau khi lưu snapshot cuối.
                    </p>
                  )}
                </div>
              ) : null}

              {/* Quick Navigation to Parallel Model Branches when inspecting model_selection */}
              {selectedNode.id === "model_selection" &&
                Array.isArray(selectedNode.rawParams?.model_names) &&
                (selectedNode.rawParams.model_names as string[]).length > 0 && (
                  <div>
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
                        Các nhánh mô hình rẽ ra
                      </h4>
                      <span className="text-xs font-bold text-automl-blue">
                        {(selectedNode.rawParams.model_names as string[]).length} nhánh
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(selectedNode.rawParams.model_names as string[]).map((mName) => {
                        const targetNodeId = `model_${mName}`;
                        const existsOnMap = nodeById.has(targetNodeId);
                        const isBest = bestModelName === mName;
                        return (
                          <button
                            key={mName}
                            type="button"
                            onClick={() =>
                              existsOnMap
                                ? setSelectedNodeId(targetNodeId)
                                : openModelModalByName(mName)
                            }
                            className={cn(
                              "inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-[11px] font-bold transition-colors",
                              isBest
                                ? "border-amber-400/60 bg-amber-500/10 text-amber-700 hover:bg-amber-500/20 dark:text-amber-300"
                                : "border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] text-[var(--automl-data-text)] hover:border-blue-400 hover:text-automl-blue dark:hover:border-cyan-400 dark:hover:text-cyan-300",
                            )}
                          >
                            {isBest && <Sparkles className="h-3 w-3" />}
                            {mName}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

              {/* Training Models Suite (if selecting compact train stage) */}
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
                      const isBest = bestModelName === modelName;
                      const scores = resolveModelScores(modelInfo);
                      const mStatus = normalizeNodeStatus(modelInfo.status);

                      return (
                        <div
                          key={modelName}
                          onClick={() => openModelModalByName(modelName)}
                          className={cn(
                            "group rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-3 text-xs transition-all cursor-pointer hover:border-blue-400 dark:hover:border-cyan-400 shadow-2xs",
                            isBest && "ring-1 ring-amber-400/70 bg-amber-500/5",
                            mStatus === "running" && "border-blue-400/70 bg-blue-500/5",
                          )}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-extrabold text-[var(--automl-data-text)] group-hover:text-automl-blue dark:group-hover:text-cyan-300 transition-colors truncate">
                              {modelName}
                            </span>
                            <div className="flex items-center gap-1.5 shrink-0">
                              {isBest && (
                                <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-0 text-[10px] py-0 px-1.5 font-bold">
                                  Best
                                </Badge>
                              )}
                              <span className="text-[10px] font-bold text-[var(--automl-data-muted)] group-hover:text-automl-blue dark:group-hover:text-cyan-300">
                                Xem →
                              </span>
                            </div>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1 text-[11px]">
                            {Object.keys(scores).length > 0 ? (
                              Object.entries(scores).map(([sKey, sVal]) => (
                                <span
                                  key={sKey}
                                  className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200/60 dark:border-slate-700/60"
                                >
                                  {sKey.toUpperCase()}: {formatPipelineValue(sVal)}
                                </span>
                              ))
                            ) : (
                              <span className="text-[11px] text-[var(--automl-data-muted)]">
                                {mStatus === "running"
                                  ? "Đang huấn luyện..."
                                  : mStatus === "failed"
                                    ? "Thất bại"
                                    : "Chưa có điểm số (—)"}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Params Block (Full wrapping — zero truncation) */}
              <FormattedObjectBlock
                title={t("params")}
                data={selectedNode.rawParams || (selectedNode.params as Record<string, unknown>)}
                icon={Database}
              />

              {/* Output Block (Full wrapping — zero truncation) */}
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
        isBestModel={Boolean(
          selectedDetailModel?.model_name && selectedDetailModel.model_name === bestModelName,
        )}
        metricSort={pipeline.rankBy?.toLowerCase() || "r2"}
        metricsConfig={metricsConfig}
      />
    </div>
  );
}

const FormattedValueDisplay = ({ value }: { value: unknown }) => {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="font-mono text-[11px] text-[var(--automl-data-muted)]">—</span>;
    }
    return (
      <div className="mt-1.5 flex flex-wrap gap-1">
        {value.map((item, idx) => (
          <span
            key={idx}
            className="rounded-md border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] px-1.5 py-0.5 font-mono text-[10px] font-bold text-[var(--automl-data-text)] break-all"
          >
            {typeof item === "object" ? formatPipelineValue(item) : String(item)}
          </span>
        ))}
      </div>
    );
  }

  if (value !== null && typeof value === "object") {
    const nestedEntries = Object.entries(value as Record<string, unknown>);
    if (nestedEntries.length === 0) {
      return <span className="font-mono text-[11px] text-[var(--automl-data-muted)]">—</span>;
    }
    return (
      <div className="mt-1.5 space-y-1.5 border-l-2 border-[var(--automl-data-card-border)] pl-2.5">
        {nestedEntries.map(([nKey, nVal]) => {
          const isComplex = nVal !== null && typeof nVal === "object";
          if (isComplex) {
            return (
              <div key={nKey} className="text-[11px]">
                <span className="font-semibold text-[var(--automl-data-muted)]">
                  {nKey}
                  {Array.isArray(nVal) ? ` (${nVal.length})` : ""}
                </span>
                <FormattedValueDisplay value={nVal} />
              </div>
            );
          }
          return (
            <div key={nKey} className="flex items-start justify-between gap-2 text-[11px]">
              <span className="shrink-0 font-medium text-[var(--automl-data-muted)]">{nKey}</span>
              <span className="text-right font-mono font-bold text-[var(--automl-data-text)] break-all">
                {formatPipelineValue(nVal)}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <span className="text-right font-mono font-bold text-[var(--automl-data-text)] break-all">
      {formatPipelineValue(value)}
    </span>
  );
};

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

  // Filter out `models` (rendered as cards above) and `holdout_scores` (rendered as emerald card above)
  const entries = data
    ? Object.entries(data).filter(([k]) => k !== "models" && k !== "holdout_scores")
    : [];

  if (entries.length === 0) {
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
        {entries.map(([key, value]) => {
          const isComplex = value !== null && typeof value === "object";
          if (isComplex) {
            return (
              <div
                key={key}
                className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-2.5 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-bold text-slate-600 dark:text-slate-300">{key}</span>
                  {Array.isArray(value) && (
                    <span className="rounded bg-slate-200/70 px-1.5 py-0.5 text-[10px] font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                      {value.length}
                    </span>
                  )}
                </div>
                <FormattedValueDisplay value={value} />
              </div>
            );
          }

          return (
            <div
              key={key}
              className="flex items-start justify-between gap-3 rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-3 py-2 text-xs"
            >
              <span className="shrink-0 font-bold text-slate-500 dark:text-slate-400">{key}</span>
              <FormattedValueDisplay value={value} />
            </div>
          );
        })}
      </div>
    </div>
  );
};
