# FiberForce

**Personal Musculoskeletal Force Modeler** for advanced, anatomy-driven resistance training.

## Project Direction (v1.0)

FiberForce 1.0 is a practical tool for serious lifters and coaches:

A tool that allows users to create a personalized biomechanical model of their body and analyze **peak force/torque demands** on specific muscle sub-regions during primary compound lifts at chosen positions, with full support for US customary units (inches, ft, lbs) and outputs in ft-lb torque.

Key characteristics:
- Users provide detailed personal measurements (default imperial: inches, lbs)
- Focus on **regional hypertrophy** (targeting specific muscle fibers/sub-regions)
- Calculates mechanical torque/force requirements using lever arms and moment arms (ft-lb primary)
- Scoped to **peak force/torque** at discrete static positions + limited multi-position + **basic continuous ROM** (post-v1 dynrom MVP via analyze_continuous / recipes; interp on angles/MA, reuses rich MultiPositionResult)
- Primary lifts (expanded post-v1): Bench Press + Incline Bench, Back Squat (high/low), Deadlift (conventional + sumo + RDL), OHP (rich variants)
- Full native GUI for visual exploration, plus library + CLI
- Recipes for common workflows, rich .interpret() insights, geometric personalization, persistence

This is a **hybrid project**: We are building real, high-quality software while deliberately generating detailed feedback on Grok Build's capabilities as a software engineering agent. See AGENT_FEEDBACK.md for the full journey.

**v2.0 Status (The Clickable Icon App)**: Full imperial (inches/ft/lbs + ft-lb torque) default + dynrom/continuous ROM, 8 lifts, top-tier native GUI (now *exclusively launched by double-clicking the icon* from a freshly built DMG + self-contained .app with custom .icns). 

