# FiberForce — Next Level Roadmap (Post v1.0)

**Date**: Immediately after exercise expansion (Incline Bench + RDL added) and "lets talk about what can be done to take this app to the next level?" planning session.
**Current Version**: 2.0.0 (v2.0 — The Clickable Icon App delivered; see Theme 4 update below + GAMEPLANS v2 section). Previous 1.0.0 + dynrom Wave 1 + 8-lift expansion complete.
**Purpose**: Structured options for evolution. Not a commitment — user chooses themes/waves. Maintains the hybrid goal (real advances + Grok Build feedback via AGENT_FEEDBACK).

See also: `GAMEPLANS.md` (Post-v1 Scope Expansion section), `docs/limitations-deep-dive.md` (primary source of gaps), `README.md` (current scope + honest note), `AGENT_FEEDBACK.md`.

## Current State Snapshot (assessed live in planning session)
- **Core**: AnalysisService, imperial default (inches/ft/lbs + ft-lb torque via from_inches/load_lbs/peak_torque_ftlb), rich .interpret()/.insight() on results, multi-pos + WeeklyProgram/TrainingSession with accumulation.
- **Lifts/Exercises** (PRIMARY_LIFTS model): Bench Press, Incline Bench Press, Overhead Press, Back Squat, Front Squat, Conventional Deadlift, Sumo Deadlift, Romanian Deadlift. Reference data + builders for main 4 + recent 2 (Incline/RDL added with proxy geometric, full integration, no regressions on prior). list_available_lifts() reflects expanded set.
- **Geometric**: Prototype (bench sternal + squat glute/quad native; proxies used for new lifts).
- **GUI** (fiberforce gui / python -m fiberforce.gui): 7+ tabs (Athlete inches, Single/Multi/Sensitivity/Programs/Quick Recipes/History-Exports with real persistence now), 9 generated assets (splash, icon, header_banner (now used only in About), result_viz, coaching_dashboard, torque_viz + extras), dark Mac QSS, menu (incl. Run Internal Smoke verifier), rich logs, exports. Exercises everything. Post-v2 polish: removed persistent top header_banner from main layout (was wasting vertical space above tabs); brand now via native titlebar icon + macOS menu bar Help > About (custom QDialog with hero image + v2 blurb). Tabs + fields + plots now dominate per desktop/fitness app conventions researched (HIG, NN/g, Strong/Hevy etc.). See CHANGES + AGENT_FEEDBACK for details.
- **Packaging/Distribution**: scripts/build_macos_app.sh (from real briefcase attempt that produced ~4GB build/fiberforce/macos/app/FiberForce.app bundle with embedded GUI). Existing build/ artifacts present. Lib is pip-installable with [gui,viz] extras. No PyPI publish or signed/notarized DMG yet. Cross-platform limited.
- **Other**: 200+ tests (geometric heavy, persistence, service), 11 examples (flagships are coaching scenarios), CLI full parity, persistence (Saved* + profiles), visualization (matplotlib + ASCII), confidence metadata on ref data, smoke/verify that now covers new lifts.
- **Honest gaps** (pulled from limitations-deep-dive + code + GAMEPLANS): static/discrete positions only (no full continuous dynamics/ROM curves), geometric limited, single-joint approx, prototype-grade ref data (no in-vivo validation), no fatigue/force-velocity/full advanced muscle models, GUI desktop Mac-focused (no 3D viz, limited history power), packaging functional but heavy/unsigned, no built-in study comparisons or measurement wizard, limited extensibility for custom lifts.
- **Strengths for evolution**: Clean facade (service), duck-typing results, imperial everywhere, real persisted runs on disk, dual artifacts for feedback, proven process (todo discipline, live verif from volume workspace, no regressions in prior expansions).

**Vision reminder** (unchanging): Personalized measurements → regional peak force/torque demands on primary compounds at static+multi positions. Usable for lifters/coaches (imperial, GUI that displays rich outputs, brutal honesty on prototype limits). No clinical claims, no full dynamics/prescription in core v1 spirit.

