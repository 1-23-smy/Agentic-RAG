# Scroll-Morph Hero — ACT 3 Depth-Gallery Flythrough Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ACT 3 to the scroll-morph landing hero: an infinite, auto-playing depth-gallery flythrough of the corpus cards that begins once the user has scrolled through the existing ring→arc morph (ACT 1) and arc shuffle (ACT 2), with new content fading in over it.

**Architecture:** The existing real-scroll progress mechanism (0–1 across a tall sticky section) is extended to also drive ACT 3's "collapse" ramp, using the same proportional breakpoints as the source design (ACT 1 ends at 500/2900, ACT 2 ends at 1600/2900, ACT 3 collapse ramps from there to 1). This requires **no new scroll-hijacking to enter ACT 3** — it's simply the tail end of the same real-scroll range. Only once real-scroll progress is fully maxed (the user has scrolled all the way to the bottom of the section) does *forward* wheel/touch/arrow-key input get captured (`preventDefault`) and diverted into a velocity-driven, auto-playing, infinite-looping "fly" value — matching the source exactly. Scrolling *upward* while at the bottom is never captured, so it always hands control back to native scroll (and thus back to ACT 2/1), with no separate state machine needed.

**Tech Stack:** Next.js 16, TypeScript, React 19 (existing stack, no new dependencies).

## Global Constraints

- Acts 1/2 remain real-page-scroll-driven; only forward (downward) wheel/touch/arrow-key input, and only once scroll is fully exhausted, gets captured for ACT 3's infinite flythrough.
- The CTA button moves from ACT 2's arc content into new ACT 3 console content; ACT 2's arc content instead shows a "KEEP SCROLLING · WAKE THE AGENT" hint.
- `prefers-reduced-motion: reduce` disables the auto-play idle push and skips applying blur — user-initiated navigation (explicit wheel/touch/key input) still works.
- No automated frontend tests (matches existing project convention). Verification is manual (`pnpm dev` + `tsc --noEmit`).
- No new dependencies, no changes to `/app` (the chat app) or to the illustrative corpus dataset's titles/scores/facts.

---

### Task 1: Add `buildTunnelDirections` to the corpus data module

**Files:**
- Modify: `frontend/components/landing/corpus-data.ts`

**Interfaces:**
- Produces: `TunnelDirection` interface `{ x: number; y: number; rot: number }` and `buildTunnelDirections(count: number): TunnelDirection[]`, consumed by Task 3 (`scroll-morph-hero.tsx`).

- [ ] **Step 1: Append the new type and function**

Add to the end of `frontend/components/landing/corpus-data.ts` (after the existing `buildCorpusDocs` function):

```typescript
export interface TunnelDirection {
  x: number;
  y: number;
  rot: number;
}

/**
 * ACT 3 depth-gallery flight directions — one per card, spread evenly via
 * the golden angle so cards stream toward the camera from all directions
 * without visually clustering.
 */
export function buildTunnelDirections(count: number): TunnelDirection[] {
  return Array.from({ length: count }, (_, i) => {
    const ang = i * 2.39996; // golden angle in radians
    const r = 0.32 + (i % 5) * 0.15;
    return {
      x: Math.cos(ang) * r,
      y: Math.sin(ang) * r,
      rot: (i % 2 ? 1 : -1) * (4 + (i % 3) * 4),
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
git commit -m "feat: add buildTunnelDirections for ACT 3 depth-gallery flythrough"
```

---

### Task 2: Add ACT 3 styles

**Files:**
- Modify: `frontend/components/landing/scroll-morph-hero.css`

**Interfaces:**
- Produces: CSS classes `.smh-console-content`, `.smh-console-h`, `.smh-scrollhint--arc`, `.smh-navhint`, `.smh-navhint-sub`, consumed by Task 4 (JSX in `scroll-morph-hero.tsx`).

- [ ] **Step 1: Update `.smh-card`'s `will-change`**

