# Scroll-Morph Hero — Skip Linear Intro Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the "line" intermediate phase from the scroll-morph landing hero's intro sequence, so cards scatter on load and ease directly into the ring formation.

**Architecture:** Single-file change to `frontend/components/landing/scroll-morph-hero.tsx` — narrow the `Phase` type, simplify the intro timer effect to one timeout, and delete the now-unreachable `"line"` branch from the animation loop's per-card goal computation.

**Tech Stack:** Next.js 16, TypeScript, React 19 (existing stack, no new dependencies).

## Global Constraints

- Keep the scattered fly-in effect — only the linear intermediate shape is removed, not the whole intro animation.
- Keep the existing 2400ms timing for the scatter → ring transition.
- No changes to scroll-driven behavior (ring→arc morph, arc shuffle) — this only affects the pre-scroll intro sequence.
- No automated frontend tests (matches existing project convention). Verification is manual (`pnpm dev` + `tsc --noEmit`).

---

### Task 1: Remove the linear intro phase

**Files:**
- Modify: `frontend/components/landing/scroll-morph-hero.tsx:17` (Phase type), `:120-127` (intro sequence effect), `:150-155` (rAF loop's line-phase branch)

**Interfaces:**
- No change to `ScrollMorphHero`'s exported signature (still a no-prop component) — this is a pure internal-behavior change, nothing else in the codebase imports `Phase` or depends on the "line" phase existing.

- [ ] **Step 1: Narrow the `Phase` type**

Change line 17 from:

```typescript
type Phase = "scatter" | "line" | "ring";
```

to:

```typescript
type Phase = "scatter" | "ring";
```

- [ ] **Step 2: Simplify the intro sequence effect**

Change lines 119-127 from:

```typescript
  // intro sequence
  useEffect(() => {
    const t1 = setTimeout(() => setPhase("line"), 500);
    const t2 = setTimeout(() => setPhase("ring"), 2400);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []);
```

to:

```typescript
  // intro sequence
  useEffect(() => {
    const t1 = setTimeout(() => setPhase("ring"), 2400);
    return () => {
      clearTimeout(t1);
    };
  }, []);
```

- [ ] **Step 3: Delete the line-phase branch from the rAF loop**

Change lines 149-156 from:

```typescript
        let goal: CardTransform;
        if (p === "scatter") {
          goal = scatter[i];
        } else if (p === "line") {
          const sp = 74;
          const lineX = i * sp - (TOTAL_CORPUS_DOCS * sp) / 2;
          goal = { x: lineX, y: 0, rot: 0, scale: 1, op: 1 };
        } else {
```

to:

```typescript
        let goal: CardTransform;
        if (p === "scatter") {
          goal = scatter[i];
        } else {
```

- [ ] **Step 4: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors. (Since `Phase` no longer includes `"line"`, this step also confirms no other code in the file still references it — if it did, `tsc` would fail here.)

- [ ] **Step 5: Manual verification**

```bash
cd frontend
rm -rf .next
(pnpm dev > /tmp/skip-line-phase-check.log 2>&1 &)
sleep 5
curl -sf -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000
pkill -f "next dev" ; pkill -f "next-server"
tail -20 /tmp/skip-line-phase-check.log
```

Expected: `HTTP 200`, no errors in the log.

Then, in a browser (this step cannot be fully automated — do it manually, or via live browser tooling if available): visit `http://localhost:3000`, confirm cards start scattered at random positions, and by ~2.4s ease directly into the ring shape with no linear/horizontal-line arrangement visible at any point in between.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/landing/scroll-morph-hero.tsx
git commit -m "feat: skip linear intro phase in scroll-morph hero, go straight to ring"
```

---

## Self-Review Notes

- **Spec coverage:** the spec's single "Change" section (narrow `Phase`, simplify intro effect, delete line branch) maps 1:1 to this task's three edit steps. Testing section maps to Steps 4-5.
- **Placeholder scan:** no TBD/TODO; every step has complete, exact before/after code and exact commands with expected output.
- **Type consistency:** `Phase` is referenced in exactly two other places in the file (`useState<Phase>("scatter")` at line 34 and `useRef<Phase>("scatter")` at line 40) — both already use `"scatter"` as the initial value, which remains valid in the narrowed type, so no other line needs changing.