## Proposed Themes for Next Level
Prioritized options synthesized from limitations, GAMEPLANS ("more rows or deeper geometric"), user history (exercises/visuals/GUI/packaging/"improve everything"), code inspection, and vision. Each includes rough effort/impact (relative), alignment, feedback value for Grok Build, and risks.

### Theme 1: Modeling & Scientific Depth (Strongest alignment to "biomechanics" identity)
- Full continuous dynamic ROM (angle-by-angle interpolation, MA curves).
- Advanced muscle models: proper length-tension curves (data-driven), force-velocity, series elastic, improved pennation/excursion.
- Major geometric expansion: native estimators for more regions (clavicular, full hamstrings/erectors, all delts/triceps for OHP/rows/incline), more lifts (deadlift variants, RDL, rows), better 3D/wrapping.
- Multi-joint considerations + stability (still peak-force focused).
- Validation layer: built-in study/EMG/force-plate comparisons; "matches literature within X%" notes.
- **Engagement / self-competition layer on the outputs (new "New Level" direction post-v2 branding)**: Personal records (max modeled ft-lb regional peaks over persisted Saved* runs), trends/deltas vs history or personal best, "consistency" (low force_variation_coefficient), geo-quality signals, milestones (e.g. number of multi-pos/continuous runs logged). Upgraded History tab ("Progress & Personal Records"), post-run progress moments appended to .interpret() output, subtle highlights in existing dark theme. All framed exactly as the existing honest interpret/report language ("modeled estimate", "relative within same athlete", "reference + optional geometric"). Builds directly on the rich MPR aggregates, accumulators, SavedMultiPositionRun (ft-lb, timestamps, geo flags, variation), WeeklyProgram.compare, etc. — no fake XP or cartoon levels. Self-competition only (Strava segments/PRs style for your own modeled regional torque demand).
- Delivered in immediate prior + this continuation wave: multi-prime-mover + per-joint + dominance % for all 8 lifts (grip/stance/pos effects on % as in close/wide bench + lit audit); PRs/trends/bars/compare on dom % + L-T/F-V notes in continuous. See CHANGES + plan.md for details.
- **Effort/Impact**: High / Very High.
- **Alignment**: Directly attacks the biggest "prototype" caveats while making the tool feel alive and rewarding (addresses "not just a form style or boring app").
- **Grok Build feedback opportunities**: Subagent research on recent MA papers, iterative design of new math (accuracy vs simplicity tradeoffs), testing validation workflows; also how to layer honest gamification/reward loops on scientific outputs without over-claim.
- **Risks**: Can explode scope/complexity; data quality must stay honest (no over-claim). Gamify must never dilute the "brutally honest prototype" promise.
- **Suggested first MVP (interleaved per 2026 "new level" user direction)**: One focused depth slice (e.g. basic length-tension over continuous ROM or expanded continuous geo + MA curve) + PR/trend layer on current + new data (History upgrade + post-run callouts using existing ft-lb/variation/geo fields). User clarified: gamify focus = self-competition & PRs; depth = modeling first (interleave light engagement wins). See separate approved plan.md in session for details. Update limitations + interpret notes aggressively.

### Theme 2: Exercise & Regional Breadth (Natural continuation of last expansion)
- Complete Front Squat (dedicated ref tables, builder, geometric proxy or better).
- Add 3-5 high-value next: Bent-Over Row / Pendlay Row, Good Mornings, Hip Thrust, Lunges (unilateral for asymmetry), perhaps Lat Pulldown or Overhead Squat variation.
- More regions per existing lifts (e.g. full traps/delts for OHP/rows, adductors, soleus).
- Simple extensibility: JSON or Python API for users to add custom lift + MA functions without core changes.
- **Effort/Impact**: Medium-High / High (users explicitly asked for more exercises recently).
- **Alignment**: Fits "primary compounds + regional" while growing usefulness.
- **Grok Build feedback opportunities**: Scaling reference data addition responsibly (research + conservative synth, avoid hallucination), how to keep tests/docs in sync during breadth adds.
- **Risks**: Dilution if not careful; reference data quality for new ones will be prototype-grade initially.
- **Suggested first MVP**: Front Squat full support + one pulling exercise (Row) + extensibility stub.

