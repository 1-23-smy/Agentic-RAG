# Scroll-Morph Landing Hero — Design

## Context

The Claude Design System project for this product ("Agentic RAG Design System", `1be284c1-1dff-42a4-beed-07d41d7c585e`) includes a concept UI kit, `ui_kits/agentic-rag-futuristic/`, explicitly marked as **not the production baseline** — a dark, neon, glassmorphic "neural console" skin exploring the product's dual vector/graph retrieval story with heavy motion. One piece of that kit, `scroll-morph-hero.html` + `ScrollMorphHero.jsx`, is a scroll-driven landing hero: 20 illustrative document/source cards fly in (scatter → line → ring), then scrolling morphs the ring into a bottom arc while "Interrogate the corpus" content fades in, and further scrolling shuffles the arc. Hovering a card flips it to reveal its retrieval face (a vector chunk's score/snippet, or a graph triple).

The production Next.js frontend (built in a prior plan) currently renders the chat app directly at `/`. This spec adds the scroll-morph hero as a new landing page at `/`, moving the chat app to `/app`.

## Goal

Port the scroll-morph hero into the Next.js frontend as a new landing page at `/`, faithful to the design's visual language, but driven by real page scroll instead of the original's wheel/touch-hijacking "virtual scroll," and linking into the existing chat app (moved to `/app`).

## Decisions (confirmed during brainstorming)

- **Placement:** new landing page at `/`. The existing chat app moves to `/app` (`frontend/app/app/page.tsx`), unchanged internally.
- **Visual fidelity:** exact concept skin, always dark — ignore the site's light/dark theme toggle entirely. This is a landing page, not part of the app shell, so a distinct always-dark neon-glass identity is intentional, matching the design system's own framing of this kit as a separate concept skin.
- **Scroll driver:** real page scroll, not the original's virtual-scroll wheel/touch hijack. A tall wrapping section with a `position: sticky` pinned stage; scroll progress (0–1) computed from real scroll position.
- **Card data:** illustrative static dataset, identical in spirit to the original's 20 hardcoded documents — no backend calls.
- **Routing:** chat app moves to `/app`. The hero's CTA ("Ask a question") navigates there via a real link.

## Architecture

- **`frontend/app/page.tsx`** — replaced to render `<ScrollMorphHero />` instead of `<ChatApp />`.
- **`frontend/app/app/page.tsx`** — new file, renders `<ChatApp />` (the entire existing chat app, moved verbatim from the old root page).
- The hero is a **self-contained visual system**, independent of the shared design-token system (`app/globals.css`) the rest of the site uses. Its CSS ports the original's hardcoded dark-neon values verbatim (not converted to `--surface-*`/`--accent` tokens), since this is a documented, deliberate exception — a distinct concept skin, not a token consumer. Class names keep the original's `smh-` prefix, which is already collision-safe against the rest of the site's Tailwind-utility-class approach.
- **Scroll re-architecture:** the original's `onWheel`/`onTouchMove` handlers call `preventDefault()` and accumulate a virtual `scroll` value capped at `MAX_SCROLL = 3000`, driving two ratios: `morph = clamp(scroll/600, 0, 1)` (ring→arc transition over the first 600 "virtual px") and `rotate = clamp((scroll-600)/(3000-600), 0, 1)` (arc shuffle over the rest). We replace the input source only: the page renders a real `<section>` of height `300vh` (three viewport heights of actual scroll distance) wrapping an inner stage that is `position: sticky; top: 0; height: 100vh`. A scroll listener (rAF-throttled) computes normalized progress via:

  ```
  rect = section.getBoundingClientRect()
  total = rect.height - window.innerHeight
  progress = clamp(-rect.top / total, 0, 1)   // 0 at section top, 1 when section has fully scrolled past
  ```

  This `progress` (already 0–1) replaces the old `scroll/MAX_SCROLL`, so the morph/rotate formulas become `morph = clamp(progress/0.2, 0, 1)` and `rotate = clamp((progress-0.2)/0.8, 0, 1)` — identical timing ratios to the original (600/3000 = 0.2), just fed by real scroll. The progress rail's fill height also becomes `progress * 100%` directly.
