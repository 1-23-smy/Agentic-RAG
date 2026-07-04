# Scroll-Morph Hero — Skip Linear Intro Phase — Design

## Context

The scroll-morph landing hero (`frontend/components/landing/scroll-morph-hero.tsx`) plays a fixed intro sequence on page load, before any user scroll: cards scatter to random positions, then assemble into a horizontal line at 500ms, then form a ring at 2400ms. The user wants the linear intermediate step removed so the default resting state (before scrolling) is directly the ring/circular formation.

## Goal

Remove the "line" phase from the intro sequence. Cards should scatter on load, then ease directly into the ring formation — no linear intermediate step.

## Decisions (confirmed during brainstorming)

- Keep the scattered fly-in effect (cards still start at random positions and animate in) — only the linear intermediate shape is removed, not the whole intro animation.
- Keep the existing 2400ms timing for the scatter → ring transition (same overall pacing as before, just skipping the visual midpoint).

## Change

In `frontend/components/landing/scroll-morph-hero.tsx`:

- The `Phase` type narrows from `"scatter" | "line" | "ring"` to `"scatter" | "ring"`.
- The intro `useEffect` currently sets two timeouts (500ms → `"line"`, 2400ms → `"ring"`); this becomes a single timeout: 2400ms → `"ring"` (initial state remains `"scatter"`).
- The rAF loop's per-card goal computation currently has three branches (`scatter` / `line` / `ring`); the `line` branch is deleted since that phase no longer exists in the type.
- No changes to the scatter or ring position math — cards still fly in from random scattered positions and ease directly into the ring shape at 2.4s.
- No changes to scroll-driven behavior (ring→arc morph, arc shuffle) — this only affects the pre-scroll intro sequence.

## Testing

Matches existing project convention: no automated frontend tests. Manual verification: `pnpm dev`, load `/`, confirm cards scatter then ease directly into the ring at ~2.4s with no linear intermediate shape visible, and `tsc --noEmit` passes.

## Out of scope

- Any change to scroll-driven morph/arc/shuffle behavior.
- Any change to intro timing beyond removing the linear step (2400ms transition kept as-is).
