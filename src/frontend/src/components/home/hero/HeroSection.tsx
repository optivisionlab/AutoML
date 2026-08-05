"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";

import HeroBackground from "./HeroBackground";
import HeroContent from "./HeroContent";
import ModelMetrics from "./ModelMetrics";

const AIModelScene = dynamic(() => import("./AIModelScene"), {
  ssr: false,
  loading: () => (
    <div className="automl-ai-scene-fallback" aria-label="Loading AI model visualization" />
  ),
});

export type HeroPointer = {
  x: number;
  y: number;
};

const idlePointer: HeroPointer = { x: 0, y: 0 };

export default function HeroSection() {
  const [pointer, setPointer] = useState<HeroPointer>(idlePointer);

  const handlePointerMove = useCallback((event: React.PointerEvent<HTMLElement>) => {
    if (event.pointerType === "touch") return;

    const rect = event.currentTarget.getBoundingClientRect();
    setPointer({
      x: ((event.clientX - rect.left) / rect.width) * 2 - 1,
      y: -(((event.clientY - rect.top) / rect.height) * 2 - 1),
    });
  }, []);

  return (
    <section
      id="home"
      className="automl-ai-hero"
      onPointerMove={handlePointerMove}
      onPointerLeave={() => setPointer(idlePointer)}
    >
      <HeroBackground pointer={pointer} />

      <div className="automl-ai-hero-inner">
        <HeroContent />

        <div className="automl-ai-visual-wrap">
          <AIModelScene pointer={pointer} />
          <ModelMetrics pointer={pointer} />
        </div>
      </div>
    </section>
  );
}
