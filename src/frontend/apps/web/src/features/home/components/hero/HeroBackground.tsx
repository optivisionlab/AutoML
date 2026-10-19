"use client";

import type { CSSProperties } from "react";

import type { HeroPointer } from "./HeroSection";

type HeroBackgroundProps = {
  pointer: HeroPointer;
};

export default function HeroBackground({ pointer }: HeroBackgroundProps) {
  return (
    <div
      className="automl-ai-hero-bg"
      style={
        {
          "--hero-pointer-x": pointer.x,
          "--hero-pointer-y": pointer.y,
        } as CSSProperties
      }
      aria-hidden="true"
    >
      <span className="automl-ai-bg-glow primary" />
      <span className="automl-ai-bg-glow secondary" />
      <span className="automl-ai-bg-grid" />
      <span className="automl-ai-bg-stars" />
    </div>
  );
}
