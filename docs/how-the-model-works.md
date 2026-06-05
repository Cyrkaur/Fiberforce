# How the Model Works

**Updated for the post-massive phase + geometric prototype + multi-variable sensitivity + full enhanced persistence + builder geometric wiring: AnalysisService as primary facade, full four-lift parity (bench/squat/deadlift conv+sumo/ohp with rich heads & positions), geometric moment arm estimators (direct + convenient `use_geometric` builder path), `sensitivity_multi`, the complete `results.py` persistence layer, visualization, profiles, and extensive testing.**

## High-Level Philosophy

FiberForce lets you create a personalized biomechanical model of *your* body and ask precise "what does this specific position and setup demand from this exact sub-region of muscle?" questions using straightforward mechanics (external load × moment arms / muscle moment arms, adjusted by a conservative length-tension factor).

The goal is to help you reason quantitatively about *why* small changes in grip, stance, bar position, ROM emphasis, or variation change the mechanical demand on very specific parts of your musculature — including interaction effects via multi-variable sensitivity and (in prototype form) your actual anthropometry via geometric estimators.

All outputs should be interpreted **relatively** because of a known unit bug in the core calculator (see limitations).

## Core Data Model (the "things" that flow through the system)

| Concept                  | Role                                                                 | Key Fields / Notes |
|--------------------------|----------------------------------------------------------------------|--------------------|
| `UserAnthropometry`      | Your personal measurements                                           | humerus, forearm, biacromial, torso_depth, femur, tibia, biiliac, measurement_date, notes |
| `Subject`                | Wrapper around anthropometry + name                                  | Used for every analysis |
| `AnalyzedPosition`       | Fully specified lift + variation + target regions + pose             | Carries the attachments (with MA values) that will be used |
| `MuscleAttachment`       | How a region attaches and its moment arm **at the analyzed position**| `joints_crossed`, `moment_arms_at_position` (from static reference tables **or** live geometric estimators in custom workflows or via `use_geometric=True`) |
| `MuscleForceResult`      | The final calculated peak force for one region                       | `peak_force_newtons`, `confidence_level`, rich `notes` (including MA source) |
| `AnalysisResult`         | Enriched container returned by `service.analyze`                     | results list + position description + assumptions |
| `SensitivityResult`      | Structured output from single- or multi-variable sensitivity sweeps  | `points` (list of `SensitivityPoint` with variable + force + confidence), ready for visualization or persistence |
| `Saved*Run` (results.py) | Persisted artifacts (analysis, sensitivity incl. multi-var, compare) | Full round-trippable dataclasses with profile_name, timestamp, notes, tags, the original config + results |

## The Main Layers (data flow)

1. **Profiles & Subject creation**
   - `save_anthropometry` / `load_anthropometry` (and the higher `save_profile_with_run`)
   - `AnalysisService.create_subject_from_measurements(...)` or `load_profile_for_analysis`
   - Rich measurements are the key that unlocks the geometric prototype.

2. **Position / Builder layer** (`fiberforce/examples.py` + `service.build_position`)
   - The single recommended way to create `AnalyzedPosition` objects for the four supported lifts.
   - Accepts high-level parameters (load, variation, target_region_name, segment lengths, grip/stance, `use_geometric`).
   - For supported cases (bench sternal, squat glute/quad) and when `use_geometric` is not explicitly False, the builders now call through `ReferenceData.estimate_moment_arm` → the geometric estimators. Clear notes record the source. This is the convenient "latest" path.

3. **Reference data** (`reference/`)
   - `moment_arms.py`: the synthesized static tables (full coverage for all lifts/regions).
   - `geometric.py`: the prototype estimators (bench sternal + squat glute/quad) + pure functions you can call directly.
   - `data.py`: `ReferenceData` facade with `estimate_moment_arm` dispatch and versioning.

4. **Calculation layer**
   - `SimplePeakForceCalculator` (the current engine): torque balance → muscle force = (load_moment + segment effects) / muscle_moment_arm × (1 / length_tension_factor).
   - For co-prime-movers on the *same joint* (e.g. sternal pec + anterior delt on shoulder for bench press), we use MA-proportional torque partitioning:
     dominance_i = MA_i / sum(MA on joint)
     torque_share_i = dominance_i * external_joint_torque
     F_i (effective) scaled so that the reported peak_torque_ftlb for the muscle is its share (not the full joint torque).
     Sum of shares across co-movers on a joint = the full external joint torque.
     This makes "ft-lb" numbers different per muscle (larger MA muscle gets larger torque share / credit).
     Dominance % now directly corresponds to the fraction of the (reported) torque "done by" that muscle in the model.
   - Assigns confidence + rich notes (including when geometric estimators were used).
   - `service.sensitivity(...)` and `service.sensitivity_multi(...)` wrap the analyzer with the same enrichment.

