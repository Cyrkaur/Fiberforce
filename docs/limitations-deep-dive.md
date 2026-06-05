# FiberForce Limitations Deep Dive

**Current as of the complete persistence + geometric builder wiring phase (May 2026).**

This document is deliberately blunt. FiberForce is a high-quality educational and hypothesis-generation tool, not a validated clinical or performance predictor. Read this before using the numbers for anything important.

## Unit Handling — v1 Imperial + ft-lb Torque (1.0)

v1 defaults to imperial (inches/ft/lbs) for user inputs (CLI/GUI/recipes via units="imperial", from_inches, load_lbs). Internal physics remain metric. Outputs emphasize ft-lb torque (peak_torque_ftlb property + reports). GUI uses custom generated images for premium visuals.

The previous cm-vs-m torque scaling bug in `calculations/peak_force.py` was corrected in 0.6:

- External torque is computed in N·m (load moment arm converted from cm → m).
- Muscle moment arms (stored in cm for human readability) are converted to meters before the division `F = Torque / lever_arm`.

**Result**: Absolute force values (`peak_force_newtons`) are now in the correct physical ballpark for the modeled loads and moment arms.

**Remaining honesty**:
- The model is still a **single-joint approximation**.
- Geometric moment arms are a **transparent educational prototype** (not in-vivo validated).
- Many simplifications remain (no multi-joint force sharing, conservative length-tension, static positions only, etc.).

Relative comparisons, deltas, rankings, and directional effects were already trustworthy. Absolute Newton values are now also much more meaningful, while still requiring the usual scientific caution.

## What the Model Actually Computes Today

- **Static peak force** at a single chosen joint configuration / bar position only. **Post-v1 dynrom MVP**: basic *continuous ROM* support via `analyze_continuous` / recipes (parameterized by primary joint angle range, linear interp on MA tables + angle interp, returns MultiPositionResult). Still per-snapshot peaks (no velocity, inertia, or true kinetics yet). Available for squat (knee-driven) + bench (shoulder-driven) as MVP; other lifts use proxies.
- Single-joint approximation for the primary action (e.g. horizontal adduction for sternal pecs on bench; hip extension for glute upper on squat).
- A conservative fixed length-tension factor (0.85) with no velocity dependence.
- Moment arms drawn from:
  - Synthesized reference tables (most regions / lifts / positions) + **MVP linear interp** for continuous angles.
  - The geometric prototype (only bench sternal pecs and squat glute/quad when rich anthropometry + `use_geometric=True` or direct estimator calls are supplied; continuous uses table interp or discrete geo calls)

No full dynamic range-of-motion simulation (MVP interp only), no multi-joint force sharing, no antagonist co-contraction, no fatigue accumulation, no technique execution variability.

## Geometric Moment Arm Prototype — Scope & Limitations

The geometric estimators (`reference/geometric.py` + `ReferenceData.estimate_moment_arm`) and the convenient builder support (`build_position(..., use_geometric=True)`) are a deliberate prototype and educational stepping stone.

**Currently supported**:
- Bench press: sternal pectoralis major horizontal adduction moment arm at the shoulder (driven by humerus length, biacromial width, grip width, torso depth).
- Squat: gluteus maximus hip extension MA at the hip + vastus lateralis (quad) knee extension MA at the knee (driven by femur, tibia, optional stance width).

