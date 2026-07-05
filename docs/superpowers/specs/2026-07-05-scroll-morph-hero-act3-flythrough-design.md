# Scroll-Morph Hero — ACT 3 Depth-Gallery Flythrough — Design

## Context

The scroll-morph landing hero (`frontend/components/landing/scroll-morph-hero.tsx`) was previously implemented with two acts, both driven by real page scroll: ACT 1 (ring → bottom arc morph) and ACT 2 (arc shuffle). The Claude Design System project's source file (`ui_kits/agentic-rag-futuristic/scroll-morph-hero.html` + `ScrollMorphHero.jsx`) has since been updated with a new **ACT 3**: once the user has scrolled through the arc assembly, further scroll/touch/keyboard input triggers an infinite, auto-playing "depth gallery" flythrough — cards stream toward the camera in a continuous loop, each entering blurred at a far distance, sharpening as it approaches, then blurring and fading again as it rushes past. New content ("AGENT ONLINE" / "Ask the corpus anything.") fades in over this flythrough with a blurred backdrop for legibility, along with a navigation hint footer.

The source's mechanism for this is fundamentally scroll-hijacking: once its internal virtual-scroll counter is maxed out, further wheel/touch/arrow-key input stops moving the counter and instead adds velocity to a separate looping "fly" value, which decays over time (damping) and auto-resumes (gentle forward push) after 3 seconds of no interaction. This is a deliberate architectural exception to the "real page scroll drives everything" decision made for Acts 1/2 — confirmed with the user: ACT 3 should be ported with full fidelity to the source (infinite loop, auto-play, keyboard capture), accepting that this one act uses hijacked input while Acts 1/2 remain real-scroll.

## Goal

Add ACT 3 to the existing scroll-morph hero: once real scroll (driving Acts 1/2) is exhausted, transition into a hijacked-input mode that drives an infinite, auto-playing depth-gallery flythrough of the 20 corpus cards, with new content fading in over it, matching the source design exactly.

## Decisions (confirmed during brainstorming)

- **Driver split:** Acts 1/2 stay real-page-scroll-driven (unchanged). ACT 3 is triggered once real-scroll progress reaches 1.0, at which point wheel/touch/arrow-key input is captured (`preventDefault`) and converted to flythrough velocity instead of attempting to scroll a maxed-out page. Scrolling back up (native scroll delta indicating upward intent while still at progress 1.0) hands control back to real-scroll for Acts 1/2.
- **Content:** adopt the source's content change exactly — the CTA button moves from ACT 2's arc content (which now shows a "KEEP SCROLLING · WAKE THE AGENT" hint instead) into new ACT 3 content ("AGENT ONLINE" eyebrow, "Ask the corpus anything." heading, new paragraph, CTA button), which fades in with a blurred radial-gradient backdrop for legibility over the moving cards behind it. A navigation hint footer ("Mouse wheel · arrow keys · touch to navigate the corpus" / "Auto-play resumes after 3 seconds of inactivity") fades in alongside it.
- **Timing renormalization:** the source's virtual-scroll ratios (ACT 1: 0–500 of a 2900 total, ACT 2: 500–1600, ACT 3: 1600–2900) are renormalized so that real-scroll progress 0→1 maps to the source's virtual 0→1600 (Acts 1+2 only, since ACT 3 no longer consumes real scroll distance). This changes the ring→arc morph breakpoint from the previously-implemented 0.2 to 500/1600 = 0.3125, preserving the design's relative pacing between Acts 1 and 2. The section height stays 300vh.

## Architecture

- **Real-scroll phase (Acts 1/2):** unchanged mechanism (tall sticky section, `getBoundingClientRect`-based progress calculation), but `MORPH_BREAKPOINT` changes from `0.2` to `0.3125` to match the renormalized ratio above. Nothing else about Acts 1/2's math changes.
- **ACT 3 trigger:** a new piece of animation state, `collapse`/`cSmooth` (0–1, easing towards 1 once real-scroll progress is maxed), computed each frame as `clamp((virtualAct3Position) / act3Range, 0, 1)` — but since ACT 3 has no real-scroll distance of its own, its "virtual position" is instead driven by a `fly` accumulator fed by hijacked input, gated as follows:
  - While real-scroll `progress < 1`: ACT 3 input capture is inactive; wheel/touch/keydown behave natively (real scroll works as today).
  - Once `progress` reaches `1` (user has scrolled to the bottom of the section): attach `wheel`/`touchmove`/`keydown` handling that calls `preventDefault()` and adds to `flyVel` (matching the source's `nudge()` function) instead of letting the (already-exhausted) native scroll try to move further. A wheel/touch gesture with upward intent while `collapse` is still low hands control back to native scroll (sets a flag that lets the section's real scroll respond again).
  - `flyVel` decays each frame (`flyVel *= 0.94`) and gets a small constant push (`flyVel += 0.00016`) whenever the page has been idle (no hijacked input) for 3+ seconds — reproducing the auto-play behavior verbatim.
  - `collapse` itself ramps from 0 to 1 based on elapsed hijacked-scroll "distance" (accumulated `|flyVel|`-driven progress) the first time ACT 3 is entered, exactly mirroring the source's `cSmooth` fade-in of the ACT 3 content and blur/scale ramp — once fully collapsed into ACT 3, `collapse` stays at 1 and only `fly` (the looping position) continues to change.