- `touch-action: none` is removed from the root element's CSS (it existed only to support the old touch-hijack pattern and would otherwise block native touch scrolling on mobile).
- Mouse parallax (`mousemove` → horizontal card offset) is unchanged — still a plain listener writing into the same ref-based animation state.
- The intro phase state machine (`scatter` → `line` → `ring`, via two `setTimeout`s) is unchanged — it runs on a fixed schedule regardless of scroll, exactly as in the original.
- The eased `requestAnimationFrame` loop (per-card `lerp` easing toward each frame's goal transform, plus intro/arc-text opacity and progress-rail height) is preserved essentially verbatim, just fed by the new `progress` value instead of the old wheel-accumulated one.

## Components

- **`frontend/components/landing/scroll-morph-hero.tsx`** — the orchestrator client component. Owns:
  - `containerRef`/`stageRef` and a `ResizeObserver` for container size (unchanged from original).
  - The scroll listener + rAF-throttled progress calculation (new, replacing wheel/touch listeners).
  - The mousemove parallax listener (unchanged).
  - The two intro-phase `setTimeout`s (unchanged).
  - The main `requestAnimationFrame` easing loop that computes each card's goal transform (scatter/line/ring/arc math, ported verbatim from the original) and imperatively writes `style.transform`/`style.opacity` to each card's DOM node via `cardRefs.current[i]` — matching the original's approach of bypassing React re-renders for per-frame animation of 20 cards.
  - Renders: intro text block, arc content block (heading/paragraph/CTA), the corpus card stage, and the progress rail.
  - Respects `prefers-reduced-motion`: when set, the easing loop's `lerp` factor is effectively 1 (each card snaps directly to its goal position/opacity every frame instead of interpolating), and the two purely decorative CSS keyframe loops (the live-status blink dot, the scroll-hint wheel animation) are disabled via the existing `@media (prefers-reduced-motion: reduce)` block — carried over from the original, extended to also cover the snap-vs-interpolate behavior.
- **`frontend/components/landing/corpus-card.tsx`** — a single flip-card, `forwardRef`'d so the orchestrator can attach it to `cardRefs.current[i]` and drive its transform imperatively. Renders the front face (document title/id/fake text lines, tinted by `mode`) and back face (vector: score + snippet; graph: source/relationship/target triple), reusing the original's hover-triggered 3D flip (`rotateY(180deg)` on `:hover`, pure CSS).
- **`frontend/components/landing/corpus-data.ts`** — pure data module. Exports a `CorpusDoc` TypeScript interface (`id`, `title`, `mode: "vector" | "graph"`, `score`, `fact: [string, string, string] | null`, `snippet: string | null`) and a `buildCorpusDocs(): CorpusDoc[]` function that reproduces the original's 20-item generation (alternating mode by index, cycling through fixed sample titles/facts/snippets/scores) — no randomness in the *content*, only in each card's initial scatter position (generated once via `useMemo` in the orchestrator, exactly as the original does).
- **`frontend/components/landing/scroll-morph-hero.css`** — the ported stylesheet. Visual values (colors, gradients, blur, font sizes, keyframes) are copied verbatim from the source design's `<style>` block. Two structural edits: (1) `touch-action: none` removed from `.smh-root`; (2) `.smh-root`'s sizing model changes from "fixed full-viewport root" to "sticky child inside a tall section" — in practice this means the *outer* wrapping section gets an inline `height: 300vh` (set in the TSX, not the CSS file, since it's a layout concern specific to how this component is embedded) while `.smh-root` itself becomes `position: sticky; top: 0; height: 100vh; overflow: hidden` (previously it was sized by filling a `100vh` parent directly). This is a plain global CSS file (not a CSS Module), imported directly in `scroll-morph-hero.tsx` — Next.js's App Router supports importing global stylesheets from any component, and the `smh-` prefix keeps this collision-safe against the rest of the site's utility-class-driven styling.

## Data flow

- No network calls anywhere on this page. `buildCorpusDocs()` runs once (module-level or via `useMemo`) to produce the 20 illustrative cards; their scatter positions are randomized once per mount via `useMemo`, then eased toward deterministic goal positions (scatter → line → ring → arc) by the rAF loop.
- Scroll progress (0–1, from the real-scroll calculation above) flows into the same ref-based animation state (`anim.current`) the easing loop already reads every frame — no React re-renders are triggered by scrolling; only direct DOM writes.
- The CTA is a `next/link` `<Link href="/app">` styled to match the original's pill button — clicking navigates (a real, prefetchable Next.js navigation) into the existing chat app.

## Edge cases / error handling

- `prefers-reduced-motion: reduce` — see Components section above; the whole-page scroll-driven animation is exactly the category of motion this media query exists to let users disable, so this spec extends the original's partial handling (which only covered two small decorative loops) to also flatten the main card easing.
- Small viewports (`width < 768`, the original's `isMobile` check controlling arc radius/card scale) is preserved as-is — no new mobile-specific behavior beyond what the source design already had.
- No loading or error states apply; this page performs no data fetching.
- The 300vh scroll section height is a fixed constant chosen to feel proportional to the original's virtual scroll range without being punishingly long to scroll through; it is not user-configurable and not derived from content.

## Testing

Matches the existing project convention (established in the prior frontend plan): no automated frontend test suite. Verification is manual:
1. `pnpm dev`, visit `/` — confirm the intro plays (scatter → line → ring), confirm scrolling smoothly morphs the ring into the bottom arc and further scrolling shuffles it, confirm hovering a card flips it to its retrieval face.
2. Confirm the CTA button navigates to `/app` and the existing chat app renders and functions exactly as before (no regression from the page move).
3. Confirm `cd frontend && pnpm exec tsc --noEmit` passes with no errors.
4. Manually toggle "reduce motion" in OS/browser accessibility settings (or via devtools' "Emulate CSS prefers-reduced-motion: reduce") and confirm cards snap to position without eased interpolation, and the two decorative loops stop animating.

## Out of scope

- Wiring the hero's corpus cards to real backend document data (`GET /documents`) — explicitly deferred; this page is illustrative/marketing, not a live data view.
- Any changes to the existing chat app's internal behavior — it is moved, not modified.
- A light-mode variant of the hero, or wiring it into the site's `next-themes` toggle — the hero is always-dark by design.
- SEO/metadata work for the new landing route beyond what Next.js provides by default.
