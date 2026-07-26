"use client";

import { useEffect, useRef } from "react";
import { BrainCircuit, Database, Rocket, SlidersHorizontal } from "lucide-react";

const nodes = [
  {
    id: "dataset",
    label: "Dữ liệu",
    caption: "12.4k dòng",
    icon: Database,
    className: "left-[8%] top-[41%]",
    tone: "bg-automl-cyan-soft text-cyan-700 dark:text-cyan-200",
  },
  {
    id: "config",
    label: "Cấu hình",
    caption: "target, metric",
    icon: SlidersHorizontal,
    className: "left-[31%] top-[26%]",
    tone: "bg-automl-orange-soft text-orange-700 dark:text-orange-200",
  },
  {
    id: "train",
    label: "Auto train",
    caption: "8 thuật toán",
    icon: BrainCircuit,
    className: "right-[30%] top-[49%]",
    tone: "bg-automl-blue-soft text-blue-700 dark:text-blue-200",
  },
  {
    id: "deploy",
    label: "Triển khai",
    caption: "API ready",
    icon: Rocket,
    className: "right-[7%] top-[33%]",
    tone: "bg-automl-green-soft text-emerald-700 dark:text-emerald-200",
  },
];

const lines = [
  "left-[20%] top-[48%] w-[14%] rotate-[-17deg]",
  "left-[43%] top-[40%] w-[21%] rotate-[13deg]",
  "right-[20%] top-[45%] w-[13%] rotate-[-15deg]",
];

export default function HAutoMLHeroScene() {
  const rootRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const coreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    const stage = stageRef.current;
    const core = coreRef.current;

    if (!root || !stage || !core) return;

    let frameId = 0;
    const target = { x: 0, y: 0, scroll: 0 };
    const current = { x: 0, y: 0, scroll: 0 };
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    const updateScroll = () => {
      const rect = root.getBoundingClientRect();
      const distance = window.innerHeight + rect.height;
      target.scroll = Math.min(1, Math.max(0, (window.innerHeight - rect.top) / distance));
    };

    const updatePointer = (event: PointerEvent) => {
      const rect = root.getBoundingClientRect();
      target.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      target.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
    };

    const animate = () => {
      current.x += (target.x - current.x) * 0.08;
      current.y += (target.y - current.y) * 0.08;
      current.scroll += (target.scroll - current.scroll) * 0.07;

      const scrollPower = reduceMotion.matches ? current.scroll * 0.2 : current.scroll;
      const rotateY = current.x * 10 + scrollPower * 18;
      const rotateX = current.y * -6 + scrollPower * 5;
      const lift = -scrollPower * 26;

      stage.style.transform = `translate3d(${current.x * 10}px, ${lift + current.y * -5}px, 0) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
      core.style.transform = `translate3d(${current.x * 14}px, ${current.y * -12}px, 46px) rotateX(${rotateX * 0.8}deg) rotateY(${rotateY * 1.2}deg)`;

      frameId = window.requestAnimationFrame(animate);
    };

    updateScroll();
    window.addEventListener("scroll", updateScroll, { passive: true });
    root.addEventListener("pointermove", updatePointer, { passive: true });
    frameId = window.requestAnimationFrame(animate);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("scroll", updateScroll);
      root.removeEventListener("pointermove", updatePointer);
    };
  }, []);

  return (
    <div
      ref={rootRef}
      className="relative h-[520px] overflow-hidden rounded-lg border border-automl-line bg-automl-surface shadow-[0_28px_80px_rgba(15,23,42,0.16)] dark:shadow-none"
    >
      <div className="flex h-12 items-center justify-between border-b border-automl-line bg-automl-surface-muted px-4">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
        </div>
        <p className="text-xs font-bold text-automl-muted">experiment: churn-classifier</p>
      </div>

      <div className="absolute inset-x-0 top-12 h-px bg-automl-line" />
      <div className="absolute inset-0 top-12 bg-[linear-gradient(to_right,hsl(var(--automl-line)/0.35)_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--automl-line)/0.35)_1px,transparent_1px)] bg-[size:44px_44px]" />

      <div className="absolute inset-x-6 bottom-6 z-20 grid gap-3 rounded-lg border border-automl-line bg-automl-surface/92 p-4 backdrop-blur md:grid-cols-3">
        {[
          ["Best model", "XGBoost"],
          ["ROC AUC", "0.793"],
          ["Build time", "02:30"],
        ].map(([label, value]) => (
          <div key={label}>
            <p className="text-xs font-bold text-automl-muted">{label}</p>
            <p className="mt-1 text-lg font-black text-automl-ink">{value}</p>
          </div>
        ))}
      </div>

      <div className="absolute inset-0 top-12 [perspective:1100px]">
        <div
          ref={stageRef}
          className="absolute inset-8 transition-transform duration-75 [transform-style:preserve-3d]"
        >
          {lines.map((line) => (
            <span
              key={line}
              className={`absolute h-1 rounded-full bg-automl-blue shadow-[0_0_0_7px_hsl(var(--automl-blue-soft)/0.7)] ${line}`}
            />
          ))}

          {nodes.map((node) => {
            const Icon = node.icon;

            return (
              <div
                key={node.id}
                className={`absolute z-10 w-36 rounded-lg border border-automl-line bg-automl-surface p-3 shadow-lg shadow-slate-950/10 dark:shadow-none ${node.className}`}
              >
                <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${node.tone}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <p className="mt-3 text-sm font-black text-automl-ink">{node.label}</p>
                <p className="mt-1 text-xs font-semibold text-automl-muted">{node.caption}</p>
              </div>
            );
          })}

          <div
            ref={coreRef}
            className="absolute left-1/2 top-1/2 z-20 h-28 w-28 -translate-x-1/2 -translate-y-1/2 rounded-lg border border-automl-blue/60 bg-automl-blue text-white shadow-[0_24px_60px_rgba(37,99,255,0.35)] [transform-style:preserve-3d]"
          >
            <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
              <BrainCircuit className="h-8 w-8" />
              <p className="text-sm font-black">HAutoML</p>
              <p className="text-[11px] font-bold text-white/75">Core</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
