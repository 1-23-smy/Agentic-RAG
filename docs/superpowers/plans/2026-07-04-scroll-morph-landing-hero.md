# Scroll-Morph Landing Hero Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scroll-driven "corpus assembly" landing hero at `/`, moving the existing chat app to `/app`, faithful to the Claude Design System's `scroll-morph-hero` concept but driven by real page scroll instead of the source's wheel/touch-hijacking virtual scroll.

**Architecture:** A new client component (`ScrollMorphHero`) renders 20 illustrative document/source cards that fly in via a fixed intro sequence (scatter → line → ring), then respond to real scroll position (via a tall wrapping `<section>` + `position: sticky` pinned stage) to morph the ring into a bottom arc and shuffle it further. All per-frame positioning is done imperatively (direct DOM writes via refs in a `requestAnimationFrame` loop), bypassing React re-renders, exactly matching the source design's performance approach for animating 20 elements at 60fps. The hero's CSS is a verbatim port of the design's dark-neon-glass values, kept deliberately separate from the site's shared design-token system.

**Tech Stack:** Next.js 16 (App Router), TypeScript, React 19, plain (non-module) global CSS import, `next/link` for navigation. No new dependencies.

## Global Constraints

- No backend/network calls anywhere in the new landing page — the corpus grid uses a static illustrative dataset only.
- The hero ignores the site's light/dark theme toggle entirely — it is always the dark neon-glass skin, by design.
- CSS visual values (colors, gradients, blur, keyframes, font sizes) are copied verbatim from the source design — no invented values, no conversion to the shared `--surface-*`/`--accent` design tokens.
- Real page scroll drives the animation — no `preventDefault()` on wheel/touch events, no `touch-action: none`.
- The existing chat app (`ChatApp` and everything it depends on) must be moved to `/app` with zero internal changes — this plan only relocates its page-level entry point.
- No automated frontend tests are added — matches the existing project convention. Verification is manual (`pnpm dev` + `tsc --noEmit`).
- `prefers-reduced-motion: reduce` must disable eased interpolation (cards snap directly to goal position/opacity) and the two decorative CSS keyframe loops (blink dot, scroll-hint wheel).

---

### Task 1: Move the chat app to `/app`

**Files:**
- Create: `frontend/app/app/page.tsx`
- Modify: `frontend/app/page.tsx` (temporarily left as-is here; Task 5 replaces its content with the new hero — this task only adds the new route so both exist briefly, avoiding a broken intermediate state)

**Interfaces:**
- Produces: the route `/app` renders `<ChatApp />` (imported from `@/components/chat-app`, unchanged).

- [ ] **Step 1: Create the new `/app` route**

```tsx
// frontend/app/app/page.tsx
import { ChatApp } from "@/components/chat-app";

export default function AppPage() {
  return <ChatApp />;
}
```

- [ ] **Step 2: Verify the new route serves the chat app**

```bash
cd frontend && (pnpm dev > /tmp/task1dev.log 2>&1 &)
sleep 5
curl -sf -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000/app
pkill -f "next dev" ; pkill -f "next-server"
```

Expected: `HTTP 200`.

- [ ] **Step 3: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/app/page.tsx
git commit -m "feat: add /app route serving the existing chat app"
```

---

### Task 2: Corpus data module

**Files:**
- Create: `frontend/components/landing/corpus-data.ts`

**Interfaces:**
- Produces: `CorpusDoc` interface and `buildCorpusDocs(): CorpusDoc[]`, consumed by Task 4 (`corpus-card.tsx`) and Task 5 (`scroll-morph-hero.tsx`).

- [ ] **Step 1: Write the data module**

```typescript
// frontend/components/landing/corpus-data.ts
export type CorpusMode = "vector" | "graph";

export interface CorpusDoc {
  id: string;
  title: string;
  mode: CorpusMode;
  score: string;
  fact: [string, string, string] | null;
  snippet: string | null;
}

const TITLES = [
  "Clinical Trial",
  "Safety Review",
  "Pharmacovigilance",
  "Dosing Guide",
  "Mechanism",
  "Case Series",
  "Meta-Analysis",
  "Label Extract",
  "Protocol",
  "Registry",
];