### Theme 3: Advanced Programs, Analysis & Insights
- True multi-dimensional sensitivity (grids/ND, not just sequential) + native viz (heatmaps, integrated in GUI using matplotlib/pyqtgraph).
- Fatigue/cumulative + recovery models (build directly on existing accumulate_* helpers; simple exponential or session-based).
- Longitudinal + imbalance: trend plots from saved runs, quad:ham ratio detection, "your X changed Y% since last block".
- GUI "scenario manager": save/compare multiple what-ifs side-by-side with visual deltas + combined interpret.
- Enhanced non-prescriptive notes (contextual from aggregates + user history).
- **Effort/Impact**: Medium / Very High (builds on mature persistence/service; immediately useful for coaches).
- **Alignment**: Turns the tool from "single analysis" into "training intelligence".
- **Grok Build feedback opportunities**: Complex feature addition on existing base (state in GUI, viz libs), how we handle "advanced but still honest" outputs.
- **Risks**: Can feel like "prescription" if notes not careful.
- **Suggested first MVP**: 2D sensitivity grids + heatmap in Sensitivity tab + one fatigue accumulator example.

### Theme 4: Production Polish, Distribution & Ecosystem (Removes real adoption friction)
- **macOS .app + DMG + icon delivered in v2.0** (see GAMEPLANS v2 gameplan + the approved plan.md): robust build script with .icns generation (sips+iconutil), full briefcase create/build/package (DMG), ad-hoc codesign, dist/ artifacts, GUI identity polish for clean "FiberForce" app name/title, all docs updated so double-clicking the icon (after DMG drag to /Applications) is the primary end-user GUI path. ~2GB self-contained .app accepted; full notarization documented (not executed in v2 wave). Post-delivery polish (user feedback): tasteful branding via titlebar icon + About dialog hero (no more large static top image wasting 1/3 of form space) — research-backed (macOS apps, fitness tools); updated in same volume + rebuild cycle.
- Cross-platform: Windows .exe/installer, basic Linux appimage/flatpak via briefcase or similar. (Deferred to post-v2.)
- Publish to PyPI (lib + extras; clean for 1.1+). (Deferred.)
- Richer exports: PDF reports (tables + images + full interpret, using reportlab or similar), one-click shareable config JSON. (Deferred.)
- Lightweight web/local demo (Streamlit/Gradio wrapper over recipes/service for quick what-ifs, no install for sharing). (Deferred.)
- In-GUI measurement aids: better wizards, diagrams, "photo reference" notes (no real computer vision yet). (Deferred.)
- **Effort/Impact**: High (packaging fiddly on mac) / High (unsigned bundle was a real barrier; v2 makes the icon-click vision real).
- **Alignment**: Makes the GUI "the app you can give to a coach" (direct from original user request + "openable with click of an icon" for v2).
- **Grok Build feedback opportunities**: Deployment/packaging (user envs, briefcase package dmg, icon pipeline, long native builds, dual dev vs bundled launch path maintenance), signing story.
- **Risks**: Platform specifics, dependency bloat (PySide6), legal for full signing.
- **v2.0 status**: Mac .app hardening + DMG + .icns + ad-hoc sign + docs + GUI identity = **delivered**. Remaining Theme 4 items (crossplat, PyPI, web, PDF) stay on the roadmap for 2.x.

(Also see GAMEPLANS.md v2.0 section and the dedicated v2 plan.md for the exact execution todos and verification.)

### Theme 5: GUI/UX Delight, Visualization & Onboarding
- Live visualizer: 2D stick figure (or simple 3D via matplotlib/pyvista) of current pose that updates with sliders/loads, color-codes active muscles by demand/MA.
- Live sensitivity heatmap in GUI (no external code needed).
- History superpowers: filter by lift/variation/date/tags, trend lines (torque per region over saved runs), visual side-by-side compare of 2+ saved runs.
- Onboarding: first-launch measurement wizard with diagrams/photos, "load example athlete" gallery (synthetic but realistic with notes), inline tooltips linking to limitations.
  - **Delivered (this UX wave)**: custom animated QStacked QDialog wizard (name + measurements pages, fade transitions via QPropertyAnimation + opacity effect, example load, finish creates+persists+seeds live preview). Live interactive single-form (default ON) + visual primary result cards (count-up + custom dominance bars) replacing "boring box" as main return. Text details collapsed. All per user explicit request + Theme 5. Brutal honesty + no new deps preserved. See CHANGES + LIMITATIONS for details + limits. Re-runnable from Help.