**Not yet supported / still static**:
- All 8 lifts (bench, incline, squat, front, deadlift+sumo, romanian, ohp) now model their primary co-movers with per-joint load MAs + MA-relative dominance % (e.g. close vs wide bench shifts pec vs delt share at shoulder; low-bar vs high-bar squat biases glute % at hip; conv vs sumo DL changes load demand + posterior share). 2026 math clarification: the reported per-muscle "ft-lb" is now the *dominance share of joint torque* (not the full joint torque for every co-mover), so numbers differ (pec gets larger share than delt on flat bench because higher MA). This fulfills the "add all the muscles" + "percent of lift dominated by target like close/wide" request and the "same number for delt and pec" observation.
- Still snapshot static peaks only (dynrom/continuous is linear table interp per primary angle, not full kinetics).
- Dynamic MA curves over full ROM, subject-specific wrapping/landmarks.
- Full optimization-based force sharing (current: MA-proportional *torque partitioning* among same-joint co-movers after the 2026 math clarification. Previously all co-movers reported the *full* joint external torque (causing "same ft-lb number for pec and delt on bench" as noted by user). Now each reports its dominance share of the joint torque as peak_torque_ftlb; forces scaled for consistency so sum of per-muscle torques = joint total. Dominance % = MA_i / sum_MA (larger MA = higher share of torque credit / better leverage / lower F if sole). Matches directional grip/stance EMG/lit but is a simple proxy, not PCSA/activation/energetic optimization or measured in-vivo. L-T/F-V now applied + noted in continuous (basic v estimate from steps); PRs/trends on dom % + efficiency live in History + post-run (modeled only). See how-the-model-works.md and peak_force.py for the exact equations and assumptions.
- Some secondary regions (e.g. traps in OHP, abs, adductors) still use proxy or omitted.

Even when `use_geometric=True` is passed, unsupported cases gracefully fall back to the static tables (notes on the attachments record the source).

The estimators are pure-Python, transparent, law-of-cosines / trigonometric projection models. They are **not** validated against in-vivo or MRI moment arm studies. They were tuned to produce values directionally consistent with the existing reference tables.

See `examples/05_...`, `06_...`, the deep combined treatment in `examples/08_...` and especially `09_...`, and the full model + assumptions inside `geometric.py`.

## Multi-Variable Sensitivity — Current Nature

`AnalysisService.sensitivity_multi` / `SensitivityAnalyzer.run_multi` (and the profile helpers that call it) perform **sequential** sweeps: for a list of `(variable, values)` it sweeps the first variable while holding the others at their first supplied value, then the next, etc.

This is a pragmatic, powerful foundation that already reveals interaction effects no single-variable sweep can show (see 06/08/09).

**Not yet delivered**:
- True 2D (or higher) grid evaluation in a single call
- Native heatmap / surface visualization (the `SensitivityResult` objects already contain all the points you need; feeding them to pandas + seaborn is trivial in user code)

The architecture (custom `rebuild_multi` callables + persisted `SavedSensitivityRun`) was explicitly designed to make the grid + viz layer a small addition.

## Persistence Layer — What Is and Is Not There

The full enhanced persistence system (`results.py`, `SavedAnalysisRun` / `SavedSensitivityRun` / `SavedCompareRun`, `run_profile_*` helpers, `AnalysisService` integration, CLI surface, `save_profile_with_run`, etc.) is **production complete** and heavily exercised by Examples 08 and 09.

**It provides**:
- Robust, versioned, human-readable JSON round-tripping of complex nested dataclasses (no external deps)
- Profile name as the natural linking key between anthropometry and all result artifacts
- Timestamps, free-form notes, tags
- Convenient end-to-end helpers that analyze + persist in one call
- Discovery (`list_saved_runs`, `list_all_for_profile`) and loading

**It does not (yet) provide**:
- Automatic schema migration for future Saved*Run field additions (a placeholder hook exists)
- Built-in encryption or access control (files live in your home directory)
- Direct integration with external training logs / RPE databases (you attach context via `notes` and `tags` today; higher-level correlation is user code on top of the loaded runs)
- "Replay" that re-runs an old saved configuration against a newer version of the model (you can do this manually by loading the LiftConfiguration snapshot and re-analyzing)

The layer is stable and the recommended foundation for any serious personal or coaching tooling.

## Other Important Assumptions & Simplifications

- Reference moment arm tables are synthesized / literature-informed averages, not subject-specific.
- External load is modeled as acting through a single effective moment arm (no distributed bar + bodyweight effects beyond the basic model).
- No stabilization / co-contraction demand is calculated.
- Joint angles are user- or builder-specified snapshots; small changes in "bottom" position can move results.
- Confidence metadata is heuristic and useful for education/comparison but not a formal uncertainty quantification.

## When You Should *Not* Use FiberForce Today

- Any situation where absolute force numbers (in Newtons or "kg") will be treated as physiologically accurate or used for programming absolute intensities.
- Injury diagnosis, return-to-play decisions, or clinical load prescription.
- As a replacement for electromyography, force-plate, or validated biomechanical modeling software when high precision is required.
- Claims about "optimal" technique or equipment for an individual without acknowledging the prototype scope of the geometric component and the overall modeling simplifications.

## When FiberForce Is Excellent Today

- Generating quantitative, personalized hypotheses for your own training experiments ("wider grip appears to lower sternal demand more at higher loads for my proportions — let's test it").
- Comparing relative demand across variations, grips, stances, or body proportions in a consistent model.
- Educational exploration of *why* certain setups feel different (lever arms, anthropometry interactions).
- Longitudinal self-tracking when you treat the numbers as relative indices attached to your real profile and context.
- Prototyping the next generation of more accurate tools (the architecture is deliberately clean and extensible).

## GUI / Result Presentation & Interactive UX (current wave limits)
- Result "data return" is now visual-primary: live-updating cards with count-up ft-lb numbers + custom painted AnimatedDominanceBar (rounded, animated fills on form change or explicit run). The old QTextEdit (rich % + unicode bars + full .interpret() + lit) is secondary and collapsed by default (toggle to expand). This directly addresses "I dont want just the boring box with text".
- First-run: custom animated QStacked QDialog wizard (name + 5 key measurements) with opacity fade page transitions. Only on true first (QSettings + no profiles). Seeds live preview + persists. Re-runnable from Help. Skippable.
- Live interactive form: default ON for single analysis. Changing lift/variation/grip/load instantly (debounced) re-runs single analyze and animates the visual bars/numbers. Multi-position / continuous / history commit remain explicit-button to avoid surprise cost or history spam.
- Animation/popup limits of the system (PySide6/Qt native, no new deps):
  - Strong: QPropertyAnimation on numeric (value via stepped or custom), geometry, opacity (QGraphicsOpacityEffect) for count-ups, bar fills, fade/slide popups, page transitions in wizard. QParallelAnimationGroup available. Easing curves (OutCubic etc) for natural feel. Frameless or styled QDialogs for any "popup" (About, onboarding, future insight detail). Custom QWidget paintEvent for pro bars/toasts (we did rounded dominance).
  - Feasible but manual: true modeless toasts (temporary banner widget + fade timer), insight detail modals richer than QMessageBox.
  - Hard limits / not done: no built-in particle/confetti/"celebration" for new PRs (would require QPainter timer loop or extra lib); no 3D live visualizer or real-time skeleton without heavy (pyvista/vtk — bundle size killer, avoided); live continuous ROM would lag if not backgrounded (we limited live to single-pos); sync calc in live path can briefly block if future heavy models added (future: QThread + worker signals).
  - Bundle: already large (~PySide6); everything here stays inside existing imports + light custom paint.
- Always surfaced: "modeled estimate", "relative MA share / mechanical leverage proxy (not activation or full optimization)", "see limitations". Onboarding and live previews carry the same honesty.
- Still per-snapshot peaks under the hood; visuals just present the existing MPR/MuscleForceResult richer.

## Relationship to the Examples and Other Docs

Every one of the nine advanced examples contains a detailed Limitations section that is more specific to the concepts it demonstrates.

- See `docs/how-the-model-works.md` for the positive architectural description.
- See `docs/advanced-patterns.md` for recipes that explicitly call out where the current edges are.
- The nine scripts in `examples/` (especially 05, 06, **08**, and **09**) are the living, runnable documentation of both power and boundaries.

---

*FiberForce exists to help serious lifters think more quantitatively and anatomically about their training. It does this best when users treat it as a sophisticated hypothesis generator and relative comparator rather than a source of absolute truth. The project is intentionally transparent about every limitation so that the trustworthy parts (relative trends, geometric interaction effects, persisted personal archives) can be used with appropriate confidence.*