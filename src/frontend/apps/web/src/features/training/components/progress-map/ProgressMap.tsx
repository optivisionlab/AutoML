"use client";

import { PointerEvent, WheelEvent, useMemo, useState } from "react";
import {
  Check,
  Clock3,
  Expand,
  Info,
  Maximize2,
  Minimize2,
  Minus,
  Move,
  Plus,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/lib/utils";
import { useTranslations } from "next-intl";
import {
  ProgressMapNode,
  ProgressMapPipeline,
  progressMapSample,
} from "@/features/training/constants/progressMapSample";

type ProgressMapProps = {
  pipeline?: ProgressMapPipeline;
  className?: string;
};

const statusClassName: Record<ProgressMapNode["status"], string> = {
  done: "border-2 border-blue-600 bg-blue-600 text-white shadow-md shadow-blue-500/30 dark:border-cyan-300 dark:bg-blue-600 dark:text-white dark:shadow-cyan-500/30",
  running: "border-2 border-cyan-400 bg-cyan-500 text-white shadow-xl shadow-cyan-400/50 ring-4 ring-cyan-400/30 animate-pulse",
  pending: "border-2 border-slate-300 bg-white text-slate-400 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-400",
  failed: "border-2 border-red-500 bg-red-500 text-white shadow-lg shadow-red-500/30",
};

const MAP_WIDTH = 1120;
const MAP_HEIGHT = 420;
const NODE_RADIUS = 12;
const MIN_ZOOM = 0.7;
const MAX_ZOOM = 1.8;

export default function ProgressMap({
  pipeline = progressMapSample,
  className,
}: ProgressMapProps) {
  const t = useTranslations("ProgressMap");
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const [selectedNodeId, setSelectedNodeId] = useState(
    pipeline.nodes.find((node) => node.status === "running")?.id ||
      pipeline.nodes[0]?.id ||
      "",
  );
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(
    () => new Set(pipeline.nodes.map((node) => node.id)),
  );
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

  const selectedNode =
    pipeline.nodes.find((node) => node.id === selectedNodeId) ||
    pipeline.nodes[0];

  const nodeById = useMemo(
    () => new Map(pipeline.nodes.map((node) => [node.id, node])),
    [pipeline.nodes],
  );

  const visibleNodes = useMemo(() => {
    const visibilityCache = new Map<string, boolean>();

    const isNodeVisible = (node: ProgressMapNode): boolean => {
      const cached = visibilityCache.get(node.id);
      if (cached !== undefined) return cached;

      if (!node.parentIds?.length) {
        visibilityCache.set(node.id, true);
        return true;
      }

      const visible = node.parentIds.every((parentId) => {
        const parent = nodeById.get(parentId);
        if (!parent) return false;
        return isNodeVisible(parent) && expandedNodeIds.has(parentId);
      });

      visibilityCache.set(node.id, visible);
      return visible;
    };

    return pipeline.nodes.filter(isNodeVisible);
  }, [expandedNodeIds, nodeById, pipeline.nodes]);

  const visibleNodeIds = useMemo(
    () => new Set(visibleNodes.map((node) => node.id)),
    [visibleNodes],
  );

  const edges = useMemo(
    () =>
      pipeline.nodes.flatMap((node) =>
        (node.parentIds || [])
          .map((parentId) => {
            const parent = nodeById.get(parentId);
            if (!parent || !visibleNodeIds.has(parent.id) || !visibleNodeIds.has(node.id)) {
              return null;
            }

            return { from: parent, to: node };
          })
          .filter(Boolean),
      ) as Array<{ from: ProgressMapNode; to: ProgressMapNode }>,
    [nodeById, pipeline.nodes, visibleNodeIds],
  );

  const toggleNode = (node: ProgressMapNode) => {
    setSelectedNodeId(node.id);
    setExpandedNodeIds((current) => {
      const next = new Set(current);

      if (next.has(node.id)) {
        next.delete(node.id);
      } else {
        next.add(node.id);
      }

      return next;
    });
  };

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
        "overflow-hidden rounded-[22px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)]",
        isFullscreen && "flex h-full flex-col rounded-none border-0",
        className,
      )}
    >
      <div className="flex flex-col gap-3 border-b border-[var(--automl-data-card-border)] px-5 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-extrabold text-[var(--automl-data-text)]">
              {t("title")}
            </h2>
            <Info className="h-4 w-4 text-[var(--automl-data-muted)]" />
          </div>
          <p className="mt-0.5 text-xs font-semibold text-[var(--automl-data-muted)]">
            {t("predictionColumn", { column: pipeline.predictionColumn })}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="automl-data-chip">{t("rankBy", { metric: pipeline.rankBy })}</span>
          <span className="automl-data-chip automl-data-chip-secondary hidden sm:inline-flex">
            {t("scoreMode", { mode: pipeline.scoreMode })}
          </span>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-9 w-9 rounded-2xl border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] font-bold shadow-none"
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

      <div
        className={cn(
          "grid min-h-[430px] grid-cols-1 lg:grid-cols-[1fr_280px]",
          isFullscreen && "min-h-0 flex-1 lg:grid-cols-[1fr_340px]",
        )}
      >
        <div
          className={cn(
            "relative min-h-[430px] overflow-hidden overscroll-contain bg-slate-50/70 dark:bg-[#08111f]",
            dragStart ? "cursor-grabbing" : "cursor-grab",
          )}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onWheel={handleWheel}
        >
          <div
            className="absolute left-4 top-4 z-20 flex items-center gap-1.5 rounded-2xl border border-slate-200/90 bg-white/95 p-1 shadow-sm backdrop-blur dark:border-white/10 dark:bg-slate-900/90"
            onPointerDown={(event) => event.stopPropagation()}
          >
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 rounded-xl text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10"
              onClick={(event) => {
                event.stopPropagation();
                updateZoom(zoom - 0.1);
              }}
              title={t("zoomOut")}
            >
              <Minus className="h-4 w-4" />
            </Button>
            <span className="min-w-12 text-center text-xs font-black text-slate-700 dark:text-slate-200">
              {Math.round(zoom * 100)}%
            </span>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 rounded-xl text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10"
              onClick={(event) => {
                event.stopPropagation();
                updateZoom(zoom + 0.1);
              }}
              title={t("zoomIn")}
            >
              <Plus className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 rounded-xl text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10"
              onClick={(event) => {
                event.stopPropagation();
                resetViewport();
              }}
              title={t("resetView")}
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
          <div className="absolute bottom-4 left-4 z-20 inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/95 px-3.5 py-1.5 text-xs font-bold text-slate-600 shadow-sm backdrop-blur dark:border-white/10 dark:bg-slate-900/90 dark:text-slate-300">
            <Move className="h-3.5 w-3.5 text-automl-blue dark:text-cyan-400" />
            {t("panHint")}
          </div>
          <div
            className="relative h-[420px] w-[1120px] origin-top-left select-none transition-transform duration-100"
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
                  id="progress-map-grid"
                  width="36"
                  height="36"
                  patternUnits="userSpaceOnUse"
                >
                  <circle
                    cx="2"
                    cy="2"
                    r="1"
                    fill={isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.05)"}
                  />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#progress-map-grid)" />

              {edges.map(({ from, to }) => {
                const fromX = (from.x / 100) * MAP_WIDTH;
                const fromY = (from.y / 100) * MAP_HEIGHT;
                const toX = (to.x / 100) * MAP_WIDTH;
                const toY = (to.y / 100) * MAP_HEIGHT;
                const direction = toX >= fromX ? 1 : -1;
                const startX = fromX + NODE_RADIUS * direction;
                const endX = toX - NODE_RADIUS * direction;
                const hasCurve = Math.abs(fromY - toY) > 12;
                const bend = Math.min(82, Math.max(44, Math.abs(endX - startX) * 0.45));
                const path = hasCurve
                  ? `M ${startX} ${fromY} C ${startX + bend * direction} ${fromY}, ${endX - bend * direction} ${toY}, ${endX} ${toY}`
                  : `M ${startX} ${fromY} L ${endX} ${toY}`;
                const isPending = to.status === "pending";

                const outerStroke = isPending
                  ? isDark
                    ? "rgba(148, 163, 184, 0.12)"
                    : "#e2e8f0"
                  : isDark
                    ? "rgba(56, 189, 248, 0.25)"
                    : "#dbeafe";

                const innerStroke = isPending
                  ? isDark
                    ? "#475569"
                    : "#94a3b8"
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
                      strokeWidth="11"
                      vectorEffect="non-scaling-stroke"
                    />
                    <path
                      d={path}
                      fill="none"
                      stroke={innerStroke}
                      strokeDasharray={isPending ? "7 7" : undefined}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="3.5"
                      vectorEffect="non-scaling-stroke"
                    />
                  </g>
                );
              })}
            </svg>

            {visibleNodes.map((node) => {
              const expanded = expandedNodeIds.has(node.id);
              const selected = selectedNode?.id === node.id;

              return (
                <button
                  key={node.id}
                  type="button"
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleNode(node);
                  }}
                  className="group absolute z-10 flex w-36 -translate-x-1/2 cursor-pointer flex-col items-center text-center outline-none"
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                  title={`${node.label} - ${t(`status.${node.status}`)}`}
                >
                  <span
                    className={cn(
                      "relative z-20 flex h-6 w-6 items-center justify-center rounded-full transition-all duration-200",
                      "-translate-y-1/2",
                      statusClassName[node.status],
                      selected && "ring-4 ring-blue-300 dark:ring-cyan-300/60 scale-110",
                    )}
                  >
                    {node.status === "done" ? (
                      <Check className="h-3.5 w-3.5 stroke-[3] text-white" />
                    ) : node.status === "running" ? (
                      <Clock3 className="h-3.5 w-3.5 text-white animate-spin [animation-duration:3s]" />
                    ) : node.status === "failed" ? (
                      <XCircle className="h-3.5 w-3.5 text-white" />
                    ) : (
                      <span className="h-1.5 w-1.5 rounded-full bg-slate-400 dark:bg-slate-500" />
                    )}
                  </span>
                  <span
                    className={cn(
                      "relative z-10 mt-3 max-w-[140px] truncate rounded-lg px-2.5 py-1 text-xs font-extrabold leading-tight shadow-sm transition-all duration-150",
                      selected
                        ? "bg-blue-600 text-white shadow-md ring-2 ring-blue-400/40 dark:bg-cyan-500 dark:text-slate-950 dark:ring-cyan-300/50"
                        : "border border-slate-200/90 bg-white/95 text-slate-800 shadow-xs hover:border-slate-400 dark:border-slate-700/90 dark:bg-[#0c1626]/95 dark:text-slate-100 dark:shadow-md dark:hover:border-cyan-500/50",
                    )}
                  >
                    {node.label}
                  </span>
                  {node.subtitle && (
                    <span
                      className={cn(
                        "relative z-10 mt-1 max-w-[130px] truncate rounded-md px-2 py-0.5 text-[10px] font-black uppercase tracking-wider transition-all",
                        selected
                          ? "bg-blue-100 text-blue-700 dark:bg-cyan-950 dark:text-cyan-300"
                          : "border border-slate-200/60 bg-slate-100/95 text-slate-500 dark:border-cyan-900/50 dark:bg-slate-950/90 dark:text-cyan-400",
                      )}
                    >
                      {node.subtitle}
                    </span>
                  )}
                  {node.parentIds?.length && (
                    <span
                      className={cn(
                        "mt-1.5 h-1.5 w-1.5 rounded-full",
                        expanded ? "bg-blue-500 dark:bg-cyan-400" : "bg-slate-300 dark:bg-slate-600",
                      )}
                    />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <aside className="border-l border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-extrabold text-[var(--automl-data-text)]">
                {t("relationshipMap")}
              </h3>
              <button className="mt-1 text-xs font-bold text-automl-blue" type="button">
                {t("swapView")}
              </button>
            </div>
            <Expand className="h-4 w-4 text-[var(--automl-data-muted)]" />
          </div>

          <MiniRelationshipMap nodes={pipeline.nodes} selectedNodeId={selectedNode?.id} />

          {selectedNode && (
            <div className="mt-5 space-y-5 border-t border-[var(--automl-data-card-border)] pt-5">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.16em] text-automl-blue">
                  {selectedNode.label}
                </p>
                <p className="mt-2 font-extrabold text-[var(--automl-data-text)]">
                  {selectedNode.branch || selectedNode.subtitle || t("pipelineStage")}
                </p>
                <p className="mt-1 text-sm font-semibold text-[var(--automl-data-muted)]">
                  {t(`status.${selectedNode.status}`)}
                  {selectedNode.elapsed ? ` · ${selectedNode.elapsed}` : ""}
                </p>
              </div>

              <DetailBlock title={t("params")} data={selectedNode.params} />
              <DetailBlock title={t("result")} data={selectedNode.result} />

              {selectedNode.log?.length ? (
                <div>
                  <p className="text-sm font-extrabold text-[var(--automl-data-text)]">
                    {t("latestLog")}
                  </p>
                  <div className="mt-2 space-y-2">
                    {selectedNode.log.map((item) => (
                      <p
                        key={item}
                        className="rounded-xl border border-slate-200/60 bg-slate-50/70 px-3 py-2 font-mono text-xs font-semibold text-slate-700 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-300"
                      >
                        {item}
                      </p>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </aside>
      </div>
    </div>
  );

  return isFullscreen ? (
    <div className="fixed inset-0 z-50 bg-white dark:bg-[#08111f]">
      {mapContent}
    </div>
  ) : (
    mapContent
  );
}

const DetailBlock = ({
  title,
  data,
}: {
  title: string;
  data?: Record<string, string | number | boolean>;
}) => {
  const t = useTranslations("ProgressMap");

  return (
    <div>
      <p className="text-sm font-extrabold text-[var(--automl-data-text)]">{title}</p>
      {data && Object.keys(data).length > 0 ? (
        <div className="mt-2 space-y-2">
          {Object.entries(data).map(([key, value]) => (
            <div
              key={key}
              className="flex items-center justify-between gap-3 rounded-xl border border-slate-200/60 bg-slate-50/70 px-3.5 py-2 text-xs dark:border-white/10 dark:bg-slate-900/80"
            >
              <span className="font-bold text-slate-500 dark:text-slate-400">{key}</span>
              <span className="text-right font-black text-slate-900 dark:text-cyan-300">
                {String(value)}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm font-semibold text-[var(--automl-data-muted)]">
          {t("emptyData")}
        </p>
      )}
    </div>
  );
};

const MiniRelationshipMap = ({
  nodes,
  selectedNodeId,
}: {
  nodes: ProgressMapNode[];
  selectedNodeId?: string;
}) => (
  <div className="mt-5 flex h-28 items-center justify-center">
    <div className="relative h-24 w-44">
      {nodes.slice(0, 28).map((node, index) => {
        const angle = Math.PI + (index / Math.max(nodes.length - 1, 1)) * Math.PI;
        const radius = node.id === selectedNodeId ? 58 : 72;
        const x = 88 + Math.cos(angle) * radius;
        const y = 78 + Math.sin(angle) * radius;

        return (
          <span
            key={node.id}
            className={cn(
              "absolute h-2.5 w-2.5 rounded-full border transition-all",
              node.status === "done" && "border-blue-400 bg-blue-600 dark:border-cyan-300 dark:bg-blue-500",
              node.status === "running" && "border-white bg-cyan-400 shadow-sm shadow-cyan-400 animate-pulse",
              node.status === "pending" && "border-slate-300 bg-slate-200 dark:border-slate-700 dark:bg-slate-800",
              node.status === "failed" && "border-red-300 bg-red-500",
              node.id === selectedNodeId && "h-3.5 w-3.5 ring-4 ring-blue-200 dark:ring-cyan-400/50 shadow-md",
            )}
            style={{ left: x, top: y }}
          />
        );
      })}
      <div className="absolute bottom-0 left-1/2 h-14 w-24 -translate-x-1/2 rounded-t-full border-4 border-slate-300 dark:border-slate-700/60 border-b-0" />
    </div>
  </div>
);