const GRAPH_FACTS: [string, string, string][] = [
  ["Warfarin", "INTERACTS_WITH", "Amiodarone"],
  ["Rifampin", "INDUCES", "CYP2C9"],
  ["NSAID", "INCREASES", "Bleed risk"],
  ["Aspirin", "INHIBITS", "COX-1"],
];

const VECTOR_SNIPPETS = [
  "reduce dose 30–50%",
  "monitor INR closely",
  "potentiates effect",
  "displaces from plasma",
];

export const TOTAL_CORPUS_DOCS = 20;

export function buildCorpusDocs(): CorpusDoc[] {
  return Array.from({ length: TOTAL_CORPUS_DOCS }, (_, i) => {
    const mode: CorpusMode = i % 3 === 0 ? "graph" : "vector";
    return {
      id: "DOC-" + String(i + 1).padStart(2, "0"),
      title: TITLES[i % TITLES.length],
      mode,
      score: (0.72 + ((i * 7) % 27) / 100).toFixed(2),
      fact: mode === "graph" ? GRAPH_FACTS[i % GRAPH_FACTS.length] : null,
      snippet: mode === "vector" ? VECTOR_SNIPPETS[i % VECTOR_SNIPPETS.length] : null,
    };
  });
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/landing/corpus-data.ts
git commit -m "feat: add illustrative corpus data module for scroll-morph hero"
```

---

### Task 3: Ported stylesheet

**Files:**
- Create: `frontend/components/landing/scroll-morph-hero.css`

**Interfaces:**
- Produces: global CSS classes (`smh-*` prefixed) consumed by Task 4 (`corpus-card.tsx`) and Task 5 (`scroll-morph-hero.tsx`) via plain `import "./scroll-morph-hero.css"`.

- [ ] **Step 1: Write the stylesheet**

This is a verbatim port of the source design's `<style>` block (from `scroll-morph-hero.html`), with two structural edits explained inline: `touch-action: none` removed, and `.smh-root` changed from a fixed full-viewport root to a `position: sticky` child (the tall `300vh` wrapping section is set inline in the TSX component, not here, since it's a layout concern specific to how this component is embedded on the page).

```css
/* frontend/components/landing/scroll-morph-hero.css */
/* Ported verbatim from the Claude Design System's scroll-morph-hero concept
   (ui_kits/agentic-rag-futuristic/scroll-morph-hero.html), with two
   structural edits: touch-action:none removed (real page scroll needs
   native touch scrolling), and .smh-root restructured from a fixed
   full-viewport root into a `position:sticky` child of a tall wrapping
   section (see scroll-morph-hero.tsx) instead of filling a 100vh parent. */

.smh-root {
  position: sticky;
  top: 0;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(900px 620px at 80% 6%, rgba(139, 92, 246, 0.16), transparent 60%),
    radial-gradient(1000px 720px at 10% 96%, rgba(18, 181, 166, 0.14), transparent 60%),
    linear-gradient(180deg, #070a14, #04060d);
  color: #e7ecf6;
  font-family: var(--font-sans);
  perspective: 1400px;
}
.smh-root::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.5;
  background-image: linear-gradient(rgba(120, 140, 190, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(120, 140, 190, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(circle at 50% 50%, #000 40%, transparent 78%);
}

.smh-eyebrow {
  font: var(--fw-semibold) 10px/1 var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.28em;
  color: #6e7ca0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.smh-eyebrow--live i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #12b5a6;
  box-shadow: 0 0 10px #12b5a6;
  animation: smh-blink 1.4s infinite;
}

.smh-intro {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 16px;
  pointer-events: none;
}
.smh-intro-h {
  font: var(--fw-extra) 60px/1.0 var(--font-display);
  letter-spacing: -0.04em;
  margin: 0;
  background: linear-gradient(180deg, #fff, #9fafdc);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.smh-scrollhint {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  font: var(--fw-bold) 10px/1 var(--font-mono);
  letter-spacing: 0.3em;
  color: #7b88ac;
}
.smh-arrow {
  width: 15px;
  height: 22px;
  border: 1.5px solid #5f6c90;
  border-radius: 8px;
  position: relative;
}
.smh-arrow::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 4px;
  width: 2px;
  height: 5px;
  background: #7fa0ff;
  border-radius: 2px;
  transform: translateX(-50%);
  animation: smh-wheel 1.5s infinite;
}

.smh-arc-content {
  position: absolute;
  top: 8%;
  left: 0;
  right: 0;
  z-index: 6;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 14px;
  padding: 0 24px;
  pointer-events: none;
}
.smh-arc-h {
  font: var(--fw-extra) 52px/1.02 var(--font-display);
  letter-spacing: -0.04em;
  margin: 6px 0 0;
  background: linear-gradient(180deg, #fff, #a9b6de);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.smh-arc-p {
  font: var(--fw-regular) 15px/1.6 var(--font-sans);
  color: #93a0c4;
  max-width: 500px;
  margin: 0;
}
.smh-cta {
  pointer-events: auto;
  margin-top: 6px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  border-radius: 999px;
  padding: 12px 22px;
  cursor: pointer;
  color: #fff;
  font: var(--fw-semibold) 14px/1 var(--font-sans);
  background: linear-gradient(180deg, #2f6bff, #143fcc);
  box-shadow: 0 8px 28px rgba(47, 107, 255, 0.5);
  transition: 0.2s;
  text-decoration: none;
}
.smh-cta span {
  font-family: var(--font-mono);
  font-size: 16px;
}
.smh-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 34px rgba(47, 107, 255, 0.7);
}

.smh-stage {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
}
.smh-card {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 66px;
  height: 90px;
  transform-style: preserve-3d;
  will-change: transform, opacity;
}
.smh-flip {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform 0.6s cubic-bezier(0.2, 0, 0, 1);
}
.smh-card:hover .smh-flip {
  transform: rotateY(180deg);
}
.smh-face {
  position: absolute;
  inset: 0;
  border-radius: 9px;
  overflow: hidden;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
}

.smh-front {
  background: linear-gradient(160deg, #fdfdff, #eef1f8);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.45);
  padding: 9px 8px;
  display: flex;
  flex-direction: column;
}
.smh-tab {
  position: absolute;
  top: 0;
  right: 0;
  width: 22px;
  height: 5px;
  border-radius: 0 9px 0 6px;
}
.smh-front--vector .smh-tab {
  background: #12b5a6;
  box-shadow: -6px 0 10px rgba(18, 181, 166, 0.5);
}
.smh-front--graph .smh-tab {
  background: #8b5cf6;
  box-shadow: -6px 0 10px rgba(139, 92, 246, 0.5);
}
.smh-docid {
  font: var(--fw-semibold) 6px/1 var(--font-mono);
  letter-spacing: 0.1em;
  color: #8a93a8;
}
.smh-title {
  font: var(--fw-bold) 7.5px/1.1 var(--font-sans);
  color: #1b2333;
  margin-top: 3px;
  letter-spacing: -0.01em;
}
.smh-lines {
  margin-top: 7px;
  display: flex;
  flex-direction: column;
  gap: 3.5px;
}
.smh-lines i {
  height: 2.5px;
  border-radius: 2px;
  background: #c9d0de;
}

.smh-back {
  transform: rotateY(180deg);
  opacity: 0;
  transition: opacity 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  background: linear-gradient(180deg, rgba(22, 28, 45, 0.96), rgba(12, 16, 28, 0.96));
}
.smh-card:hover .smh-back {
  opacity: 1;
}
.smh-back--vector {
  border: 1px solid rgba(18, 181, 166, 0.5);
  box-shadow: inset 0 0 20px rgba(18, 181, 166, 0.18);
}
.smh-back--graph {
  border: 1px solid rgba(139, 92, 246, 0.5);
  box-shadow: inset 0 0 20px rgba(139, 92, 246, 0.18);
}
.smh-chunk {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 5px;
  align-items: center;
}
.smh-score {
  font: var(--fw-bold) 13px/1 var(--font-mono);
  color: #3fe0ce;
  text-shadow: 0 0 10px rgba(18, 181, 166, 0.6);
}
.smh-snip {
  font: var(--fw-regular) 6.5px/1.35 var(--font-sans);
  color: #aeb8d6;
}
.smh-graph {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.smh-node {
  font: var(--fw-semibold) 7px/1 var(--font-mono);
  color: #c9bef6;
  background: rgba(139, 92, 246, 0.18);
  border: 1px solid rgba(139, 92, 246, 0.5);
  border-radius: 4px;
  padding: 2px 5px;
}
.smh-rel {
  font: var(--fw-medium) 5px/1 var(--font-mono);
  color: #7e70b8;
  letter-spacing: 0.05em;
}

.smh-rail {
  position: absolute;
  right: 18px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 120px;
  background: rgba(140, 160, 220, 0.12);
  border-radius: 3px;
  z-index: 7;
  overflow: hidden;
}
.smh-rail-fill {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 0%;
  background: linear-gradient(180deg, #12b5a6, #2f6bff, #8b5cf6);
  box-shadow: 0 0 10px rgba(47, 107, 255, 0.6);
}

@keyframes smh-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}
@keyframes smh-wheel {
  0% {
    top: 4px;
    opacity: 1;
  }
  70% {
    top: 12px;
    opacity: 0;
  }
  100% {
    top: 4px;
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .smh-arrow::after,
  .smh-eyebrow--live i {
    animation: none;
  }
}
```

- [ ] **Step 2: Verify the CSS file has no syntax errors**

```bash
cd frontend && (pnpm dev > /tmp/task3dev.log 2>&1 &)
sleep 5
curl -sf -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000
pkill -f "next dev" ; pkill -f "next-server"
grep -i "error" /tmp/task3dev.log || echo "no errors in log"
```

Note: this file isn't imported by anything yet (Task 4/5 import it), so this step only confirms the dev server itself still boots — the file's syntax is fully verified once Task 5 imports it and the page renders correctly.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/landing/scroll-morph-hero.css
git commit -m "feat: port scroll-morph hero stylesheet from design system"
```

---

### Task 4: Corpus card component

**Files:**
- Create: `frontend/components/landing/corpus-card.tsx`

**Interfaces:**
- Consumes: `CorpusDoc` type from `frontend/components/landing/corpus-data.ts` (Task 2), `.smh-*` CSS classes from `frontend/components/landing/scroll-morph-hero.css` (Task 3).
- Produces: `CorpusCard`, a `forwardRef<HTMLDivElement, CorpusCardProps>` component with `doc: CorpusDoc` prop, consumed by Task 5 (`scroll-morph-hero.tsx`) which attaches it to `cardRefs.current[i]` and writes `style.transform`/`style.opacity` on it directly every animation frame.

- [ ] **Step 1: Write the component**

```tsx
// frontend/components/landing/corpus-card.tsx
import * as React from "react";
import type { CorpusDoc } from "./corpus-data";

export interface CorpusCardProps {
  doc: CorpusDoc;
}

export const CorpusCard = React.forwardRef<HTMLDivElement, CorpusCardProps>(
  ({ doc }, ref) => {
    return (
      <div ref={ref} className="smh-card">
        <div className="smh-flip">
          <div className={`smh-face smh-front smh-front--${doc.mode}`}>
            <span className="smh-tab" />
            <span className="smh-docid">{doc.id}</span>
            <span className="smh-title">{doc.title}</span>
            <span className="smh-lines">
              {[92, 78, 88, 64, 82, 50].map((w, k) => (
                <i key={k} style={{ width: `${w}%` }} />
              ))}
            </span>
          </div>
          <div className={`smh-face smh-back smh-back--${doc.mode}`}>
            {doc.mode === "graph" && doc.fact ? (
              <div className="smh-graph">
                <span className="smh-node">{doc.fact[0]}</span>
                <span className="smh-rel">{doc.fact[1]}</span>
                <span className="smh-node">{doc.fact[2]}</span>
              </div>
            ) : (
              <div className="smh-chunk">
                <span className="smh-score">{doc.score}</span>
                <span className="smh-snip">&ldquo;&hellip;{doc.snippet}&hellip;&rdquo;</span>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
);
CorpusCard.displayName = "CorpusCard";
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/landing/corpus-card.tsx
git commit -m "feat: add CorpusCard flip-card component for scroll-morph hero"
```

---

### Task 5: ScrollMorphHero orchestrator

**Files:**
- Create: `frontend/components/landing/scroll-morph-hero.tsx`

**Interfaces:**
- Consumes: `buildCorpusDocs`, `TOTAL_CORPUS_DOCS`, `CorpusDoc` from `./corpus-data` (Task 2); `CorpusCard` from `./corpus-card` (Task 4); `./scroll-morph-hero.css` (Task 3).
- Produces: `ScrollMorphHero`, a default-exportable client component, consumed by Task 6 (`frontend/app/page.tsx`).

This is the most involved task — it ports the source design's `ScrollMorphHero.jsx` animation logic (scatter/line/ring/arc math, rAF easing loop, mouse parallax) while replacing the scroll input source (real page scroll instead of wheel/touch hijack) and adding `prefers-reduced-motion` handling.

- [ ] **Step 1: Write the component**

```tsx
// frontend/components/landing/scroll-morph-hero.tsx
"use client";

import * as React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { CorpusCard } from "./corpus-card";
import { buildCorpusDocs, TOTAL_CORPUS_DOCS } from "./corpus-data";
import "./scroll-morph-hero.css";

const SCROLL_SECTION_VH = 300; // scroll distance, in viewport-heights, driving the full animation
const MORPH_BREAKPOINT = 0.2; // ring→arc morph completes at this fraction of scroll progress (matches source's 600/3000)

const lerp = (a: number, b: number, t: number) => a * (1 - t) + b * t;
const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

type Phase = "scatter" | "line" | "ring";

interface CardTransform {
  x: number;
  y: number;
  rot: number;
  scale: number;
  op: number;
}

export function ScrollMorphHero() {
  const sectionRef = useRef<HTMLElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);
  const introTextRef = useRef<HTMLDivElement | null>(null);
  const arcContentRef = useRef<HTMLDivElement | null>(null);
  const railFillRef = useRef<HTMLSpanElement | null>(null);
  const [phase, setPhase] = useState<Phase>("scatter");

  const docs = useMemo(() => buildCorpusDocs(), []);

  const anim = useRef({ progress: 0, morph: 0, rotate: 0, parallax: 0, mSmooth: 0, rSmooth: 0, pSmooth: 0 });
  const size = useRef({ w: 0, h: 0 });
  const phaseRef = useRef<Phase>("scatter");
  phaseRef.current = phase;
  const reducedMotionRef = useRef(false);

  const scatter = useMemo<CardTransform[]>(
    () =>
      docs.map(() => ({
        x: (Math.random() - 0.5) * 1500,
        y: (Math.random() - 0.5) * 900,
        rot: (Math.random() - 0.5) * 180,
        scale: 0.6,
        op: 0,
      })),
    [docs]
  );
  const cur = useRef<CardTransform[]>(scatter.map((s) => ({ ...s })));

  // reduced-motion preference
  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    reducedMotionRef.current = mql.matches;
    const onChange = (e: MediaQueryListEvent) => {
      reducedMotionRef.current = e.matches;
    };
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  // container size
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const set = () => {
      size.current = { w: el.offsetWidth, h: el.offsetHeight };
    };
    set();
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // real-scroll progress (0–1 across the tall wrapping section) + mouse parallax
  useEffect(() => {
    let ticking = false;

    const computeProgress = () => {
      const section = sectionRef.current;
      if (!section) return;
      const rect = section.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      anim.current.progress = total > 0 ? clamp(-rect.top / total, 0, 1) : 0;
      ticking = false;
    };

    const onScroll = () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(computeProgress);
      }
    };

    const onMove = (e: MouseEvent) => {
      const el = containerRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      anim.current.parallax = (((e.clientX - r.left) / r.width) * 2 - 1) * 60;
    };

    computeProgress();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    window.addEventListener("mousemove", onMove);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      window.removeEventListener("mousemove", onMove);
    };
  }, []);

  // intro sequence
  useEffect(() => {
    const t1 = setTimeout(() => setPhase("line"), 500);
    const t2 = setTimeout(() => setPhase("ring"), 2400);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []);

  // rAF loop — compute goals, ease (or snap under reduced motion), paint via refs
  useEffect(() => {
    let raf: number;
    const tick = () => {
      const a = anim.current;
      a.morph = clamp(a.progress / MORPH_BREAKPOINT, 0, 1);
      a.rotate = clamp((a.progress - MORPH_BREAKPOINT) / (1 - MORPH_BREAKPOINT), 0, 1);

      const easeFactor = reducedMotionRef.current ? 1 : 0.09;
      a.mSmooth = lerp(a.mSmooth, a.morph, easeFactor);
      a.rSmooth = lerp(a.rSmooth, a.rotate, easeFactor);
      a.pSmooth = lerp(a.pSmooth, a.parallax, reducedMotionRef.current ? 1 : 0.08);

      const { w, h } = size.current;
      const isMobile = w < 768;
      const minDim = Math.min(w, h);
      const p = phaseRef.current;
      const m = a.mSmooth;

      for (let i = 0; i < TOTAL_CORPUS_DOCS; i++) {
        let goal: CardTransform;
        if (p === "scatter") {
          goal = scatter[i];
        } else if (p === "line") {
          const sp = 74;
          const lineX = i * sp - (TOTAL_CORPUS_DOCS * sp) / 2;
          goal = { x: lineX, y: 0, rot: 0, scale: 1, op: 1 };
        } else {
          const rad = Math.min(minDim * 0.35, 340);
          const ang = (i / TOTAL_CORPUS_DOCS) * 360;
          const rr = (ang * Math.PI) / 180;
          const ring = { x: Math.cos(rr) * rad, y: Math.sin(rr) * rad, rot: ang + 90 };

          const baseR = Math.min(w, h * 1.5);
          const arcR = baseR * (isMobile ? 1.4 : 1.05);
          const apexY = h * (isMobile ? 0.34 : 0.22);
          const centerY = apexY + arcR;
          const spread = isMobile ? 104 : 132;
          const start = -90 - spread / 2;
          const step = spread / (TOTAL_CORPUS_DOCS - 1);
          const bounded = -clamp(a.rSmooth, 0, 1) * (spread * 0.8);
          const ca = start + i * step + bounded;
          const car = (ca * Math.PI) / 180;
          const arc = {
            x: Math.cos(car) * arcR + a.pSmooth,
            y: Math.sin(car) * arcR + centerY,
            rot: ca + 90,
            scale: isMobile ? 1.35 : 1.7,
          };
          goal = {
            x: lerp(ring.x, arc.x, m),
            y: lerp(ring.y, arc.y, m),
            rot: lerp(ring.rot, arc.rot, m),
            scale: lerp(1, arc.scale, m),
            op: 1,
          };
        }
        const c = cur.current[i];
        c.x = lerp(c.x, goal.x, easeFactor);
        c.y = lerp(c.y, goal.y, easeFactor);
        c.rot = lerp(c.rot, goal.rot, easeFactor);
        c.scale = lerp(c.scale, goal.scale, easeFactor);
        c.op = lerp(c.op, goal.op, reducedMotionRef.current ? 1 : 0.1);
        const el = cardRefs.current[i];
        if (el) {
          el.style.transform = `translate(-50%,-50%) translate(${c.x}px,${c.y}px) rotate(${c.rot}deg) scale(${c.scale})`;
          el.style.opacity = String(c.op);
          el.style.zIndex = String(1000 + Math.round(c.y));
        }
      }

      if (introTextRef.current) {
        const o = clamp(1 - m * 1.7, 0, 1);
        introTextRef.current.style.opacity = String(o);
      }
      if (arcContentRef.current) {
        const o = clamp((m - 0.78) / 0.22, 0, 1);
        arcContentRef.current.style.opacity = String(o);
        arcContentRef.current.style.transform = `translateY(${lerp(24, 0, o)}px)`;
      }
      if (railFillRef.current) {
        railFillRef.current.style.height = a.progress * 100 + "%";
      }

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [scatter]);

  return (
    <section ref={sectionRef} style={{ height: `${SCROLL_SECTION_VH}vh` }}>
      <div ref={containerRef} className="smh-root">
        <div ref={introTextRef} className="smh-intro" style={{ opacity: 0 }}>
          <div className="smh-eyebrow">Universal Agentic RAG</div>
          <h1 className="smh-intro-h">
            Every page.
            <br />
            One mind.
          </h1>
          <p className="smh-scrollhint">
            <span className="smh-arrow" />
            SCROLL TO ASSEMBLE THE CORPUS
          </p>
        </div>

        <div ref={arcContentRef} className="smh-arc-content" style={{ opacity: 0 }}>
          <div className="smh-eyebrow smh-eyebrow--live">
            <i />
            CORPUS ASSEMBLED · {TOTAL_CORPUS_DOCS} DOCUMENTS
          </div>
          <h2 className="smh-arc-h">Interrogate the corpus.</h2>
          <p className="smh-arc-p">
            Twenty sources, one agent. Every answer is routed across vector space and the
            knowledge graph — and grounded, to the page.
          </p>
          <Link href="/app" className="smh-cta">
            Ask a question<span>›</span>
          </Link>
        </div>

        <div className="smh-stage">
          {docs.map((doc, i) => (
            <CorpusCard key={doc.id} doc={doc} ref={(el) => (cardRefs.current[i] = el)} />
          ))}
        </div>

        <div className="smh-rail">
          <span ref={railFillRef} className="smh-rail-fill" />
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/landing/scroll-morph-hero.tsx
git commit -m "feat: add ScrollMorphHero orchestrator driven by real page scroll"
```

---

### Task 6: Wire the hero into the landing route and verify end-to-end

**Files:**
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: `ScrollMorphHero` from `@/components/landing/scroll-morph-hero` (Task 5).

- [ ] **Step 1: Replace the root page**

```tsx
// frontend/app/page.tsx
import { ScrollMorphHero } from "@/components/landing/scroll-morph-hero";

export default function Home() {
  return <ScrollMorphHero />;
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Manual end-to-end verification**

```bash
cd frontend && (pnpm dev > /tmp/task6dev.log 2>&1 &)
sleep 5
curl -sf -o /tmp/task6-root.html -w "HTTP %{http_code}\n" http://localhost:3000
grep -o "SCROLL TO ASSEMBLE THE CORPUS" /tmp/task6-root.html
curl -sf -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000/app
tail -30 /tmp/task6dev.log
pkill -f "next dev" ; pkill -f "next-server"
```

Expected: both routes return `HTTP 200`; the root page's HTML contains the intro scroll-hint text; no errors in the dev log.

Then, in a browser (this step cannot be fully automated — do it manually):
1. Visit `http://localhost:3000` — confirm the intro plays (cards scatter, then line up, then form a ring), confirm the eyebrow/heading/scroll-hint fade in.
2. Scroll down — confirm the ring smoothly morphs into a bottom arc as the "Interrogate the corpus" content fades in, and further scrolling shuffles the arc's card order.
3. Hover a card — confirm it flips to show its retrieval face (a teal score+snippet for vector-mode cards, a violet source/relationship/target for graph-mode cards).
4. Click "Ask a question" — confirm it navigates to `/app` and the existing chat app renders and works exactly as before.
5. Open browser devtools, enable "Emulate CSS prefers-reduced-motion: reduce" (Chrome: Rendering tab), reload — confirm cards snap directly to position without eased drift, and the small blinking dot / scroll-hint wheel animation are stopped.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: wire ScrollMorphHero into the landing route at /"
```

---

## Self-Review Notes

- **Spec coverage:** Architecture (route split, scroll re-architecture) → Tasks 1 and 5/6. Components (orchestrator, card, data, CSS) → Tasks 2–5, one task per file as the spec's file-structure section lays out. Data flow (static dataset, scroll→easing loop→DOM writes, CTA navigation) → Tasks 2 and 5. Edge cases (`prefers-reduced-motion`, mobile breakpoint) → Task 5. Testing → Task 6's manual verification checklist, covering every item in the spec's Testing section.
- **Placeholder scan:** no TBD/TODO; every code step contains complete, runnable code; every test step has an exact command and expected output.
- **Type consistency:** `CorpusDoc` (Task 2) is consumed identically by `CorpusCardProps` (Task 4) and `ScrollMorphHero`'s `docs`/`scatter` arrays (Task 5) — same field names throughout (`id`, `title`, `mode`, `score`, `fact`, `snippet`). `TOTAL_CORPUS_DOCS` (Task 2) is the single source of truth for the card count, used identically in Task 5's ring/arc math and the JSX's `.map()`. The `MORPH_BREAKPOINT = 0.2` constant in Task 5 matches the spec's documented 600/3000 ratio.