- **Per-card depth-gallery math:** appended to the existing "ring" branch's goal computation (after the ring→arc lerp), gated by `collapse > 0.001` exactly as the source does — each card gets a golden-angle flight direction (`buildTunnelDirections()`), a looping depth `n = ((i/TOTAL + fly) % 1 + 1) % 1`, and from `n` derives scale (0.16 far → 2.8 near), position (radial offset scaled by `depth = n*n` for acceleration), opacity (fade in over the first 12% of depth, fade out over the last 20%), and blur (blurred entering at the far plane, sharp through the middle, blurred again rushing past near the camera) — all lerped verbatim from the source's formulas.

## Components

- **`frontend/components/landing/scroll-morph-hero.tsx`** (extended):
  - New refs: `consoleContentRef`, `navHintRef`.
  - New `anim` state fields: `collapse`, `cSmooth`, `fly`, `flyVel`, `autoPlay`, `lastInteract`.
  - New effect: hijacked wheel/touch/keydown listeners, gated as described above, replacing/extending the existing real-scroll effect (the real-scroll `computeProgress` logic stays; the hijack listeners are additive and only act once `progress` is maxed).
  - Extended rAF loop: `collapse`/`cSmooth` computation, the auto-play/damping physics for `flyVel`/`fly`, the ACT 3 per-card goal branch (scale/position/opacity/blur), and imperative `style.filter` writes on each card (new — Acts 1/2 never set blur).
  - New JSX: the `consoleContent` block (mirrors the existing `arcContent` block's fade-in pattern) and the `navHint` footer block.
  - Modified JSX: `arcContent`'s CTA `<Link>` replaced with the new "KEEP SCROLLING · WAKE THE AGENT" hint paragraph; the CTA `<Link href="/app">` moves into the new `consoleContent` block.
- **`frontend/components/landing/corpus-data.ts`** (extended): new pure function `buildTunnelDirections(count: number): TunnelDirection[]` (golden-angle spread, exported type `TunnelDirection = { x: number; y: number; rot: number }`), generated once via `useMemo` in the orchestrator exactly like `buildCorpusDocs()` already is.
- **`frontend/components/landing/scroll-morph-hero.css`** (extended): `.smh-console-content` + its `::before` blurred backdrop, `.smh-scrollhint--arc`, `.smh-navhint` + `.smh-navhint-sub`, and `.smh-card`'s `will-change` gains `filter`.
- **`frontend/components/landing/corpus-card.tsx`**: unchanged.

## Data flow

- No network calls (same as before).
- Real-scroll progress flows into `morph`/`rotate` exactly as today (with the renormalized breakpoint).
- Once maxed, hijacked wheel/touch/keydown deltas flow into `flyVel` → `fly` (accumulated, wrapping via modulo per-card) → each card's depth-gallery transform/opacity/blur, written imperatively to the DOM every frame, bypassing React re-renders (same performance pattern as Acts 1/2).
- `collapse`/`cSmooth` gates both the ACT 3 per-card math and the fade-in of `consoleContent`/`navHint`, mirroring how `morph` already gates `introText`/`arcContent`.

## Edge cases

- **Re-entering Acts 1/2 from ACT 3:** while `collapse` is still ramping up (or has just reached 1), an upward wheel/touch gesture should hand control back to real scroll rather than going negative into nonsensical `flyVel` territory — implemented by checking gesture direction and only treating downward/forward input as ACT 3 fuel once fully collapsed; upward input while `collapse < 1` reduces `collapse` back toward 0 and restores real-scroll authority.
- **`prefers-reduced-motion`:** extends the existing reduced-motion handling — `cSmooth`/`fly` easing collapses to instant (no eased ramp), and the auto-play idle-push is disabled entirely (no forced motion when the user hasn't interacted and has requested reduced motion).
- **Mobile:** touch swipe-up while at the bottom drives `flyVel` the same way wheel does on desktop, matching the source's `onTM` handler logic.
- **Blur performance:** `filter: blur()` is only written to the DOM when `blur > 0.06` (matching the source's threshold), avoiding needless style writes when a card is sharp — same performance-conscious pattern the source already uses.

## Testing

Same as before: no automated frontend tests. Manual verification via `pnpm dev`:
1. Scroll through Acts 1/2 as before (ring assembles, morphs to arc, shuffles).
2. Keep scrolling/swiping past the bottom — confirm ACT 3 triggers, cards begin flying toward the camera in a visible loop.
3. Stop interacting for 3+ seconds — confirm the flythrough keeps gently auto-advancing.
4. Try arrow keys and (if testable) touch swipe — confirm both nudge the flythrough forward/backward.
5. Confirm the new "AGENT ONLINE" content and nav-hint footer fade in over the flythrough with legible contrast (blurred backdrop working).
6. Click the CTA in ACT 3 — confirm it navigates to `/app`.
7. Scroll back up from ACT 3 — confirm it hands control back to normal real-scroll for Acts 1/2.
8. `tsc --noEmit` passes.

## Out of scope

- Any change to the chat app at `/app`.
- Any change to the illustrative corpus dataset itself (titles/scores/facts) — only a new `buildTunnelDirections()` data function is added.
- Visual/theme changes beyond what's specified in the source's ACT 3 CSS additions.