5. **Sensitivity / Compare / Visualization layers (now with multi-var + geometric + persistence)**
   - `SensitivityAnalyzer.run_multi(..., rebuild_multi=callable)` — multi-var sequential (new foundation).
   - `AnalysisService.sensitivity_multi` is the convenience wrapper.
   - You can supply rebuilds that call the live geometric estimators (directly or, preferably, via `build_position(..., use_geometric=True)`) — this makes segment lengths mechanically active in sensitivity studies today (see 05/06/08/09).
   - `service.compare` and `plot_comparison` for clean A/B deltas.
   - Full `results.py` layer saves and reloads `SensitivityResult` lists, `AnalysisResult`, `ComparisonResult`, etc., tied to profiles.

6. **Persistence layer (complete)**
   - Everything important can be saved as typed `Saved*Run` objects (analysis, full multi-var sensitivity surfaces, compares).
   - Profile name is the foreign key.
   - Helpers such as `run_profile_multi_sensitivity`, `service.save_current_analysis`, `save_profile_with_run`, `list_all_for_profile`, and the CLI `profile` subcommands give you end-to-end "measure once, analyze + persist many times, load later" workflows.
   - All nine examples (especially 07/08/09) demonstrate the system; 08 and 09 are the most comprehensive.

7. **Service facade** (`analysis/service.py`)
   - The "one ring to rule them all." Almost all real usage should go through an `AnalysisService` instance.
   - It owns the calculator, sensitivity analyzer, reference, and context.
   - It provides `build_position` (the only builder you should normally call), `sensitivity_multi`, `save_current_analysis`, passthroughs to the profile persistence helpers, etc.
   - `service.describe()` is your friend — it tells you exactly what capabilities the current instance exposes.

## Geometric + Builder Integration (the "latest wiring")

The geometric direction has two usage styles, both fully supported:

- **Convenient (recommended for most work)**: Pass `use_geometric=True` (and your measurements) to `service.build_position` or the profile helpers. The builders internally call the estimators for supported regions and record the source in attachment notes. `use_geometric=False` forces the classic static path.
- **Maximum control / custom math**: Call `estimate_bench_sternal_ma(anthro, grip=...)` or `estimate_squat_glute_ma(...)` directly inside your own `rebuild_*` functions (as demonstrated in 05/06 and still valuable in 08/09 for transparency).

Both styles are exercised heavily in the new advanced examples.

## Multi-Variable Sensitivity & Persistence

`run_multi` + custom `rebuild_multi` (dict of current parameter values → new `AnalyzedPosition`) is the pragmatic foundation. When the rebuild uses geometric (via the builder flag or direct calls), every point on the surface reflects *your* skeleton + the exact grip/stance/load combination being evaluated.

The entire result (list of `SensitivityResult` objects) can be wrapped in a `SavedSensitivityRun`, persisted with your profile, and loaded later for new questions. Examples 08 and 09 show the full pattern end-to-end.

## Output You Can Trust Today

- Relative rankings and deltas between variations, grips, stances, or body types on the *same* model.
- Slopes and interaction effects from single- and multi-variable sweeps (especially when geometric is active).
- Differences between static-table modeling and live geometric modeling for the supported cases (a powerful diagnostic in its own right).
- Any analysis or sensitivity surface you persist with a profile — the data model gives you everything needed for custom longitudinal tooling.

## What Is Deliberately Out of Scope (for now)

- Absolute physiological accuracy of force numbers (unit bug + many modeling simplifications).
- Full 3D multi-joint rigid body dynamics or muscle path wrapping.
- Dynamic MA over a full ROM (the current geometric is snapshot-oriented).
- Velocity, rate of force development, fatigue, or technique variability.
- Clinical or diagnostic use.

These are acknowledged in every Limitations section and in `docs/limitations-deep-dive.md`.

---

Use the service. Save rich profiles. Drive geometric multi-var studies through the convenient builder path or direct estimators. Persist the important artifacts. Load them later. Visualize the relative trends. Treat the absolutes as directional. That is the current complete, honest, and powerful way to use FiberForce.

See the nine runnable examples (especially 05–09) and the other three docs for the concrete code and deeper discussion.