- Polish: consistent theming, better error UX, keyboard/accessibility, export previews.
- Selection spot delight (delivered): replaced clumped QCombo dropdowns for variation/target (single + multi-pos) with spacious full-width visual chip bars (human labels + muscle color dots, always-visible tappable, no popup list). Chips primary (original combos hidden), drive live cards on tap, full 8 lifts, consistent across analysis tabs. Ties directly to "interactive form" + visual cards + future logger "contextual ... using the interactive style". See CHANGES + plan for details + rebuild verif.
- **Effort/Impact**: Medium-High / High (history shows "increasing the visuals... top tier" was a big win; users love seeing the model).
- **Alignment**: "GUI that lets me do everything and display those" (direct from original GUI request).
- **Grok Build feedback opportunities**: Iterative Qt + viz embedding (new libs?), state management for live updates, user research via examples.
- **Risks**: Adding heavy viz deps; keeping it lightweight.
- **Suggested first MVP**: 2D pose visualizer in Single/Multi tab (live with controls) + history filter + one measurement guide panel.

### Theme 7: Full Workout Tracking + Modeled Force Overlay (furthest end-goal vision)
User explicit (after the interactive UI + log cleanup waves): "ideally you could track your workouts here and you could also see all the useful data for force and you could see 1rm, 5rm, volume, top set volume, etc all of the data you would need. this would theoreticall apply to every muscle and veery exercise, but perhaps you could say only exercises with dumbbelsl, barbells. and machines first"

- Core idea: the modeling (regional peak torque demand, dominance %, L-T/F-V notes, geometric personalization) is the unique value. Layer it on top of real logged training data so users see "I did 225x5 bench today → that set demanded ~180 ft-lb peak on my sternal pecs at 57% dominance (with my proportions and flat grip); my weekly modeled sternal work is up 12%".
- Real training metrics always captured: volume (weight × reps × sets), e1RM/5RM from working sets (Epley etc.), top-set volume, RPE, notes.
- Modeled overlay only for exercises that map to our current (or expanded) lifts: start deep/quality on the main compounds (the 8 we model well + common db/machine equivalents like db bench, machine chest press as proxies). Unmapped exercises still get full real logging + volume/1RM with a clear "modeled force not yet available" note.
- Data model foundation (added in this wave):
  - EXERCISE_MAP for the initial 10-12 bb/db/machine exercises.
  - LoggedSet (performed weight/reps + attached full list of MuscleForceResult from the analyze call, plus convenience scalars: set_volume_lbs, modeled_work_ftlb = peak_torque × reps, dominance).
  - LoggedWorkout (date, name, list of LoggedSet, athlete link).
  - create_logged_set(athlete, exercise_key, weight_lbs, reps, ...) that resolves the map, runs the model, attaches everything.
  - estimate_one_rep_max, real_volume, modeled_total_work, get_regional_modeled_summary (reuses existing accumulate_regional_* on the attached results), get_exercise_summary (with e1RM per exercise).
  - Persistence (save_logged_workout / load / list) using the same JSON machinery as Saved*Run + profiles.
