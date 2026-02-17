# Client-Side LP Solver Design

## Problem

Every slider drag tick fires a network request to the Python backend (`/api/solve`), with only a 30ms debounce. This causes UI lag for the user and doesn't scale with multiple concurrent users.

## Solution

Move the solver to the browser using HiGHS WASM — a high-performance LP solver compiled to WebAssembly (~1-2MB). This eliminates server load for solving and enables real-time feedback during slider drag.

## Solver Choice: HiGHS WASM

- [highs-js](https://github.com/lovasoa/highs-js) — HiGHS C++ solver compiled to WASM via emscripten
- Gold-standard open-source LP/MIP solver (default in scipy)
- Accepts CPLEX `.lp` format strings
- ~1-2MB WASM bundle, loads asynchronously

## LP Reformulation

The existing CP-SAT model (solver.py, ~500 lines) is almost entirely linear. Key translation points:

**Direct LP translation (no changes needed):**
- Decision variables: `gram_vars` become continuous LP variables (fractional grams are fine)
- Calorie band: `target - tol <= sum(cal_coeff * g) <= target + tol`
- Hard macro constraints (gte/lte/eq): linear inequalities
- Micronutrient UL hard constraints: linear upper bounds
- Minimax variables: `w >= x_i` for all i (linear)
- Shortfall percentages: linear constraints
- Lexicographic weighted objective: single linear sum with tier weights

**Minor reformulation needed:**
- `abs_equality` (2 uses in macro ratio and eq-mode soft constraints): Replace `|x|` with standard LP split — introduce `x_pos, x_neg >= 0`, constrain `x = x_pos - x_neg`, use `x_pos + x_neg` as absolute value.

**Key simplification:** CP-SAT requires integer variables (hence SCALE=100, MICRO_SCALE=10000 tricks). LP handles continuous variables natively — drop all scaling, work in natural units (grams, mg, kcal).

## Architecture

### New Files

1. **`frontend/src/lib/solver.ts`** — LP model builder. Takes same inputs as Python solver, generates CPLEX `.lp` format string, calls HiGHS WASM, parses solution into existing `SolveResponse` shape.

2. **`frontend/src/lib/solver.worker.ts`** — Web Worker wrapper. Runs solver off main thread so UI stays smooth. Main thread posts solve inputs, worker posts back solutions.

### Modified Files

3. **`frontend/src/lib/api.ts`** — `solve()` switches from `fetch('/api/solve')` to posting a message to the worker. Same interface, no component changes needed.

### Unchanged

- All Svelte components (`IngredientRow`, `DualRangeSlider`, `StackedBar`, etc.)
- `SolveResponse` type shape
- `contributions.ts`
- `saveState()` — decoupled from solving, gets its own debounce (~500ms)

### Data Flow

```
slider oninput → triggerSolve (debounce ~50ms) → postMessage to worker
  → worker builds LP string → HiGHS.solve() → postMessage back
  → update solution state → $derived chains recompute → UI updates
```

Debounce can be ~50ms (no network latency, just WASM compute). If a new solve arrives while worker is busy, discard the stale result.

### Server Endpoint

`/api/solve` kept as optional fallback (e.g. WASM doesn't load), but no longer the default path.

## Testing & Rollout

**Validation:** LP solver won't produce identical results to CP-SAT (continuous vs integer grams), but should be within 1-2g per ingredient with matching constraint satisfaction.

**Test cases:**
- Feasible solutions satisfy all hard constraints (calorie band, macro bounds, UL limits)
- Infeasible cases correctly detected
- Minimax objectives work (worst-case shortfall minimized)
- Lexicographic priorities respected (higher tiers dominate lower)
- Edge cases: single ingredient, all at min, overlapping constraints

**Rollout steps:**
1. Build LP solver in TypeScript with unit tests
2. Wire into frontend via Web Worker
3. Run comparison tests against Python solver on saved scenarios
4. Make client-side the default, keep server as optional fallback
5. Later: remove server endpoint if desired

**Bundle size:** ~1-2MB WASM, loaded async in worker. First solve has ~200ms cold start (WASM compilation), subsequent solves are fast.