Change (around line 166-174):

```css
.smh-card {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 66px;
  height: 90px;
  transform-style: preserve-3d;
  will-change: transform, opacity;
}
```

to:

```css
.smh-card {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 66px;
  height: 90px;
  transform-style: preserve-3d;
  will-change: transform, opacity, filter;
}
```

- [ ] **Step 2: Append the ACT 3 rules**

Add to the end of `frontend/components/landing/scroll-morph-hero.css` (after the `@media (prefers-reduced-motion: reduce)` block):

```css

/* ACT 3 — console content over the flythrough */
.smh-console-content {
  position: absolute;
  left: 0;
  right: 0;
  top: 63%;
  bottom: auto;
  z-index: 6;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 14px;
  padding: 0 24px;
}
.smh-console-h {
  font: var(--fw-extra) 52px/1.02 var(--font-display);
  letter-spacing: -0.04em;
  margin: 6px 0 0;
  background: linear-gradient(180deg, #fff, #a9b6de);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.smh-console-content::before {
  content: "";
  position: absolute;
  left: 50%;
  top: 46%;
  transform: translate(-50%, -50%);
  width: 720px;
  height: 360px;
  z-index: -1;
  pointer-events: none;
  background: radial-gradient(closest-side, rgba(6, 9, 18, 0.86), rgba(6, 9, 18, 0.45) 55%, transparent 80%);
  filter: blur(8px);
}
.smh-scrollhint--arc {
  margin-top: 10px;
  color: #8fa0c8;
}

/* ACT 3 navigation hint */
.smh-navhint {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 22px;
  z-index: 7;
  text-align: center;
  pointer-events: none;
  font: var(--fw-semibold) 11px/1.5 var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: #93a0c4;
}
.smh-navhint-sub {
  color: #5f6c90;
  letter-spacing: 0.14em;
}
```

- [ ] **Step 3: Verify no CSS syntax errors**

```bash
cd frontend
rm -rf .next
(pnpm dev > /tmp/act3-css-check.log 2>&1 &)
sleep 5
curl -sf -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000
pkill -f "next dev" ; pkill -f "next-server"
grep -i "error" /tmp/act3-css-check.log || echo "no errors in log"
```