- Derived value: per-muscle "demand" over time (because every supported exercise contributes to multiple regions via the multi-mover models we built), trends that combine real volume with modeled force-volume, PRs on both real and modeled numbers, imbalance signals, "what did this block actually ask of my chest vs triceps".
- UI (future): "Log Workout" flow (fast, template from previous, contextual dropdowns using the interactive style), dashboard views (weekly muscle load bars mixing real + modeled, 1RM history per exercise, top sets), link from a logged workout back to "re-analyze this exact set with different variation or updated measurements".
- Integration: Logged workouts can feed or be converted into TrainingSession/WeeklyProgram for the existing regional stress/volume reports. History tab evolves to show both "modeled analysis runs" and "real logged workouts".
- Phased (user-prioritized first slice): basic logger for the 8-10 main compounds + common db/machine proxies, attach modeled force per set, real volume + modeled work + e1RM from working sets + support for explicit 1RM tests/AMRAP, persisted, visible in the app (smoke now demos a full "Smoke Push Day" with numbers in the Activity Log dialog).
- Honest limits (always surfaced): modeled peaks are static per-position estimates (even with dynrom); no true fatigue/velocity/inertia in real reps yet; % is mechanical MA share; "every muscle" is only as good as the exercises we have full multi-mover tables for; user still has to enter the real data (make it fast with templates, autofill previous workout, the interactive dropdowns we already have).

**User choices captured in this wave** (via ask_user_question):
- First narrow slice: the basic session logger for common bb/db/machine exercises with real sets + attached modeled force + volume/modeled-work + e1RM.
- Deep quality on main compounds first (volume-only + note for others).
- Both working-set e1RM estimates + explicit max test / AMRAP support with special treatment in trends/PRs.

- **Effort/Impact**: High / Very High (turns the analyzer into the thing serious lifters actually use every day).
- **Alignment**: Directly fulfills the original "I want to go as deep as we can" + "not just a form style or boring app" + self-competition on real + modeled outputs.
- **Grok Build feedback opportunities**: Complex data modeling over time, UI for fast data entry without fatigue, longitudinal viz, bridging "analysis mode" and "logging mode" in one app.
- **Risks**: Scope creep ("every exercise"), data entry UX being the make-or-break, users over-trusting the modeled numbers as "what I should feel".
- **Suggested MVP for next slice**: the Logged* dataclasses + create_logged_set + persistence + demo inside smoke (already done) + minimal "Quick Log a Set" in the Recipes tab that lets you pick an exercise, enter weight/reps, see the attached force cards + volume numbers, save it. Then full "Log Workout" tab in a follow-on wave. Always rebuild + test only via the one-click app.

(Continue to integrate with Theme 3 longitudinal + Theme 5 history superpowers.)

### Theme 6: Validation, Education, Extensibility & Quality
- Validation harness: scripts + tests that diff outputs vs published studies/typical EMG/force data for canonical conditions; "reproducibility report".
- Education: in-GUI model explainer (per-result assumptions + notes surfaced nicely), glossary, "accurate measurement" interactive guide.
- Extensibility: clean public API + docs for adding custom MA estimators or regions (plugins via entry points or simple subclass).
- Quality bar: strict mypy, property-based tests (hypothesis for anthro/position edges), higher coverage, CI notes.
- Docs evolution: auto API (pdoc), living "how the model works" updates, case study examples.
- **Effort/Impact**: Medium / Medium-High (builds trust for "serious lifters").
- **Alignment**: Supports the "honest prototype" promise.
- **Grok Build feedback opportunities**: Research + validation workflows, documentation generation, testing strategies for scientific code.
- **Risks**: Data access (public studies), over-promising on "validation".
- **Suggested first MVP**: Validation script for 2-3 key conditions + inline assumption display in GUI results + one custom estimator example in docs.

**Cross-cutting concerns** (apply to any theme):
- Performance: numpy/pandas for sweeps/grids, caching of reference, parallel execution for expensive multi.
- Maintain imperial primacy + clean metric support.
- Keep dual tracking: every wave updates AGENT_FEEDBACK (planning, iteration, tool use observations for "evolving mature app").
- Use Grok Build: Plan Mode for any big design (e.g. dynamic model), subagents (researcher for papers, reviewer for PRs on new math), todo_write, background for builds/tests, image_gen for new assets.
- Verif always: cd to volume + PYTHONPATH or venv, pytest + smoke (new + old lifts) + examples + GUI import + manual imperial ft-lb cases + packaging test.