**PERMANENT TESTING POLICY**: The user ONLY tests the GUI by double-clicking the real one-click .app (drag DMG to /Applications or open dist/*.app directly). The agent must ALWAYS run the full rebuild (`bash scripts/build_macos_app.sh` after the venv/pip -e block) after any GUI/src change before claiming a feature is "testable". Dev commands (`python -m fiberforce.gui` etc.) are for internal agent smoke/verification only — never presented as the user experience. This policy was explicitly set because of repeated "I don't see the change" issues with stale bundles in prior waves.

Real macOS .app/DMG artifacts (always fresh after changes), 170+ tests, 12 examples, smoke "PASSED". See GAMEPLANS, NEXT_LEVEL_ROADMAP (Theme 4), AGENT_FEEDBACK, and the top of src/fiberforce/gui/app.py for the full launch + rebuild instructions.

## Current Scope (v1.0 Polished / Release Execution)

Major capabilities delivered (pushing to v1):

- **AnalysisService** — the single source of truth: analyze, multi-position (rich MultiPositionResult with .interpret()), sensitivity (single + multi-var + .insight()), builders with geometric, program-level (TrainingSession/WeeklyProgram with .interpret() + compare + reports), persistence.
- **Imperial / US units first** (v1): measurements in inches/ft/lbs by default (via from_inches, load_lbs, units="imperial" in service/recipes/CLI/GUI). Internal always metric for precision.
- **Torque outputs in ft-lbs**: peak_torque_ftlb on results (converted from Nm), reports and displays prefer ft-lb torque demand proxies, individual results carry exact joint torque.
- **Premium GUI desktop app** (double-click icon from DMG or `fiberforce gui`): full native PySide6 Mac app with modern dark scientific-fitness theme (inspired by Strong/Hevy/Strava: clean data viz, high-contrast cyan/green accents, cards, premium plots), tabs for Athlete (inches + visuals), Single/Multi-Pos (continuous ROM torque curves + muscle activation map preview), Sensitivity (styled plots + insight), Programs (.interpret() + report), Quick Recipes, History/Export with trends. Exercises everything. Updated splash/icons, styled matplotlib curves, regional muscle visuals. **Branding polish**: no large static top image (per real app patterns — titlebar icon + Help > About dialog hosts hero + science blurb); tabs/fields/plots dominate vertical space. **New Level (depth + gamify + ease)**: History is now "Progress & Personal Records" (self-competition PRs/trends on your modeled ft-lb regional peaks + milestones, using the real persisted MPR data); post-run ★ "new personal modeled peak" moments appended to .interpret() outputs; start of richer angle-varying L-T demand in continuous dynrom for future PRs. **Dropdowns**: variation, positions (preset editable), target region are now auto-populated contextual QComboBox based on chosen lift (no more free-text typos for "low_bar" or "Gluteus Maximus::Upper fibers" — pick lift, the rest just works with sensible defaults). All honest "modeled estimates". See CHANGES + roadmap.
- **Recipes module**: high-level conveniences for common flows (default imperial).
- **Geometric + full 4-lift parity** — position-aware (bottom/mid/top/lockout) geometric MA for bench/squat/deadlift/ohp. Builders, service, CLI, GUI, recipes all support use_geometric + anthro.
- **Visualization + persistence** — matplotlib + excellent ASCII fallback; full Saved*Run + profile system; CLI symmetry.
- **Extensive testing + verification** — 200+ tests, full example matrix, CLI smokes, GUI import/launch checks. `fiberforce smoke` for quick core verify.
- Rich .interpret() / .insight() on results for human coaching insights (no prescription).
- Polished Typer CLI with `fiberforce gui`, smoke, full commands, imperial flags.
- Confidence, notes, provenance on every result.

**Honest note (v1)**: Still a scoped prototype (peak force at discrete positions, single-joint approx, geometric is directional prototype, no full dynamics/fatigue/etc.). But now with US units and torque ft-lbs as primary for accessibility. See `docs/limitations-deep-dive.md`.

See `DESIGN.md`, `SCOPE_OF_WORK.md`, `GAMEPLANS.md`, updated `docs/`, examples/, and the GUI for vision and usage.

## Quick Start

```bash
python -m pip install -e ".[viz]"
fiberforce --help
fiberforce demo                  # classic synthetic bench example
fiberforce list-lifts
fiberforce list-regions
```

**Library quickstart (recommended — v1 imperial recipes first)**:

```python
# Easiest v1 path (inches, lbs, ft-lb outputs, geometric where supported)
from fiberforce.recipes import create_athlete, analyze, analyze_multi_position

ath = create_athlete(
    name="You",
    units="imperial",
    femur_in=17.0, tibia_in=15.0, humerus_in=13.4,
    biacromial_in=15.7, torso_depth_in=9.4,
)
print("Athlete ready (geometric enabled)")

# Single analysis — ft-lb torque by default
res = analyze("deadlift", load_lbs=385, variation="sumo", athlete=ath, units="imperial")
print(res.results[0])  # shows ft-lb via __str__

# Multi-pos with rich .interpret() (coaching notes, geometric provenance)
mpr = analyze_multi_position("squat", ["bottom", "mid"], load_lbs=315, athlete=ath,
                             variation="low_bar", use_geometric=True, units="imperial")
print(mpr.interpret())
```

**Lower-level service (still fully supported, uses cm internally):**

```python
from fiberforce import AnalysisService
from fiberforce.profiles import save_anthropometry

service = AnalysisService()
print(service.describe())

# Create and persist your measurements (rich = geometric-ready)
subj = service.create_subject_from_measurements(
    name="You",
    humerus_length_cm=33.5,
    femur_length_cm=43.0,
    tibia_length_cm=38.0,
    biacromial_width_cm=40.5,
    torso_depth_at_chest_cm=23.0,
)
save_anthropometry(subj.anthropometry, "my-body")

# Deadlift analysis in one line
pos = service.build_position("deadlift", load_kg=175, variation="sumo", target_region_name="Upper fibers")
result = service.analyze(subj, pos)
print(result.results[0])

# Geometric-enabled bench (latest convenient path)
pos_b = service.build_position("bench", 105, grip_width_cm=58, use_geometric=True,
                               humerus_cm=33.5, biacromial_cm=40.5)
print(service.analyze(subj, pos_b).results[0])
```

**CLI quickstarts**:
- `fiberforce analyze deadlift -l 180 -v conventional --target "Lumbar"`
- `fiberforce sensitivity squat --variable load_kg --start 120 --end 180 --step 10 --plot`
- `fiberforce compare deadlift --a conventional --b sumo --load-kg 180 --plot`
- `fiberforce profile save me --femur 44 --tibia 39 --humerus 34 --biacromial 40.5`
- `fiberforce profile multi-sens me --lift bench --variables "load_kg:100,120" "grip_width_cm:48,58,68"`

Full quickstarts, recipes, and advanced patterns live in the documentation and the nine runnable examples.

## Documentation

- **[Usage Guide](docs/usage-guide.md)** — practical workflows, CLI + library examples, deadlift, OHP, visualization, profiles + the complete enhanced persistence layer, quickstarts
- **[How the Model Works](docs/how-the-model-works.md)** — core concepts, data flow, architecture, calculation details, geometric + multi-var + persistence, quickstart code
- **[Advanced Patterns](docs/advanced-patterns.md)** — real-world AnalysisService usage, custom sensitivity with rebuild callables (including geometric), combining multiple lifts, **the full Saved*Run persistence layer with code recipes**, project patterns
- **[Limitations Deep Dive](docs/limitations-deep-dive.md)** — exhaustive assumptions, the unit bug, current vs future scope (geometric prototype limits, sequential multi-var, persistence boundaries), precise "when not to use" guidance

Start with the Usage Guide, then read the Limitations Deep Dive for honesty, then Advanced Patterns for power-user workflows. The nine advanced examples in `examples/` are the best concrete, runnable reference.

## The Nine Advanced Examples (runnable)

Located in `examples/` with full reports in `examples/outputs/`. All use `AnalysisService` as the primary API, include heavy commentary, honest Limitations sections, and write dated reports.

Highlights of the latest (08 & 09):
- **08** — Complete profile + enhanced persistence workflows (every `Saved*Run`, `run_profile_*` helper, `save_current_analysis`, discovery, bundling, geometric multi-var inside persisted runs via the modern builder path).
- **09** — Flagship combined geometric + multi-var (static vs live geometric parallel surfaces on the same profile, direct + builder geometric patterns, full persistence of sensitivity runs, post-hoc loading for comparison).

See `examples/README.md` for the full catalog and "How to Run".

## Tech Stack

- Python 3.9+
- Typer (CLI) + Rich
- Matplotlib (optional, for visualization)
- Clean modular library design in `src/fiberforce/`

## Development & Testing the Current Version (v1 — Bulletproofed)

**CRITICAL: Follow this exact sequence. Past runs hit "command not found: fiberforce", "Directory cannot be installed in editable mode: /Users/Server", PATH warnings, and GUI splash crashes because pip/launch was run from ~ or without venv or without cd first.**

**The ONLY supported dev workspace for this project (and the one with all history, assets, outputs):**
`/Volumes/Maximus/Maximus Prime/Workspace-Grok_Build/projects/fiberforce`

### One-Time Setup (copy-paste this block)
```bash
# 0. cd FIRST — always. Never run pip or python -m fiberforce from anywhere else (especially not ~).
cd "/Volumes/Maximus/Maximus Prime/Workspace-Grok_Build/projects/fiberforce"

# 1. Create isolated venv (prevents polluting system python and PATH hell)
python3 -m venv .venv
source .venv/bin/activate

# 2. Upgrade pip + install editable with GUI (PySide6) + viz (matplotlib for plots + embedded GUI charts)
python -m pip install --upgrade pip
python -m pip install -e ".[gui,viz]"

# 3. Verify the entrypoint is now on this venv's PATH
fiberforce --version
# Expected: FiberForce version 1.0.0 (or 1.0.0-dev during polish)
```

### Quick Verification Matrix (after the setup block above)
```bash
# Smoke (exercises recipes, imperial, ft-lb torque, dynrom/continuous, 8 lifts, WeeklyProgram, Sensitivity.insight, interpret — the core)
fiberforce smoke

# v2.0 PRIMARY GUI: build the clickable .app once, then double-click the icon (see Packaging section below for the one-command DMG + .app).
# Dev / fast iteration (still excellent):
fiberforce gui
# Fallback (uses __main__.py, recommended during active dev or if PATH issues):
python -m fiberforce.gui

# Core CLI
fiberforce --help
fiberforce list-lifts
fiberforce list-regions

# Full test suite (~204 focused tests, geometric heavy)
python -m pytest -q

# Flagship coaching examples (imperial + ft-lb + geometric + interpret in 10/11)
python examples/01_program_level_insights.py
python examples/10_coaching_scenario_squat_variation.py
python examples/11_sensitivity_driven_grip_decision.py
```

All examples write to `examples/outputs/` and must exit 0. The smoke + GUI smoke are the fastest "is my install healthy?" checks.

See `examples/README.md` for the full catalog and what each demonstrates (many now use `recipes.create_athlete(..., units="imperial", femur_in=...)` + `load_lbs` + display ft-lb).

For contribution / repeated work:
- Always `cd` to the volume path above first.
- `source .venv/bin/activate` (or reactivate) before any pip/python -m fiberforce.
- `python -m pytest tests/ -q --tb=short`
- `ruff check src tests`
- Keep the full example suite + 200+ test matrix + smoke green on every change.

The project uses `pyproject.toml` with hatchling; `pip install -e ".[gui,viz]"` (or [dev,viz,test]) from the **correct cd'ed dir with venv active** is the supported path. The venv bin must be first on PATH (activate does this).

**If you ever see "fiberforce: command not found" after pip: you skipped cd, skipped venv, or did not `source .venv/bin/activate`. Start over from the block above.**

### Packaging / Building the Clickable macOS App (THE ONLY way the user tests the GUI)
**CRITICAL (user policy)**: The user ONLY interacts with / tests the app by double-clicking the icon in the built .app (after drag from DMG to /Applications). The agent is REQUIRED to ALWAYS execute the full rebuild sequence below after every GUI-relevant change (especially anything in src/fiberforce/gui/app.py) before saying "you can test it". Stale bundles from previous builds will not contain the latest interactive features (onboarding wizard, live animated visual cards, etc.).

**Primary experience**: Run the build (see command), open the produced DMG, drag FiberForce to /Applications (overwrite previous), then double-click the icon in Finder/Launchpad/Dock/Spotlight. This is the complete end-user flow. No terminal required for the user after the (one-time per change) build.

The build uses Briefcase (which already produced a working bundle in v1). v2 polishes it into the supported "click the icon" path:

- Robust icon pipeline: committed `app_icon.icns` (generated from the 1024x1024 jpg via sips + iconutil) + the jpg (still used at runtime for splash/QIcon inside the app).
- Full pipeline: `briefcase create` → `build` → `package` (the package step produces the DMG).
- Post-steps: ad-hoc codesign (so double-click "just works" on the build Mac without right-click Gatekeeper), stage to `dist/FiberForce-2.0.dmg` + `dist/FiberForce.app`.
- Excellent output + troubleshooting (including notes for full Apple notarization if you want to distribute publicly).

**One-time build (after the standard volume venv block):**

```bash
bash scripts/build_macos_app.sh
```

Then:

```bash
open dist/FiberForce-2.0.dmg
# Drag FiberForce.app to /Applications (overwrite any older version)
# Double-click the icon in /Applications (Finder / Launchpad / Spotlight / Dock)
```

**This double-click is the ONLY testing method used by the user.** Per explicit policy: after any GUI change the agent must re-run the full build sequence above before the feature can be considered "testable by the user".

After a clean first launch (or after clearing the per-user state in ~/Library/Preferences/*fiberforce* and ~/.fiberforce/profiles), you will immediately see the new interactive first-run experience: a custom animated multi-page wizard that asks "who are you" (name) then for your key measurements (inches). It creates a real persisted profile, seeds the Athlete tab, and jumps you into Single Analysis with a live visual preview already populated.

In Single Analysis you test the "not boring box" + "form feels interactive" changes:
- The main result area is now visual-primary cards (big count-up ft-lb number + per-muscle custom rounded dominance bars that animate on change + efficiency).
- The old detailed text report is collapsed by default (toggle to expand if you want the full .interpret() + lit notes).
- Changing the lift, variation (e.g. flat vs flat_close/wide), target, or load spinbox triggers a debounced live re-calc; the visual cards update with smooth count-up and bar-fill animations. This is the "when you interact with the different elements of the form" experience.
- Explicit "Run Analysis" still works for committing to history/PRs and expanding the full text.

**What you get**:
- A self-contained .app ( ~2 GB because it embeds PySide6 + Python — the price of true no-python-required native app).
- Custom icon visible in Finder/Dock/Launchpad.
- All v2.0 / v1 capabilities (dynrom/continuous ROM is fully there).
- Devs can keep using `fiberforce gui` / `python -m fiberforce.gui` (or `run_gui_prototype.sh`) for fast edit/launch cycles during development. The .app is the "ship it / share it" artifact.

See the completely rewritten `scripts/build_macos_app.sh` (now ~180 lines of clear v2 docs + logic) for the exact commands, icon generation function, dist handling, ad-hoc sign, hdiutil fallback, and "how to do full notarization for public distribution" instructions.

See also `[tool.briefcase]` in `pyproject.toml` (version + icon + descriptions updated for v2) and `src/fiberforce/gui/assets/` (jpg + icns).

**Size & signing notes**:
- Large because self-contained. This is intentional and accepted for v2 "click the icon" UX.
- Ad-hoc sign (done by the script) is enough for your machine + people you trust. For App Store or wide distribution without warnings you will need an Apple Developer ID cert + `notarytool` (the script + README document the steps; Entitlements.plist is handled by briefcase).

This finally makes the original vision ("an app that launches on the mac here... be able to display those") a double-click reality.

## Dual Purpose

1. **Software**: Build something genuinely useful for serious lifters who care about the science of training.
2. **Feedback**: Generate high-signal observations about Grok Build to help improve the system.

See `AGENT_FEEDBACK.md` for ongoing observations and process insights from the massive phase and subsequent wiring/persistence work.

---

*FiberForce is deliberately transparent and scoped. Use it for relative comparisons and hypothesis generation while respecting its current limitations.*
