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
      </div>
    </section>
  );
}