## Risks (Overall)
- Scope creep (v1 was deliberately narrow for a reason).
- Model accuracy / user over-trust (new features must carry stronger provenance).
- Packaging/distribution complexity on mac (and cross-platform).
- GUI bloat (PySide6 + new viz libs).
- Agent: balancing "talk/plan" vs shipping value; long waves on research-heavy themes.

Mitigations: User-driven prioritization, small MVPs per wave, aggressive honesty in docs/output/limitations, scoped "in/out" per theme.

## Suggested Order / Waves (flexible)
1. Quick wins from recent momentum: Theme 2 MVP (Front Squat + 1 row) + Theme 5 MVP (pose visualizer + history polish) — builds directly on exercise expansion, high user-visible delight.
2. Or Theme 4 (app polish + PyPI) if distribution friction is blocking real use.
3. Then Theme 1 (dynamics/geometric depth) or Theme 3 (advanced sensitivity/fatigue) for core modeling leap.
4. Theme 6 as ongoing quality/education thread.

## How This Continues the Hybrid Goal
- Every step (research, design, implementation of a wave) produces specific, tied-to-moments observations in AGENT_FEEDBACK (e.g. "subagent for paper research on MA data was X effective", "friction re-adding geometric for new lift was Y", "planning for post-v1 vs initial build differed in Z ways").
- Dual artifacts: code/docs advance + rich log.
- Process discipline preserved (todos, live verif from canonical workspace, no regressions, edit plan before exit if needed).

## Immediate Next (after this doc)
- User discussion/prioritization (which themes? constraints? start with breadth or depth or polish?).
- Pick 1-2 for first wave.
- Seed detailed todo list (merge:false) + begin (audit specific area, research if needed, implement with verif + feedback entry after each batch).
- Update GAMEPLANS.md to reference this roadmap.
- This doc lives in project root and can be updated as we learn.

**External Inspiration (from quick 2026 web_search during planning)**:
- Tools like OpenCap (Stanford, smartphone video + ML + musculoskeletal sim for joint loads/muscle activation — democratizes what used to be $150k lab work). Opportunity: future "import video pose" or compare mode?
- Weightlifting biomech research (lectures by Kristof Kipp on bar path, forces, power in Olympic lifts).
- General biomech ecosystem: motion capture (Vicon etc.), force plates, EMG, simulation software, low-cost apps (MyJump for jump metrics, 3D SSPP for ergonomics/lift analysis).
- Papers/interest: incline bench angle effects on clavicular activation, variations of big 3 (incline, pause squats, RDLs/stiff-legs popular), manual lifting risk models.
- Weightlifting apps (Shred, Boostcamp, etc.): mostly programming/logging + tutorials; very few do *internal force modeling*. FiberForce's niche (personalized regional peak torque) remains unique and defensible.
- Implication for roadmap: Theme 1 (validation against such tools/studies) and Theme 5 (video input ideas) have external momentum. Avoid competing on logging; double down on modeling + personalization.

This search was lightweight (to enrich, not block); full researcher subagent could dig deeper (specific papers on RDL MA, competitor feature matrices) if a theme is chosen.

**User Prioritization (from planning session discussion)**:
- Top theme: **1. Modeling & Scientific Depth**
- Preference: **Prefer depth (modeling first)**
- Specific first focus area: **Full dynamics / ROM curves**
- No other constraints or input at this time.

**Decision for next wave**: Start with Theme 1 MVP centered on continuous dynamic ROM simulation (for at least 1-2 lifts, e.g. squat + bench to start), including angle interpolation, basic MA curves over ROM, updates to builders/service/GUI (live slider or multi-pos becomes continuous), and strong updates to limitations + docs. Use proxies where full geometric isn't ready. This directly addresses the #1 honest limitation ("static positions only").

Subsequent waves can layer advanced muscle models (length-tension/velocity), expanded geometric, validation comparisons, etc.

This choice keeps momentum from the recent exercise expansion while going deep on the scientific core.