Expected: `HTTP 200`, no errors. (These classes aren't consumed by any JSX yet — Task 4 wires them up — so this step only confirms the file parses cleanly.)

- [ ] **Step 4: Commit**

```bash
git add frontend/components/landing/scroll-morph-hero.css
git commit -m "feat: add ACT 3 console-content and nav-hint styles"
```

---

### Task 3: Extend the orchestrator with ACT 3 animation state and input handling

**Files:**
- Modify: `frontend/components/landing/scroll-morph-hero.tsx`

**Interfaces:**
- Consumes: `buildTunnelDirections`, `TunnelDirection` from `./corpus-data` (Task 1).
- Produces: the extended `anim` ref shape (adds `collapse`, `cSmooth`, `fly`, `flyVel`, `autoPlay`, `lastInteract`) and `ACT1_END`/`ACT2_END` constants, consumed by Task 4 (which adds the JSX that reads `cSmooth` via new refs).

This task replaces the entire file. The current file (before this task) has: constants `SCROLL_SECTION_VH`/`MORPH_BREAKPOINT`, a `Phase` type, a `CardTransform` interface, and the `ScrollMorphHero` component with its refs/effects/rAF loop/JSX. This task changes the constants, extends `CardTransform`, extends `anim`'s shape, adds a `tunnelDir` memo, extends the scroll-effect to add hijacked wheel/touch/keydown listeners, extends the rAF loop's math, and extends the JSX with two new refs (`consoleContentRef`, `navHintRef`) — Task 4 fills in those two refs' JSX content and the arc-content copy change, so this task's JSX additions are just the ref-bearing empty containers (Task 4 completes them).

- [ ] **Step 1: Replace the file**

```tsx
// frontend/components/landing/scroll-morph-hero.tsx
"use client";

import * as React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { CorpusCard } from "./corpus-card";
import { buildCorpusDocs, buildTunnelDirections, TOTAL_CORPUS_DOCS } from "./corpus-data";
import "./scroll-morph-hero.css";

const SCROLL_SECTION_VH = 300; // scroll distance, in viewport-heights, driving the full animation

// Proportional breakpoints matching the source design's virtual-scroll ratios
// (ACT 1: 0–500 of a 2900 total, ACT 2: 500–1600, ACT 3 collapse: 1600–2900).
const ACT1_END = 500 / 2900; // ring→arc morph completes
const ACT2_END = 1600 / 2900; // arc shuffle completes; ACT 3 collapse begins

const lerp = (a: number, b: number, t: number) => a * (1 - t) + b * t;
const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

type Phase = "scatter" | "ring";

interface CardTransform {
  x: number;
  y: number;
  rot: number;
  scale: number;
  op: number;
  blur: number;
}

export function ScrollMorphHero() {
  const sectionRef = useRef<HTMLElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);
  const introTextRef = useRef<HTMLDivElement | null>(null);
  const arcContentRef = useRef<HTMLDivElement | null>(null);
  const consoleContentRef = useRef<HTMLDivElement | null>(null);
  const navHintRef = useRef<HTMLDivElement | null>(null);
  const railFillRef = useRef<HTMLSpanElement | null>(null);
  const [phase, setPhase] = useState<Phase>("scatter");

  const docs = useMemo(() => buildCorpusDocs(), []);
  const tunnelDir = useMemo(() => buildTunnelDirections(TOTAL_CORPUS_DOCS), []);

  const anim = useRef({
    progress: 0,
    morph: 0,
    rotate: 0,
    collapse: 0,
    parallax: 0,
    mSmooth: 0,
    rSmooth: 0,
    cSmooth: 0,
    pSmooth: 0,
    fly: 0,
    flyVel: 0,
    autoPlay: true,
    lastInteract: 0,
  });
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
        blur: 0,
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

  // real-scroll progress (0–1 across the tall wrapping section, covering Acts
  // 1/2/3-collapse) + mouse parallax + ACT 3 hijack (forward input only, only
  // once progress is fully maxed — scrolling up always falls through to
  // native scroll, which naturally exits ACT 3).
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

    const nudge = (v: number) => {
      const a = anim.current;
      a.flyVel += v;
      a.autoPlay = false;
      a.lastInteract = performance.now();
    };

    const onWheel = (e: WheelEvent) => {
      if (anim.current.progress >= 1 && e.deltaY > 0) {
        e.preventDefault();
        nudge(e.deltaY * 0.0005);
      }
      // Otherwise: let native scroll handle it — the scroll listener above
      // recomputes progress, which naturally drives Acts 1/2/3-collapse.
    };

    let touchY = 0;
    const onTouchStart = (e: TouchEvent) => {
      touchY = e.touches[0].clientY;
    };
    const onTouchMove = (e: TouchEvent) => {
      const y = e.touches[0].clientY;
      const dy = touchY - y;
      touchY = y;
      if (anim.current.progress >= 1 && dy > 0) {
        e.preventDefault();
        nudge(dy * 0.0006);
      }
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (anim.current.progress < 1) return; // let native keyboard scrolling work for Acts 1/2
      if (e.key === "ArrowDown" || e.key === "ArrowRight") {
        e.preventDefault();
        nudge(0.03);
      }
      // ArrowUp/ArrowLeft while at the bottom: no preventDefault, so native
      // scroll-up regains control and exits ACT 3.
    };

    computeProgress();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("touchstart", onTouchStart, { passive: false });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  // intro sequence
  useEffect(() => {
    const t1 = setTimeout(() => setPhase("ring"), 2400);
    return () => {
      clearTimeout(t1);
    };
  }, []);

  // rAF loop — compute goals, ease (or snap under reduced motion), paint via refs
  useEffect(() => {
    let raf: number;
    const tick = () => {
      const a = anim.current;
      a.morph = clamp(a.progress / ACT1_END, 0, 1);
      a.rotate = clamp((a.progress - ACT1_END) / (ACT2_END - ACT1_END), 0, 1);
      a.collapse = clamp((a.progress - ACT2_END) / (1 - ACT2_END), 0, 1);

      const easeFactor = reducedMotionRef.current ? 1 : 0.09;
      a.mSmooth = lerp(a.mSmooth, a.morph, easeFactor);
      a.rSmooth = lerp(a.rSmooth, a.rotate, easeFactor);
      a.cSmooth = lerp(a.cSmooth, a.collapse, easeFactor);
      a.pSmooth = lerp(a.pSmooth, a.parallax, reducedMotionRef.current ? 1 : 0.08);

      // ACT 3 flythrough physics: auto-play resumes after 3s idle, velocity
      // decays each frame toward equilibrium. Disabled under reduced motion
      // (no automatic motion), but manual nudges from onWheel/onTouchMove/
      // onKeyDown still update flyVel/fly directly regardless.
      if (a.cSmooth > 0.01 && !reducedMotionRef.current) {
        if (performance.now() - a.lastInteract > 3000) a.autoPlay = true;
        if (a.autoPlay) a.flyVel += 0.00016;
        a.flyVel *= 0.94;
        a.fly += a.flyVel;
      }

      const { w, h } = size.current;
      const isMobile = w < 768;
      const minDim = Math.min(w, h);
      const p = phaseRef.current;
      const m = a.mSmooth;

      for (let i = 0; i < TOTAL_CORPUS_DOCS; i++) {
        let goal: CardTransform;
        let blurGoal = 0;
        if (p === "scatter") {
          goal = scatter[i];
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
          const shuffleShift = -clamp(a.rSmooth, 0, 1) * (spread * 0.8);
          // Wrap each card's position within the fixed [0, spread) window so cards
          // cycle back into view from the opposite edge instead of drifting off-screen
          // as shuffleShift grows — the visible arc always stays full.
          const wrappedOffset = (((i * step + shuffleShift) % spread) + spread) % spread;
          const ca = start + wrappedOffset;
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
            blur: 0,
          };

          // ACT 3 — fly through the corpus: an infinite depth gallery.
          const d = a.cSmooth;
          if (d > 0.001) {
            const dir = tunnelDir[i];
            const n = ((i / TOTAL_CORPUS_DOCS + a.fly) % 1 + 1) % 1; // 0 far → 1 near (streams toward camera)
            const depth = n * n; // accelerate as it approaches
            const tScale = lerp(0.16, 2.8, depth);
            const tx = dir.x * depth * (w * 0.64) + a.pSmooth * 0.4;
            const ty = dir.y * depth * (h * 0.64);
            let top = 1; // opacity: fade in far, fade out as it passes
            if (n < 0.12) top = n / 0.12;
            else if (n > 0.8) top = clamp(1 - (n - 0.8) / 0.2, 0, 1);
            let tb = 0; // blur at the far plane and as it rushes past
            if (n < 0.16) tb = (1 - n / 0.16) * 6;
            else if (n > 0.82) tb = ((n - 0.82) / 0.18) * 5;
            goal = {
              x: lerp(goal.x, tx, d),
              y: lerp(goal.y, ty, d),
              rot: lerp(goal.rot, dir.rot, d),
              scale: lerp(goal.scale, tScale, d),
              op: lerp(goal.op, top, d),
              blur: 0,
            };
            blurGoal = tb * d;
          }
        }
        const c = cur.current[i];
        c.x = lerp(c.x, goal.x, easeFactor);
        c.y = lerp(c.y, goal.y, easeFactor);
        c.rot = lerp(c.rot, goal.rot, easeFactor);
        c.scale = lerp(c.scale, goal.scale, easeFactor);
        c.op = lerp(c.op, goal.op, reducedMotionRef.current ? 1 : 0.1);
        c.blur = lerp(c.blur, blurGoal, reducedMotionRef.current ? 1 : 0.12);
        const el = cardRefs.current[i];
        if (el) {
          el.style.transform = `translate(-50%,-50%) translate(${c.x}px,${c.y}px) rotate(${c.rot}deg) scale(${c.scale})`;
          el.style.opacity = String(c.op);
          el.style.filter = !reducedMotionRef.current && c.blur > 0.06 ? `blur(${c.blur.toFixed(2)}px)` : "";
          el.style.zIndex = String(1000 + Math.round(c.scale * 400));
        }
      }

      if (introTextRef.current) {
        const o = clamp(1 - m * 1.7, 0, 1);
        introTextRef.current.style.opacity = String(o);
      }
      if (arcContentRef.current) {
        const o = clamp((m - 0.78) / 0.22, 0, 1) * clamp(1 - a.cSmooth * 2.2, 0, 1);
        arcContentRef.current.style.opacity = String(o);
        arcContentRef.current.style.transform = `translateY(${lerp(24, 0, o)}px)`;
      }
      if (consoleContentRef.current) {
        const o = clamp((a.cSmooth - 0.6) / 0.4, 0, 1);
        consoleContentRef.current.style.opacity = String(o);
        consoleContentRef.current.style.transform = `translateY(${lerp(22, 0, o)}px)`;
        consoleContentRef.current.style.pointerEvents = o > 0.5 ? "auto" : "none";
      }
      if (navHintRef.current) {
        navHintRef.current.style.opacity = String(clamp((a.cSmooth - 0.7) / 0.3, 0, 1));
      }
      if (railFillRef.current) {
        railFillRef.current.style.height = a.progress * 100 + "%";
      }

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [scatter, tunnelDir]);

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
          <p className="smh-scrollhint smh-scrollhint--arc">
            <span className="smh-arrow" />
            KEEP SCROLLING · WAKE THE AGENT
          </p>
        </div>

        <div ref={consoleContentRef} className="smh-console-content" style={{ opacity: 0 }}>
          <div className="smh-eyebrow smh-eyebrow--live">
            <i />
            AGENT ONLINE
          </div>
          <h2 className="smh-console-h">Ask the corpus anything.</h2>
          <p className="smh-arc-p">
            The corpus is indexed and the agent is live. It routes, retrieves, and cites in real
            time.
          </p>
          <Link href="/app" className="smh-cta">
            Ask a question<span>›</span>
          </Link>
        </div>

        <div className="smh-stage">
          {docs.map((doc, i) => (
            <CorpusCard
              key={doc.id}
              doc={doc}
              ref={(el) => {
                cardRefs.current[i] = el;
              }}
            />
          ))}
        </div>

        <div className="smh-rail">
          <span ref={railFillRef} className="smh-rail-fill" />
        </div>

        <div ref={navHintRef} className="smh-navhint" style={{ opacity: 0 }}>
          <p>Mouse wheel · arrow keys · touch to navigate the corpus</p>
          <p className="smh-navhint-sub">Auto-play resumes after 3 seconds of inactivity</p>
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
git commit -m "feat: add ACT 3 depth-gallery flythrough to scroll-morph hero"
```

---

### Task 4: End-to-end verification

**Files:**
- None (verification only — Task 3 already contains the complete implementation, including the JSX content this task verifies).

**Interfaces:**
- None — this task has no code changes.

- [ ] **Step 1: Automated verification**

```bash
cd frontend
rm -rf .next
(pnpm dev > /tmp/act3-e2e-check.log 2>&1 &)
sleep 5
curl -sf -o /tmp/act3-root.html -w "HTTP %{http_code}\n" http://localhost:3000
grep -o "AGENT ONLINE" /tmp/act3-root.html
grep -o "KEEP SCROLLING · WAKE THE AGENT" /tmp/act3-root.html
grep -o "Mouse wheel · arrow keys · touch to navigate the corpus" /tmp/act3-root.html
curl -sf -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000/app
pkill -f "next dev" ; pkill -f "next-server"
tail -20 /tmp/act3-e2e-check.log
```

Expected: both routes return `HTTP 200`; the root page's HTML contains all three new text snippets; no errors in the dev log.

- [ ] **Step 2: Manual browser verification**

In a browser (or via live browser tooling if available):
1. Visit `http://localhost:3000` — confirm the intro plays and scrolling through Acts 1/2 still works exactly as before (ring assembles, morphs to arc, shuffles).
2. Keep scrolling past the bottom of ACT 2 — confirm the "KEEP SCROLLING · WAKE THE AGENT" hint appears, then ACT 3 begins: cards start flying toward the camera, the "AGENT ONLINE" content and nav-hint footer fade in with a legible blurred backdrop.
3. Stop interacting for 3+ seconds while in ACT 3 — confirm the flythrough keeps gently auto-advancing on its own.
4. Try arrow-down/arrow-up keys while in ACT 3 — confirm arrow-down nudges the flythrough forward, arrow-up scrolls back up and exits ACT 3 into ACT 2.
5. Scroll up from ACT 3 with the mouse wheel — confirm it hands control back to normal scrolling (arc/ring visible again), rather than continuing to drive the flythrough.
6. Click the CTA button in ACT 3 — confirm it navigates to `/app` and the chat app renders correctly.
7. If testable, enable "Emulate CSS prefers-reduced-motion: reduce" in devtools, reload, scroll into ACT 3, and confirm it doesn't auto-advance when idle (no automatic motion), though manual scroll/key input still moves it.

- [ ] **Step 3: No commit needed**

This task is verification-only; if any issue is found, return to Task 3 and fix it there (commit the fix, then re-run this task's verification).

---

## Self-Review Notes

- **Spec coverage:** Architecture (real-scroll extension through collapse, hijack gated on progress>=1 and forward-only direction) → Task 3. Components (`buildTunnelDirections`, CSS additions, orchestrator extension) → Tasks 1, 2, 3 respectively, one task per file as the spec's Components section lays out. Data flow (progress→collapse→fly, imperative DOM writes, CTA relocation) → Task 3. Edge cases (re-entering Acts 1/2, reduced motion, mobile touch, blur threshold) → Task 3's code (gated conditionals) and Task 4's verification checklist item 4/5/7. Testing → Task 4, covering every item in the spec's Testing section.
- **Placeholder scan:** no TBD/TODO; every code step contains complete, runnable code; every test step has exact commands and expected output.
- **Type consistency:** `TunnelDirection` (Task 1) is consumed identically in Task 3's `tunnelDir` memo and per-card ACT 3 goal computation (`dir.x`/`dir.y`/`dir.rot`). `CardTransform`'s new `blur` field (Task 3) is initialized in the `scatter` array, read/written consistently in the rAF loop, and never referenced before Task 3 defines it. `ACT1_END`/`ACT2_END` (Task 3) replace the prior `MORPH_BREAKPOINT` consistently — no leftover reference to the old constant name anywhere in the replaced file.
- **Deliberate deviation from the source, consistent with the approved architecture:** the source's keydown handler always calls `preventDefault()` on arrow keys regardless of act, which would break native keyboard scrolling during Acts 1/2 in our real-scroll port. Task 3 gates keydown capture the same way as wheel/touch (only when `progress >= 1`, and only for the forward direction), preserving native keyboard scroll for Acts 1/2 while still matching the source's ACT 3 behavior exactly once reached.