**Implementation start (in same session)**: Audit of discrete handling completed (discrete pos strings -> table keys or geometric(pos=...), hard-coded angles per pos in builders e.g. knee~35deg squat bottom, MultiPositionResult as list of snapshots + aggregates/interpret, GUI uses comma pos lists or fixed, ReferenceData exact key lookup). Design MVP: linear interp helper on existing tables (for load/muscle MA dicts) + param-by-primary-angle generation of snapshots; reuse MultiPositionResult for compatibility (add metadata); geometric trig models already angle-capable so can drive continuous; still per-snapshot peak (no true vel/inertia yet). First code: added _interpolate_value + get_*_continuous to ReferenceData (tested, sample interp works, no breakage to discrete paths); continuous builders (squat knee-driven + bench) in examples.py; service build_continuous_positions + analyze_continuous; recipes.analyze_continuous wrapper; CLI smoke demo; test added + passes; smoke/service tests green. Docs (limitations, README, roadmap, GAMEPLANS) updated. MVP for full dynamics/ROM curves complete as first slice of Theme 1 (core working, reusable, imperial/ft-lb/interpret all preserved). Remaining (GUI tab, more interp in geo, full tests) follow-on per dynrom todos.

**This is a living proposal, not a contract.** The goal is useful evolution that feels like a real "next level" for the app while generating excellent data on Grok Build for long-term project stewardship.

See the approved planning session plan.md (in .grok session) for full context, open questions, and process details.

**Post polish keep-going update**: mpr.positions now use angle labels (knee=xx°) from cont builders for better display in interpret/GUI/table. Small but nice. Wave enhanced. All complete, keep going done for this slice.

---

### 2026 "New Level" Direction (post v2.0 branding + "not just a form style or boring app")
User request: "Lets talk about a new level, im thinking making this not just a form style or boring app, but a bit more depth and gamify."

**User clarifications (via ask_user_question during plan mode)**:
- Gamify flavor: Self-competition & PRs (personal records, trends like "+X% modeled glute torque vs prior best", visual progress in history, history highlights). Strava-like for your own modeled regional torque demand / ROM variation / geo personalization. Not cartoon XP/levels or external leaderboards.
- Depth priority: Depth first (modeling) — continue Theme 1 (L-T/F-V, fuller dynamics, geo) ; layer gamification as engagement on the (current + richer) numbers. Interleave light wins so the app feels more "alive" sooner without delaying core science.

**Adopted approach (from approved plan.md)**: Interleaved wave — one focused Theme 1 depth slice (e.g. length-tension over continuous ROM or expanded continuous geo + MA curve in dynrom) + self-competition layer on top of existing rich data (SavedMultiPositionRun ft-lb + timestamps + variation_coeff + geo flags + MPR aggregates + accumulators + WeeklyProgram.compare). 

Concrete deliverables (first wave):
- Depth: richer per-angle modeled demand (still peak per snapshot, honest notes).
- Gamify: History tab upgraded to "Progress & Personal Records" (PRs as max modeled ft-lb per region/lift/pos across persisted runs, sparklines, deltas vs best/avg, milestones like "ROM Explorer"). Post-run progress moments appended to .interpret() outputs (e.g. "New personal modeled peak..."). Subtle highlights only (no popups, no fake scores). All text reuses exact existing honest framing from interpret/reports/limitations.
- Light visual support: muscle map / bars reflect run or PR; delta indicators on ft-lb values.
- Process: update this roadmap (this subsection), GAMEPLANS new wave, dense AGENT_FEEDBACK (plan mode + subagent explore + ask + serious gamif research from Strava/Hevy patterns), CHANGES, verifs on volume (smoke + manual PR trigger + history check), no regressions.

**Why this feels like "new level"**: Escapes pure "form → run → read text" while staying true to the physics-accurate, brutally honest prototype identity. The numbers being PR'd/trended *are* the model outputs (ft-lb regional peaks, consistency via variation, personalization via geo). Depth makes future PRs more meaningful.

See the approved session plan.md for full context, multiple approaches considered (data-only vs interleaved vs big UI first), risks (honesty paramount), success criteria, and detailed execution phases.

This iteration of the living roadmap records the direction. Implementation follows the standard discipline (todo_write merge:false, one in_progress, live volume verifs after edits, etc.).

---

*Generated as first concrete output of the approved "next level" planning session. Will be iterated with user input.*