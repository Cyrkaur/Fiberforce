# FiberForce — Changes (v2.0 + prior)

## Selection spot visual upgrade (chips primary) — single + multi-pos analysis tabs: replace clumped long dropdown lists for variation + target with spacious always-visible tappable chips (human labels, muscle color dots, full-width after controls). Directly addresses "longlist and kind of clumped" + "better way ... not so boring and squished". Ties into live visual cards (tap choice -> instant anim bars/numbers).

**User verbatim**: "now lets talk about the selection spot on both the single and double analysis tabs, on the target dropdowns and rthe variation dropdowns somethings that a longlist and kind of clumped. is there a better way to present that information so the user can select what they want in a way that isnt so boring and squished?"

**Before**: QFormLayout rows + QComboBox (editable=False) populated with raw slugs ("flat_close") or long "Pectoralis Major::Sternal fibers". Popup vertical list, technical, squished, no grouping or visual. Live reacted after choice but the selection spot itself was boring dropdown.

**After (per approved plan + user choice "Chip/pill selectors primary" + "Hide or remove the original dropdown rows")**:
- New `SelectionChipBar` (reusable QWidget, QHBox + QButtonGroup exclusive checkable QPushButtons, theme styled rounded + cyan :checked, color ● dot for targets via MUSCLE_COLORS).
- Maps: VARIATION_LABELS (slugs -> "Close Grip"), TARGET_SHORT_LABELS ("Pec::Sternal" -> "Sternal Pec"), MUSCLE_COLORS for instant visual grouping.
- In both _create_analyze_tab and _create_multipos_tab: form keeps only lift/load/geo/positions; after controls group, full-width chips rows with cyan labels ("Variation (tap chip — instantly animates live visual cards below)").
- Backing QComboBox still created but .setVisible(False); chips drive them on tap (setCurrentText) so _live_preview, run_*, smoke sets, .currentText() paths unchanged.
- _populate_contextual_fields now also builds chip choices + set_current (human labels, correct per lift).
- 2-way sync connects (combo change -> chip UI; chip tap -> combo -> live signals).
- Layout: chips are spacious (min 68px buttons, 6px spacing), always visible, no popup list ever for these choices. Original "clumped" rows removed.
- Multi consistent with single (chips before the Run/Continuous buttons; explicit runs use the choice).
- Internal smoke updated to log "✓ ... chips: var/target visual selectors".
- No new deps, preserves 8 lifts, live single, imperial/ft-lb, % dom, PRs, continuous, everything.

**Rebuild + bundle verif (policy)**: full cd/venv/pip-e + scripts/build_macos_app.sh (196s, exit 0). New 2.0.0.dmg (430MB), 2.0.dmg (558MB), dist/FiberForce.app. Grep inside frozen .../gui/app.py found "class SelectionChipBar" + "SelectionChipBar" (multiple) + chip primary strings. User tests ONLY by double-clicking the icon (or drag from DMG).

**Result**: selection spot is now delightful, scannable, interactive surface (tap a "Wide Grip" chip on bench, watch the live dominance bars + ft-lb count-up change instantly to reflect higher pec share). Matches the visual cards + "feels more interactive" direction. Still honest modeled notes in tooltips.

**Follow-up bugfix (user: "when I hit for it to calculate the torque number stays blank, I tried bench and squat")**:
- Explicit Run/Calc in Multi-Position (squat/bench) left the big "lead / peak" torque number in Visual Results Summary as initial "— " (blank). Single sometimes errored in text but card partially updated.
- Root (latent result shape mismatch, surfaced by chips making "calculate" the exercised path on the real .app): run_multipos table did `note = (ap.notes or "")` where ap in mpr.analyses is AnalysisResult (no .notes; the dataclass has .results/.position_description etc.). Exception before _update_mp_visual(mpr) → card never refreshed. Same for continuous table. Single had " 'MuscleRegion' is not iterable" ( "xx" in r.muscle_region or .split when the field is now the dataclass with __str__ "Name — Region", not old "Pec::Sternal" str) inside the per-r loop or res.interpret().
- Fixes: table notes now safe `getattr(ap, "notes", None) or getattr(..., "position_description", "") or ...`. Visual short logic in both _update_*_visual: `mr = getattr(r,"muscle_region",""); short = ... if isinstance(mr,str) else str(mr)[:22]`. Wrapped interpret append in single run (try, non-fatal) so results + card update always happen.
- Another full policy rebuild (new dmgs/app at 16:04). Bundle has the getattr + isinstance fixes. Diags: multi now no Error + peak label populates with number on Run; single bench/squat clean, numbers + bars. Chips + live + explicit all still work end-to-end. The "always only test the built app" + chips change made the bug visible immediately; fixed before any more user testing.

## Post-v2.0 "How the data is returned" UX wave (Theme 5 slice) + PERMANENT "ALWAYS REBUILD" POLICY: custom animated first-run onboarding wizard (name + measurements), live interactive form (default ON), visual-primary result cards with count-up + custom painted dominance bars (animated), text details collapsed by default. "Not just the boring box".

## Post-v2.0 "How the data is returned" UX wave (Theme 5 slice) + PERMANENT "ALWAYS REBUILD" POLICY: custom animated first-run onboarding wizard (name + measurements), live interactive form (default ON), visual-primary result cards with count-up + custom painted dominance bars (animated), text details collapsed by default. "Not just the boring box".

**New permanent policy (user explicit: "always rebuild the app, I only want to test through the app")**:
- The user will *only* test GUI changes by double-clicking the real one-click .app icon (after drag from DMG to /Applications).
- After any src/fiberforce/gui change, the agent *must* run the full rebuild (cd + venv + pip -e + bash scripts/build_macos_app.sh) and only then present the DMG/double-click instructions.
- Dev `python -m fiberforce.gui` is now agent smoke/verif only.
- This policy was codified across app.py docstring, README, build script header, plan.md, etc. immediately upon the directive.
- For this UX wave: a fresh rebuild was launched right after the policy note (full guarded cd+venv+pip-e+build script, background task 019e94a9-06b4-7593-ad5d-36cba3e0871d).
- Build completed successfully (exit 0, ~211s). New artifacts:
  - dist/FiberForce-2.0.0.dmg (431M @ 15:05)
  - dist/FiberForce-2.0.dmg (558M @ 15:06)
  - dist/FiberForce.app (updated 15:05)
- Post-build verification (inside the new frozen bundle):
  - "Live Visual Summary" present
  - "_onboard_animated_switch" present (multiple)
  - "class AnimatedDominanceBar" present
  - "onboarded/v1" present
  - Policy string "always rebuild the app" present in the bundled app.py
- The one-click .app now contains the full interactive first-run wizard + live form → animated visual cards experience. User can now test exclusively via double-click as requested.

## Backend math clarification for per-muscle torque (addresses "same force number for anterior delt and pec on bench")
- Root cause identified via user report + code audit: in `SimplePeakForceCalculator.calculate_peak_force`, for all co-contributors on the *same joint* (e.g. sternal pec + ant delt both on shoulder for bench), `peak_torque_nm` (and thus displayed `peak_torque_ftlb`) was set to the *full external joint torque* for every muscle. Muscle force F = full_torque / MA_m (different per muscle due to different MAs), but the "ft-lb number" shown in GUI/single/multi was the joint torque (identical).
- Fix (MA-proportional torque partitioning): after computing dominance % = MA_i / sum_MA per joint:
  - torque_share_i = (MA_i / sum) * full_external_joint_torque
  - Store in res.peak_torque_nm = share (different per muscle; larger MA gets larger share)
  - Scale the peak_force_newtons consistently: effective F now produces exactly the share torque when multiplied by its MA.
  - Sum of reported per-muscle peak_torques on a joint now equals the joint external torque (no overcounting).
  - Dominance % now directly = % of the (reported) torque credited to that muscle.
  - Notes updated with "Modeled torque contribution/share: XX% of joint (MA-proportional partitioning)".
- Science/math basis (static inverse dynamics):
  - external_joint_torque = load × load_MA (at shoulder or elbow).
  - For a single muscle alone: F_m = torque / MA_m ; muscle_torque = F_m × MA_m = torque.
  - For N co-movers on one joint (real bench has pecs + delt contributing to shoulder torque; tri to elbow): real force sharing is complex (PCSA, activation, optimization). Our simple transparent model uses relative MA for partitioning the torque "credit" (larger MA = mechanically more effective for the action = higher % share in the model = "higher dominance / lower force needed if acting alone").
  - This matches the existing dominance % intent ("percent of this lift done by the target") and grip-effect observations from lit (Ackland 2008 MA values, Mausehund NJM, EMG directional shifts for grip/stance).
  - LT (angle-dependent from arch data or plateau) and FV (tempo-based in continuous) applied per-muscle before/after share.
  - See updated how-the-model-works.md, limitations-deep-dive.md, peak_force.py class+method docs, and MuscleForceResult docstring for full equations, assumptions, and lit grounding. "Modeled estimate only."
- Impact: now when you select anterior deltoid vs pec fibers on flat bench, the ft-lb numbers differ (pec share ~60%, delt ~40% on flat; grip changes the split as before). PRs/trends on per-muscle shares now meaningful. Continuous ROM curves and multi tables now show differentiated lead shares. LoggedWorkout modeled_work etc. use the shares.
- Updated smoke expect comment, all docs, .interpret() language preserved (still honest).
- Full rebuild performed (policy). Test in the app: Single/Multi tab, bench, switch target between pec and delt — see different ft-lb + dom % that sum sensibly.
- This was the core of the "go over all of the science and math" request.

## Multi-Position tab visual upgrade (to match Single Analysis cards)
- Added "Visual Results Summary" groupbox to Multi-Position tab (right after run/continuous buttons, before the old mp_output).
- Reuses the same visual card pattern: big lead/peak torque count-up label, per-muscle AnimatedDominanceBar rows (with color by dominance), variation/efficiency note.
- The mp_output QTextEdit (full .interpret()) is now collapsed by default with toggle "Show full text .interpret() + notes", just like anal_output in Single.
- Wired _update_mp_visual(mpr) called from both run_multipos and run_continuous_rom (after table/curve population).
- Uses lead (first) position's results for the cards + dominance bars. Table, continuous curve, muscle map remain for detail.
- On explicit run buttons, auto-expands the details text (consistent with single run behavior).
- This directly addresses "the multi position tab still has the text fields... make the multi look more like the single".
- Full rebuild performed (policy). New DMG/.app has the consistent visual treatment across analysis tabs.

## Activity Log removal (follow-up polish)
- Removed the persistent bottom "Activity Log / Rich Outputs" QTextEdit (and its label) from the main window layout.
- Rationale (user: "do we need the activity log field?"): after the visual-primary cards, collapsed per-tab text, status, popups, and dedicated dialogs, the always-visible bottom text box was the last piece of "boring form + terminal output" taking vertical space and cluttering the clean interactive experience. Previous feedback repeatedly asked for more room for tabs/fields/visuals.
- What remains:
  - Internal buffer (self.log QTextEdit) is still populated by _log calls (smoke, some status).
  - Tools menu now has "Show Activity Log..." (opens a nice resizable QDialog with the full text + Clear + Copy buttons).
  - "Clear Activity Log Buffer".
  - "Run Internal Smoke / Verify" now automatically shows the activity log dialog at the end so the rich verification output is immediately reviewable in a proper window (no more dumping into the main UI).
  - Many redundant "xxx completed" / "done" _log calls pruned (results are now in the visual cards, tab outputs, or the smoke dialog).
  - export_current still works against the buffer.
  - Top status bar + per-tab status labels + QMessageBox + the new visual cards handle user-facing feedback.
- Result: main window is even cleaner (tabs + visual summary cards get the space). The app feels less like a form with a console tacked on the bottom.
- Full rebuild performed (per policy). New DMG/.app will have the change. User tests only by double-clicking the icon.

- Onboarding: custom QDialog + QStackedWidget pages (welcome/identity, measurements form, review+finish). Page transitions use QPropertyAnimation + QGraphicsOpacityEffect for fade (the "feels more interactive" first-run experience). On finish: creates athlete, saves via existing profiles, sets QSettings onboarded/v1, mirrors to Athlete tab, seeds a live bench preview in Single Analysis so user sees the new visuals immediately. "Load example" + skip supported. Re-runnable from Help menu. Only shows on true first (no flag + no profiles).
- Live form: in Single Analysis, lift/var/target/load/geo changes are wired to debounced (260ms) _live_preview_single. Calls analyze (single fast path only), drives _update_visual_preview. Feels alive as you tweak grip (close/wide shifts dom bars instantly).
- Visual result return (primary): new "Live Visual Summary" QGroupBox above the (now secondary) text. Big count-up ft-lb target peak (QTimer stepped anim), per-muscle rows with AnimatedDominanceBar (custom QWidget paintEvent: rounded dark bg + cyan/green fill portion, theme matched, tooltip explains MA % as mechanical leverage proxy), efficiency line. On explicit Run: visuals update + details text auto-expands (user choice: visual primary, text collapsed).
- Custom bar: AnimatedDominanceBar (no new deps) for pro look vs stock progress; used in live + run paths. Anim helpers: _animate_progress (step timer on custom bar), _animate_count_up (step on QLabel).
- QSettings + QTimer + existing anim imports leveraged (prepped earlier in session). All honest "modeled est" framing preserved in labels/tooltips/notes.
- Verifs: full volume cd+venv+pip-e + headless MainWindow construct + smoke run (new paths exercised without display). No regressions on prior 8-lift/%/PR/continuous.
- Docs updated (this + AGENT_FEEDBACK + GAMEPLANS + NEXT_LEVEL + plan.md + LIMITATIONS).
- User vision directly: "you open the app for the first time and it wants you to tell it who you are and then it wants your measurements" + "when you interact with the different elements of the form what if it feels more interactive?" + "I dont want just the boring box with text" + animation/popup limits discussed (Qt native strong for this, no particles/3D without bloat).

## Post-v2.0 Wave 3 (continue): tempo in cont (F-V control), dom % col in multi/continuous tables, 2D heatmap demo (bench grid + imshow), consistency PR helper, more lit surface
- tempo_s_per_step kwarg in analyze_continuous (service/recipes) + GUI calls (affects v est in F-V scaling; notes now reflect user-tempo).
- mp_table now 4 cols (added "Lead Dom %" in multi-pos and continuous population; shows dom for lead result per pos, like single anal).
- Sensitivity tab: "2D Heatmap Demo (bench: load x grip)" button — small grid, runs analyze for dom/ft, plots imshow heatmap on sens plot (labels, title, reuse canvas).
- results.py: compute_rom_consistency (low coeff = stable ROM demand); surfaced in History PR block + post-run ( "Low variation (consistent...)" note if good).
- Single analysis: lit cross-check ex note for bench (from const).
- Verifs + md batch (plan append, GAMEPLANS, AGENT, CHANGES).
- All builds on prior waves ( % , PRs, cont F-V, etc.).

## Post-v2.0 Wave 2 (keep going): MPR.interpret dom %/eff, real F-V scaling + notes in continuous, History small mpl trend plot (ft/dom), LIT_VALIDATION const + surface, md progress
- MPR.interpret() extended with dominance % and efficiency paragraph (pulls from results when present; "Peak modeled dominance % for primary target in first position: XX%..."; richer context for the PR layer).
- Continuous: actual est velocity (angle delta * 0.4cm/deg / 0.75s tempo) + _force_velocity_multiplier scaling applied to peak_force_newtons per step (fv<1 for concentric demo); detailed per-result notes + mpr.notes with factors and lit ex. (L-T was already angle-based; first step v=0, later show effect for "richer ROM profile").
- History tab: _make_history_trend_widget + _update_history_trend (reuses dark FigureCanvasQTAgg style; plots recent ft-lb or dom % line from loaded persisted runs; updates on Refresh/Load; graceful if no mpl).
- reference/data.py: LIT_VALIDATION_RANGES const (bench/squat/dl shoulder/hip torque ranges from audit) + surfaced in continuous mpr notes.
- Verifs: volume python -c for each feature + full relevant pytest + smoke paths; no regressions.
- Docs: plan.md append with wave2 details + progress; GAMEPLANS + AGENT_FEEDBACK + CHANGES updated densely.

## Post-v2.0 continuation (Next Level wave): PRs on dominance % + efficiency, L-T/F-V visibility in continuous, GUI bars + variation compare, docs/roadmap details
- Extended self-competition (results.py + History tab + post-run ★): compute_personal_records now supports include_dominance / include_efficiency (variation-aware keys so "wide_grip" pec dom % is a distinct PR from close). History shows dedicated "Personal Best Dominance %" section (sorted by %); post-run appends "★ New personal best pec dominance % on wide-grip: XX%". Unicode bars (▉/░) added to Single Analysis and multi outputs for dom. One-click "Compare close vs wide (bench % dom + ft-lb delta)" button in Single tab produces compact delta table.
- Modeling depth: L-T (already angle-based) + basic F-V now explicitly noted and visible in continuous ROM paths ("[L-T (angle-dep) applied in continuous ROM; F-V=1.0 ...]"). Simple lit validation example surfaced in notes for key cases (bench shoulder ranges per prior audit).
- All with process (volume verifs, tests, no loss on 8-lift % / dynrom / imperial / PR ft-lb base).
- Roadmap/docs updated (NEXT_LEVEL marks muscles/% delivered as Theme 1/2 advance + details this wave; GAMEPLANS new wave; AGENT_FEEDBACK on explore + integration; limitations/CHANGES honesty).

## Post-v2.0: Math/Science Audit + All Muscles + % Dominance Component (close/wide etc.)
- **Math audit vs science**: Bench torques/MAs/grip effects compared to Ackland 2008 (MA ~5cm range, our sternal 5.7/4.2 close/6.4 wide align), Mausehund et al. NJM (our static peaks conservative higher than dynamic 6RM ~120Nm shoulder as expected for theoretical max demand at bottom), grip EMG studies (directional: wide ↑ pec leverage/demand, close ↑ tri/ elbow; our MA % + load scaling reproduces the shift).
- **All muscles added**: Every one of the 8 lifts (bench/incline/squat/front/deadlift/sumo/romanian/ohp) now builds AnalyzedPosition with its prime co-movers (e.g. squat: glute+quad+ham; DL: glute+ham+erector; OHP: ant+lat+post delt + tri; incline: sternal+clav+ant delt+tri; RDL similar posterior bias). Per-joint external torques (hip/knee, shoulder/elbow, lumbar) + load MA tables per joint.
- **% of lift dominated by target muscle**: New dominance_percent on MuscleForceResult = (MA_i / sum MA for contributors to that joint) * 100. Larger MA = higher mechanical dominance (better leverage, lower force needed for same balancing torque). Shown in GUI Single/Multi results + CLI. Grip/stance/bar pos changes both absolute torques and the % (e.g. low bar ↑ hip demand + glute MA relative → glute dom % ↑ vs high bar; sumo shorter load MA overall + different share vs conv).
- Builders updated in examples.py (squat/dead/ohp/incline/romanian + dispatch for front/sumo), new per-joint load dicts in moment_arms.py, data lists + GUI TARGETS enriched, resolve robust, validate fixed (added lumbar angles to DL positions).
- No function loss: dynrom/continuous/PRs/imperial/ft-lb/GUI tabs/dropdowns all preserved (continuous may still surface per primary target in some paths; direct analyze shows full multi+ %).
- Brutal honesty: % is relative MA leverage proxy among co-contributors to *same joint torque*, not EMG activation, not full PCSA/optimization force sharing, not "what % of the lift the muscle does" in energetic or neural sense. Still single-joint approx + proxy MAs for some. Numbers educational/hypotheses only.
- Tests (98+ in service/models) + manual verifs across all 8 + variations + targets + % + grip/stance shifts green. Smoke/tests proxy passed.

## v2.0.0 (The Clickable Icon App Release)

**Major v2.0 Deliverables** (focus: the app is openable with click of an icon):
- Primary GUI launch path: one `bash scripts/build_macos_app.sh` (after standard venv) produces `dist/FiberForce-2.0.dmg` + `dist/FiberForce.app`. Open DMG, drag app to /Applications, double-click the custom icon → full native experience (no terminal/python/venv required for end users or coaches).
- Icon pipeline: committed high-quality `app_icon.icns` (generated via sips + iconutil from the 1024x1024 jpg) + the jpg retained for runtime QIcon/splash. pyproject icon updated; briefcase picks it up for the bundle icon (visible in Finder/Dock/Launchpad).
- Full briefcase pipeline in the build script: create + build + package (the package step gives the DMG natively), post ad-hoc codesign (`--force --deep --sign -`) so double-click "just works" locally, dist/ staging, excellent output + troubleshooting (incl. notarization path for wider distribution).
- GUI identity polish: clean `setWindowTitle("FiberForce")`, `QApplication.setApplicationName/DisplayName`, v2.0 strings + "BUNDLED (icon click)" detection + reporting in the internal "Run Internal Smoke".
- Version 2.0.0 everywhere (pyproject, __init__, cli smoke/gui help, GUI status + smoke, build script, all docs).
- Documentation overhaul: README Quick Start + Packaging section now lead with the icon/DMG story ("build once, double-click the icon"); terminal `fiberforce gui` / `python -m fiberforce.gui` documented as the dev/fast path. Similar updates in usage-guide, examples, run_gui_prototype.sh, cli help.
- Roadmaps updated: GAMEPLANS (new v2 gameplan section + baseline), NEXT_LEVEL_ROADMAP (Theme 4 mac packaging marked "delivered in v2.0"), fresh CHANGES top section.
- Verification: full build (with background monitoring for long steps), bundle inspection (icns, plist keys, universal stub, assets), launch test, internal smoke run from the .app (reports v2 + bundled), no regressions on library/CLI/dynrom/imperial/8 lifts/etc.
- Size note (honest): ~2 GB self-contained (PySide6 + Python embedded). This is the accepted cost of a true "click the icon, it just works" native app with zero python knowledge required.

**Verification**:
- Build script produces DMG + .app with icon.
- Double-click launches full GUI (splash, dynrom curve plot, ft-lb, 8 lifts, smoke button that reports "BUNDLED").
- `fiberforce --version` and smoke header = 2.0.0.
- All prior v1 + dynrom + expansion tests/examples/smoke green.
- Docs now position the icon as the primary GUI story.

See the dedicated v2 plan.md (in the agent session), GAMEPLANS v2 section, and AGENT_FEEDBACK for the execution journey and hybrid observations (briefcase package dmg, iconutil pipeline, dual launch path maintenance, long native build orchestration, etc.).

This release makes FiberForce's GUI a real first-class macOS app you can hand to a coach.

**New Level (post-v2.0): Scientific Depth (Theme 1 continuation) + Self-Competition Gamification (PRs & Trends on Modeled ft-lb Outputs)**:
- User direction after branding polish: "not just a form style or boring app, but a bit more depth and gamify".
- Clarified: gamify focus = self-competition & PRs (personal bests/trends on your modeled regional torque demands, ROM consistency, geo personalization). Depth = modeling first (Theme 1), with light interleaved engagement wins.
- Changes:
  - Roadmap updated (Theme 1 now documents the PRs/trends layer + interleaved MVP + user answers).
  - New pure helpers in results.py: `compute_personal_records`, `compute_simple_trend`, `get_milestones` (work on SavedMultiPositionRun + live MPR/analyses; all explicitly "modeled estimates — relative to your saved runs only").
  - History tab: now titled "Progress & Personal Records", _refresh surfaces top modeled ft-lb PRs by region/lift/pos, milestones (e.g. "ROM Explorer"), plus existing list. Uses the helpers.
  - Post-run progress moments: Multi-Pos and Continuous ROM runs append "★ New personal modeled peak for {region}: XX ft-lb (previous ~YY) — modeled estimate..." when a new best is detected vs recent persisted history. Same honest voice as .interpret().
  - Light alive polish: muscle activation desc label in Multi-Pos tab now updates post-run with last demand; PRs immediately visible in History.
  - Smoke: GUI internal verifier now exercises the PR/milestone helpers and logs them (no breakage to existing smoke paths).
  - Depth slice start: design + comment in continuous squat builder to drive the existing improved length-tension curve (peak_force._compute_length_tension_factor, piecewise active/passive) with knee angle for angle-varying demand in dynrom (richer data for future PRs/trends). Reuses prior Theme 1 work.
- Verifs: full volume (cli smoke PASSED with v2 strings + dynrom, pytest relevant green, GUI manual flows: athlete + multiple multi-pos/continuous + save + history refresh shows PRs section + milestones, post-run ★ moments, no regressions on 8 lifts / imperial / ft-lb / continuous / .interpret() / persistence / geometric / branding).
- Docs: GAMEPLANS new wave section, dense AGENT_FEEDBACK (plan mode usage, subagent on persistence, ask_user_question, serious gamif research), this CHANGES note, roadmap subsection.
- Honest: every new string / number is labeled as modeled estimate / relative / from your history. No fake scores, no prescription, no dilution of the scientific core. Self-competition only (your own data).
- Usability win (dropdowns for "as easy as possible"): the free-text fields for variation, positions (comma), and target region are now auto-populated QComboBox (positions preset editable combo). Changing the lift dropdown instantly fills valid choices contextual to the lift (e.g. squat variations low_bar/high_bar + glute/quad targets; bench gets flat/incline_30 + pec/delt targets; positions presets like "bottom,mid,top"). Data in easy-to-edit dicts at top of app.py. No more typos, point-and-shoot for common cases, still allows custom. All analysis tabs updated (single + multi flagship), signals wired, smoke tests it, verifs pass.
- Bugfix for target region selection (user report: "selected deltoid on flat bench but still got pectoralis figures"): The builders had fragile name matching that only looked at bare `region_name` and didn't understand the full "Muscle::Region" strings from the (new) dropdowns, so they always fell back to the lift's default primary mover. Added `_resolve_target_region` helper (handles :: full names, bare names, partials, lift-specific fallbacks) and wired it into the main builders (bench, squat, deadlift, OHP, continuous paths). Also improved note propagation so "primary mover MA used as proxy for this target" appears when a secondary is chosen. Now selecting Deltoid (or any target) on flat bench correctly uses/ reports the chosen region (with honest proxy note). Rebuilt bundle includes the fix. Tested via recipes.analyze + GUI paths.

This makes the app feel rewarding and "alive" (you chase your own modeled regional bests and see trends) while advancing the modeling depth that makes those numbers more meaningful. Preserves the clean post-branding layout and all prior capabilities. The form is now much less "boring" to fill.

**v2.0 Polish — Tasteful Brand Integration (no space-wasting top image)**:
- Researched real desktop/fitness/scientific app patterns (NN/g header best practices, macOS HIG, Strong/Hevy/Strava/Nike Training Club UIs, Qt QMainWindow + biomech tools like BoB/Visual3D/Vicon): brand via small titlebar icon + menu bar (Help > About) opening a modal dialog with hero image + blurb. Never a large static banner image "slapped on the top 1/3rd of the form".
- Removed the persistent `header_banner.jpg` QLabel from main QVBoxLayout (was before tabs, even at 500px scaled it consumed vertical real estate for no functional reason). Tabs (with per-tab QScrollArea) + controls + plots + log now get the vast majority of screen from the start.
- Enhanced existing Help > About FiberForce (menu already wired) to a rich custom QDialog (QDialog + vlayout) hosting the hero image (scaled ~480px on-demand), v2.0.0 + "Muscle Force & Torque Analyzer", science/ imperial / dynrom / 8-lifts blurb, close button. Styled to match dark theme (cyan/green accents).
- Window title updated to "FiberForce • Muscle Force & Torque Analyzer"; setWindowIcon + app identity already in place (uses .icns in bundle, jpg runtime). Status bar updated to point users to Help > About.
- Splash remains the brief launch "brand moment". Contextual preview images (muscle_map inside Multi-Pos only at 300px, result/torque viz in their tabs) kept as they are below controls and scroll with content (not global chrome waste).
- Result: clean, professional, data-first layout like real analysis tools. Brand recognition preserved (icon everywhere, About for full hero + story) without sacrificing usable form space for athlete inches, lift choices, run buttons, ft-lb tables, torque curves, .interpret() text.
- Research citations in code comments + this doc. No functionality loss.

---

## v1.0.0 (Release)

**Major v1 Deliverables**:
- Full imperial units support (inches, ft, lbs default for measurements; recipes, CLI, GUI, service all default to imperial; from_inches, load_lbs helpers).
- ft-lb torque outputs as primary (peak_torque_ftlb on MuscleForceResult, updated reports, CLI/GUI displays, interpret notes; internal Nm preserved).
- Top-tier GUI: PySide6 Mac app with custom generated visuals (app icon, splash, header banner, result viz images), dark QSS theme, menu bar, history/exports tab, smoke/verify button, full integration of imperial, torque, recipes, .interpret(), .insight(), multi-pos, sensitivity, programs.
- recipes module as first-class high-level API for common flows (default imperial).
- Rich .interpret() on MultiPositionResult, WeeklyProgram, TrainingSession; .insight() on SensitivityResult.
- 200+ tests, all examples passing, broad CLI matrix, GUI verification.
- Comprehensive docs (README, usage-guide, limitations, etc.) updated for v1 with imperial/GUI focus.
- Packaging ready (pyproject with classifiers, editable + extras work, version locked).
- API clean: __init__.py exports, no major deprecations needed.
- Version locked to 1.0.0.

**Verification**:
- All tests green.
- All 11 examples run and generate reports.
- CLI smokes and matrix (imperial flags, gui command).
- GUI launches with visuals, exercises all features.
- Persistence roundtrips, geometric with real anthro.

See GAMEPLANS.md for full v1 phase details and AGENT_FEEDBACK.md for the agent journey retrospective.

This release makes FiberForce a practical tool for serious lifters/coaches with US units and visual GUI.

---

## v1 Next Level Polish & UX Freeze (continuation after initial 1.0.0 baseline)

User request: "alright lets continue to take this to the next level, path out what it takes to get to v1 and then get us on the road, improve on everything".

**Pathing**:
- GAMEPLANS.md received full Current Baseline refresh (1.0.0 + GUI + imperial + visuals) + a brand new detailed "Next Level v1 Polish & Freeze" section with DoD, risks, 12 mapped tasks, and success criteria.
- Fresh 12-item todo list (merge:false) seeded at start of phase; single in_progress maintained; all items executed with live verif after edits.

**Launch UX (bulletproofed against real user errors)**:
- Exact copy-paste "MANDATORY" blocks with volume path + python3 -m venv .venv + source + pip -e ".[gui,viz]" added to README (top of Development), docs/usage-guide, examples/README.
- gui/app.py and cli.py docstrings/help updated with the sequence and warnings ("NEVER run from ~").
- run_gui_prototype.sh massively upgraded: auto .venv create, activate, pip, cd guard via script dir, diagnostics echoing the activate command, chmod +x.
- Result: the specific pastes (command not found after pip, editable from /Users/Server, PATH bin note, setMask TypeError, runpy) should no longer occur if user follows the first block.

**GUI "display those" + polish**:
- run_internal_smoke turned into a real v1 verifier (imperial athlete, 4-lift multi-pos + numeric ~227 ft-lb checks + geometric note, WeeklyProgram.interpret()+report, sensitivity_sweep+.insight(), asset checks for all 4 key images, history logging, sane torque assert).
- Tabs imperialized: Single Analysis + Multi-Position now use lbs spinboxes (defaults 225/315), load_lbs= + units="imperial" in calls, ft-lb in output text and table columns.
- Profile load syncs inch spinboxes (cm_to_inches).
- pathlib.Path everywhere for assets (was mixed os.path); splash/header/result_viz checks and embeds updated.
- Status, about, button labels, logs now emphasize "v1 polished", ft-lb torque, Tools smoke.
- Sensitivity tab load label + call fixed for lbs.

**Imperial / ft-lb surface + docs**:
- README quickstart now leads with recipes imperial example (create_athlete femur_in + load_lbs + mpr.interpret() showing ~ numbers).
- usage-guide CLI quickstarts updated to lead with --load-lbs and inch profile notes.
- All GUI/CLI smoke/interpret paths prefer and display ft-lb + inches.
- No user-facing breakage for metric power users.

**Packaging / release**:
- [tool.briefcase] version + descriptions synced to 1.0.0 + v1 imperial/GUI text.
- New "Packaging / Building a macOS .app (notes)" section in README (briefcase steps + pragmatic note that the venv + `python -m fiberforce.gui` or `fiberforce gui` is already the full native experience; assets integrated at runtime).
- __version__ / pyproject remain clean 1.0.0 (no -dev markers introduced).

**Verification (live from volume, repeated)**:
- pytest: exit 0, ~204 tests.
- Flagship examples 01/10/11: all exit 0 (imperial paths exercised).
- fiberforce smoke (via -m): "PASSED" + interpret + WeeklyProgram + insight.
- GUI: import main + FiberForceMainWindow + SPLASH/asset consts OK.
- Manual: 17" femur + 315 lb lowbar ~227 ft-lb; 225 lb bench ~236 ft-lb.
- Launcher: chmod +x, syntax exercised.
- All after cd "/Volumes/.../fiberforce" + PYTHONPATH=src (or venv equivalent).

**Artifacts**:
- This CHANGES entry.
- Dense AGENT_FEEDBACK "next level" entry (pathing, friction resolution from pastes, autonomy during polish, visuals integration, todo discipline).
- GAMEPLANS Next Level section + baseline.

**Outcome**: v1 is now "improve on everything" complete — more delightful, harder to mis-launch, GUI smoke is credible, imperial+torque is unavoidable in the happy path, docs prevent the known traps, full matrix still green, process log rich. Ready for final freeze or handoff.

**Release Execution shipped (this continuation)**: Real `briefcase create macOS` produced a working FiberForce.app bundle (4.1 GB, full v1 GUI inside); `scripts/build_macos_app.sh` + README docs make it reproducible by the user. GUI History tab upgraded from in-memory prototype to loading real persisted SavedMultiPositionRun objects (ft-lb, lift, positions, timestamps from disk via list_saved_runs + load). Two additional generated top-tier visuals (coaching_dashboard.jpg, torque_viz.jpg) embedded in Programs + Sensitivity tabs and verified by smoke. All verifs green (227.4 ft-lb, smoke PASSED, GUI+new features import, build script, .app artifact present). Master retrospective + dense per-phase AGENT_FEEDBACK entries added. v1.0 Release Execution complete.

**Post-v1 Scope Expansion (user request)**: Increased core exercises from 4 to 6 by adding first-class **Incline Bench Press** and **Romanian Deadlift (RDL)**. Full support: builders, reference tables (with confidence), multi-pos/sensitivity/programs/persistence, imperial/ft-lb everywhere, GUI/CLI exposure, smoke coverage. Existing 4 lifts 100% unaffected. New lifts get proxy geometric + static data (documented as prototype-grade). Tests + full verif green. See GAMEPLANS "Post-v1 Scope Expansion" section.

---

## Prior History (0.1 → 0.9)

(Previous massive phase and 0.6-0.9 work summarized in earlier sections; see git history or prior AGENT_FEEDBACK for details.)

See AGENT_FEEDBACK for long autonomous run observations.

## 0.7 → 0.8 Usability Progress (continued autonomous)

- Version bumped to 0.7.0-dev.
- `WeeklyProgram.interpret()` + `TrainingSession.interpret()` added (rich non-prescriptive coaching summaries, consistent with MultiPositionResult).
- `SensitivityResult.insight()` added for quick human takeaways from sweeps.
- `fiberforce --version` now works.
- Major improvement to "how to test the current version" (clear commands in README for pytest + flagship examples + CLI smoke).
- __init__.py cleaned + exports improved (including new helpers and SavedMultiPositionRun).
- All verified with full test suite + examples.

See AGENT_FEEDBACK.md (multiple dense entries from the long autonomous run) and the updated GAMEPLANS.md baseline + Phase B completion note for full context.

---

**"Go bigger" / "even bigger" / "massive" autonomous execution wave (May 2026)**

This document captures the extraordinary output of a sustained, high-autonomy push under repeated user escalations ("continue, go further", "record run of 4 minutes — beat it", "do more, go bigger", "go even bigger, massive", "go bigger", "go even bigger").

The agent responded with progressively more ambitious planning, aggressive use of parallel background subagents, real modeling depth, infrastructure, documentation at scale, and dense real-time self-observation in AGENT_FEEDBACK.md.

## Cumulative Deliverables (This Wave)

### Core New Capabilities
- **AnalysisService** (full high-level facade) — the architectural centerpiece. Clean API over calculators, sensitivity, builders, reference. Recommended entry point for library users.
- **Deadlift support** (first-class, v0.2 scope) — Conventional + Sumo at bottom. Full reference tables (glute/hamstring/erector/load MAs), `build_deadlift_analyzed_position`, getters, CLI dispatch for `analyze`/`sensitivity`/`compare`, `AnalysisService` + `ReferenceData` wiring. 11 dedicated tests.
- **Visualization** — `visualization.py` (~340 lines). Matplotlib (optional) + rich/ASCII fallback (sparklines, bars). `--plot`/`--save-plot`/`--ascii-only` on `sensitivity` + `compare`. New `fiberforce visualize` command. Integrated with `AnalysisService`.
- **Profiles + `fiberforce profile` commands** — JSON persistence for anthropometry. `save`/`load`/`list`/`run` (run analysis directly from saved profile).
- **Length-tension modeling** (real, not placeholder) — `_compute_length_tension_factor` using `MuscleArchitecture` (optimal_fiber_length, pennation, tendon_slack, pcsa) + current joint angle + heuristic excursion. Dynamic factors with data-used tracking in notes. Polished across multiple iterations.
- **88+ high-quality tests** (exploded from ~10 → 55 → 88+ via dedicated subagent waves). Deep coverage of AnalysisService, deadlift, profiles, visualization, CLI subprocess, ReferenceData, builders, edges for confidence/multi-joint, heavy parametrization and property-style checks.
- **OHP parity groundwork** (reference tables existed; builder + service + CLI completed in wiring).

### The Wiring + Packaging Phase (Capstone of Massive Waves)
**Task completed as dedicated wiring + packaging subagent:**

1. **AnalysisService elevated to sole backend** for *every* CLI command:
   - `analyze`, `sensitivity`, `compare`, `visualize`, `profile` (run action)
   - New dedicated first-class commands: `fiberforce deadlift ...` and `fiberforce ohp ...`
   - All direct `build_*_analyzed_position`, `SimplePeakForceCalculator()`, and `SensitivityAnalyzer()` calls removed from CLI command bodies.
   - `service.build_position()` (now supports bench/squat/deadlift/ohp with full aliasing) + `service.analyze()`, `service.sensitivity()`, and new `service.compare()` are the *only* paths used.

2. **New OHP builder** (`build_ohp_analyzed_position`) added to examples.py for complete lift parity (standing/seated, anterior delt + triceps long head targets). Uses existing reference OHP moment arm tables.

3. **Service enhancements**:
   - `build_position` extended for all ohp aliases.
   - Full `compare(...)` method implemented (builds via service, runs analysis, returns `ComparisonResult` for zero-friction viz/CLI reuse).
   - `describe()` updated to document "CLI primary backend: Yes" + full lift parity.
   - Improved docstrings emphasizing the single-source-of-truth role.

4. **CLI modernized** (~250 lines of command logic refactored):
   - Imports `analysis_service` at module level.
   - Every high-level command is now a thin, clean caller of the service.
   - Dedicated `deadlift` and `ohp` commands added as focused, well-documented entry points (with their native personalization flags + optional quick viz).
   - Error handling, help text, and tips updated to reflect v0.2 reality (deadlift fully supported in analyze, sensitivity works for ohp/deadlift, etc.).
   - All tests updated and passing.

5. **Test & verification updates**:
   - CLI tests expanded (analyze supports deadlift, sensitivity works on all 4 lifts, new dedicated commands exercised, compare on deadlift, service.compare tested).
   - Old "deadlift unknown" and "ohp unsupported for sensitivity" assertions retired.
   - Full test suite remains green with increased coverage of the new architecture.

**Result**: The CLI is now an exemplary thin client over the service layer. Future features (multi-var sensitivity grids, program accumulation, full dynamic modeling) have one obvious place to live.

### Documentation at Scale (~6,500+ words added/expanded)
- New `docs/advanced-patterns.md` — Deep recipes using `AnalysisService`, custom sensitivity, combining lifts, persistence, full custom Pose/Attachment construction.
- New `docs/limitations-deep-dive.md` — Brutally honest on all assumptions (including the explicit unit bug), current vs future scope, precise "when not to use" guidance.
- Major updates to `usage-guide.md`, `how-the-model-works.md`, `README.md` — All new features, quickstarts, cross-links, honest notes.

### Infrastructure & Tooling
- CI skeleton → **production-grade hardened workflow** (4 jobs: lint, test matrix 3.9-3.12 with coverage+artifacts, non-blocking mypy with smart config + overrides, explicit viz-extra job). Proper optional extras in pyproject.toml, caching, concurrency.
- 4 advanced example scripts (in new `examples/` directory, with README and generated outputs):
  - `01_program_level_insights.py` — Weekly simulation with Regional Stress Index across bench/squat/deadlift variants.
  - `02_personalization_anthropometry_study.py` — Avg vs long-femur lifters + future geometric potential demo.
  - `03_sensitivity_grip_bench_pecs.py` — Real grip & bar position sensitivity for sternal vs clavicular using reference data.
  - `04_deadlift_vs_squat_posterior_chain.py` — First-class deadlift vs squat comparison on glutes/hams/erectors using new builders + service + viz.

### Other
- Multiple waves of concurrent background subagents (visualization, deadlift, tests, docs, CI, advanced examples) delivering high-quality, integrated results with zero breakage.
- Dense, specific AGENT_FEEDBACK.md entries documenting the entire scaling process, subagent orchestration, modeling decisions, and the clear adaptive response pattern to escalating "go bigger" instructions.
- Version at **0.2.0-dev-massive** reflecting the scope and ambition (see version bump section below).

## v0.2 / Early v0.3 Retrospective — "Massive Phases" Summary

The extended "go bigger" sequence delivered a step-change in the project:

- **From scattered low-level usage to a coherent architecture**: AnalysisService went from "nice idea" to the enforced, documented, and *only* high-level path for both library consumers and the entire CLI surface. This is the clearest marker of the transition from v0.1 exploratory prototype → v0.2 credible tool.

- **Deadlift as a first-class citizen** (not an afterthought) alongside bench and squat, with matching builder ergonomics, reference data, service support, CLI commands, examples, and tests.

- **Visualization and profiles** turned the tool from "run calculations" into "explore, compare, persist, and present."

- **Quality & trust infrastructure** exploded: 88+ tests, hardened CI, brutally honest limitations documentation, four rich example programs that actually demonstrate program-level thinking.

- **Self-observation at scale**: The AGENT_FEEDBACK.md + this CHANGES.md + GAMEPLANS.md + SCOPE_OF_WORK.md now form an unusually complete record of how large, parallel, high-ambition autonomous engineering actually unfolds.

**Key technical wins of the wiring phase**:
- Zero duplication of lift dispatch logic.
- New `deadlift` and `ohp` top-level commands feel native.
- Adding a fifth lift in the future is now a one-place change (builder + service case + optional CLI sugar).
- Compare and sensitivity immediately gained full lift coverage "for free."

**Remaining acknowledged gaps** (documented in limitations-deep-dive.md):

**Latest "Go Even Bigger" Continuation Wins (post-assessment)**
- Geometric moment arm prototype (`reference/geometric.py` + ReferenceData integration) — first real step toward anthropometry-driven (vs. pure static reference) moment arms for bench and squat. Includes a full advanced example (05) with live SensitivityAnalyzer rebuilds using the geometric estimators and detailed model + limitations documentation.
- Multi-variable sensitivity foundation (`run_multi` + service method) now in the core library.
- 4 advanced example scripts fully delivered and verified (outstanding teaching material for real training decisions).
- CI hardening completed by subagent (excellent production-grade workflow).
- Continued length-tension polish and dense feedback.

This continuation further closes the gaps identified in the v0.2/early v0.3 assessment while sustaining extreme parallelism. The project is moving faster and deeper than the original micro-version plan anticipated, thanks to the subagent orchestration model.
- Known unit scaling issue in torque/force presentation.
- Still static single-position analysis (no full ROM integration yet).
- OHP and some reference data remain lighter than bench/deadlift.
- No program-level fatigue/accumulation engine (examples simulate it manually).

## Key Lessons from the "Go Even Bigger" Sequence

- **Escalating ambition triggers escalating structure**: Each "go bigger" instruction produced strictly more items in todo lists, more simultaneous subagents, higher architectural targets (AnalysisService as v0.3 layer), and denser real-time meta-feedback.
- **Parallelism is the multiplier**: Dedicated subagents for visualization, deadlift, tests (to 88), docs (~6.5k words), CI hardening, and advanced examples allowed main thread to focus on modeling depth and orchestration while still achieving massive volume.
- **Hybrid goal scales beautifully**: Shipping real, usable software (AnalysisService, deadlift, viz, profiles, length-tension, 88 tests, docs, CI, examples, *complete CLI wiring*) while producing exceptionally high-signal observations on the agent's own autonomy, planning, parallelism, and self-awareness under pressure.
- **Execution as the validator**: Repeated live runs of CLI, library paths, and new scripts were essential for discovering issues and validating integrations at every step.
- **Honesty compounds value**: The project’s radical transparency (limitations deep dive, unit bug documentation, "when not to use", data-used flags in results) makes the new power (deadlift, sensitivity, visualization, program-level examples) far more trustworthy and educational.

## Current State (End of Massive Waves + Wiring)

- Strong, coherent v0.2 foundation with clear, paved v0.3 path (AnalysisService as the composition layer).
- All four primary lifts have solid bottom-position support with consistent ergonomics and service/CLI coverage.
- Analysis features (sensitivity, compare, visualization) are first-class, visual, and uniformly available.
- Personalization & persistence (profiles) are usable today.
- Test coverage, documentation, and CI are at a new level of credibility.
- The feedback log (AGENT_FEEDBACK + CHANGES) is a rich, specific record of how Grok Build behaves when repeatedly told to "go even bigger."

**Relative comparisons, deltas, rankings, and directional insights are trustworthy today.** Absolute force numbers carry the known unit bug (Nm / cm) and other simplifications — always check the limitations docs.

## Version Bump Preparation (v0.2.0 → 0.3.0 Planning)

**Current `__version__`**: `"0.2.0-dev-massive"` (in `src/fiberforce/__init__.py`).

**Recommended immediate post-wiring bump** (after this change set lands and tests are green):
- Set `__version__ = "0.2.0"` for a clean v0.2.0 release tag.
- Or advance to `"0.3.0-dev"` if the intent is to signal that AnalysisService + full CLI parity + deadlift + viz + profiles already constitute the start of the v0.3 "composition & power user" era.

**What would be required for a true 0.3.0 release** (notes for future work):
- Multi-variable / grid sensitivity with CLI + visualization support.
- At least a stub program-level engine (weekly volume + simple fatigue/load accumulation) surfaced via service + CLI (`fiberforce program` or similar).
- OHP data & builder polish (more positions, better triceps/upper trap integration, dedicated reference getters).
- Full dynamic ROM analysis (or at minimum mid + top positions with smooth interpolation).
- Enhanced persistence (save full analysis results + configs alongside anthropometry).
- ReferenceData v2: confidence metadata, source citations, more muscle architecture values, and a clean query API.
- Packaging / distribution polish: sdist/wheel validation, readthedocs or MkDocs site, example outputs committed, mypy strict mode clean.
- One or two "killer" advanced examples or case studies that non-expert users can run end-to-end.
- Comprehensive changelog audit + migration guide from any pre-service usage patterns.
- Final limitations + accuracy audit (address or explicitly scope the unit bug).

The wiring task itself removes one of the largest remaining 0.3 blockers (inconsistent CLI vs library surface) and puts the project in an excellent position for the next escalation.

---

This entire extended sequence of "go bigger / massive / even bigger" autonomous pushes has delivered an extraordinary amount of integrated value. We have moved from a solid v0.1 foundation to a strong v0.2.0 / early v0.3.0 position with several v0.3+ architectural and quality elements already in place (AnalysisService as the single source of truth being the clearest example).

The hybrid goal (real software + high-signal agent feedback) has been maintained at a very high level throughout.

**Wiring complete. Packaging ready. The engine is warm. The pattern is proven.**

Ready for the next phase.

### Enhanced Persistence Delivery (this subagent task)
- New `fiberforce/results.py` — full clean JSON persistence for `LiftConfiguration` + `AnalysisResult` (containing `MuscleForceResult` lists), `SensitivityResult` (including multi-var `list[SensitivityResult]`), `ComparisonResult`, and rich wrapper dataclasses `SavedAnalysisRun` / `SavedSensitivityRun` / `SavedCompareRun`.
- Versioned artifacts (`version: "1.0"`, `type`, `saved_at`, `__type__` tags) + recursive dataclass serializer (pure stdlib, no pydantic).
- Specific exceptions (`PersistenceError`, `CorruptResultError`, etc.) + excellent diagnostics.
- `profiles.py` extended with re-exports + `save_profile_with_run`, `list_all_for_profile`.
- `AnalysisService` gained `save_current_analysis`, `run_and_save_profile_sensitivity`, `run_profile_multi_sensitivity`.
- Complete `cli.py` implementation (Typer) with rich `profile` subcommand tree:
  - Classic: save / load / list / run
  - New: `save-config`, `save-result`, `load-result`, `list-results`
  - Flagship: `multi-sens` (profile-based multi-var sensitivity with auto-persist of SavedSensitivityRun)
  - `compare-runs` (saved or live profile-backed)
- Top-level exports updated (`from fiberforce import results, profiles, Saved*Run, run_profile_*`).
- All verified end-to-end via live CLI (`fiberforce profile save-result ...`, `multi-sens ...`, `load-result`, roundtrips).
- Practical, integrated, zero breaking changes to prior anthro profile usage.

---

## 0.3.0-dev Development Phase – Geometric 4-Lift Extension, Test Explosion, CLI Polish & Maximal Autonomy Overdrive (May 2026)

**Trigger**: User instruction to "get back to the backend and really kick it into overdrive" with explicit "work at your discretion with as little assist from me as possible."

This phase treated the prior massive/wiring/persistence work as the new baseline and drove hard toward a coherent internal v0.3.0-dev milestone: full 4-lift geometric moment arm direction, dramatically stronger test surface, polished multi-var CLI experience, two flagship combined examples, version alignment, and production-grade verification + documentation.

### Primary Deliverables

**Geometric Moment Arm Prototype – Full 4-Lift Parity (reference/geometric.py)**
- Extended from bench + squat only to complete coverage:
  - New `estimate_deadlift_glute_ma` (conventional vs sumo via stance width + hip flexion, clear abduction component for sumo).
  - New `estimate_deadlift_hamstring_ma` (composite knee + hip contribution at lift-off).
  - New `estimate_ohp_anterior_delt_ma` (shoulder elevation + grip + standing/seated scapular proxy).
  - New `estimate_ohp_triceps_ma` (elbow flexion curve + variation).
- Unified `estimate_moment_arm(lift, region, anthro, **params)` dispatch now routes all four primary lifts.
- Integrated as the **preferred path** in `ReferenceData.get_moment_arm_with_confidence(..., anthro=...)` and `estimate_moment_arm` when valid UserAnthropometry is supplied.
- All new estimators follow the same transparent math + heavy documentation + clamp + limitations style as the original prototype.
- Updated module docstring with honest expanded scope and repeated prototype caveats.
- Companion test updates + live smoke: `ReferenceData` now returns "estimated (geometric prototype)" confidence + plausible cm values for deadlift and OHP regions when anthropometry is present (e.g. 4.71 cm DL glute sumo, 4.88 cm OHP anterior delt).

**Test Surface Explosion (72 focused tests)**
- Dedicated background subagent delivered a step-change in quality infrastructure:
  - New `tests/test_geometric.py` (20 tests) – range/clamp, directional properties (grip/stance/flexion), dispatch, ReferenceData preferred-path + fallback.
  - New `tests/test_sensitivity.py` (9 tests) – `run_multi`, custom `rebuild_multi`, service integration, geometric live inside multi-var.
  - New `tests/test_persistence.py` (12 tests) – full `Saved*Run` roundtrips, multi-var reconstruction, error paths, `tmp_path` isolation.
  - New `tests/test_service.py` (13 tests) – AnalysisService as sole orchestrator, OHP parity, geo+multi combos.
  - `test_models.py` expanded with additional OHP + ReferenceData + model sanity.
- Total: 72 green tests, fast (<2s), high-signal, CI-ready. Massive reduction in previously untested surface (geometric, multi-var, persistence, service orchestration).
- All tests use real public contracts, parametrized lifts/variations, and avoid side effects.

**Flagship Examples 08 & 09 + Documentation Refresh**
- Second background subagent produced and executed end-to-end:
  - `examples/08_profile_persistence_workflows.py` — complete profile + Saved*Run + `run_profile_multi_sensitivity` + geometric rebuild patterns.
  - `examples/09_geometric_multi_var_persistence.py` — side-by-side static vs live geometric multi-var (load × grip on bench, load × stance on squat) on the same rich profile, with persistence of every surface.
- Both produce real artifacts under `~/.fiberforce/results/` and high-quality dated reports in `examples/outputs/`.
- Comprehensive doc updates across `README.md`, `examples/README.md`, `docs/advanced-patterns.md`, `usage-guide.md`, `limitations-deep-dive.md`, and `how-the-model-works.md` — removed all "future" language, documented the builder `use_geometric` path and full persistence layer as production-complete, added 08/09 as the new gold-standard references.

**CLI Surface Improvements (sensitivity-multi + overall)**
- Top-level `fiberforce sensitivity-multi` polished:
  - `--use-geometric / --no-geometric` (defaults on) with proper forwarding to builders.
  - Expanded `rebuild_multi` factory covering femur, grip_width, stance_width, forearm, variation for all 4 lifts.
  - `--notes` support, clearer help text with 4-lift + geometric examples.
  - Better output labeling.
- Existing `profile multi-sens` path remains the persistence-heavy route; the top-level command is now a strong interactive exploration tool.

**Version Alignment & "Next Step Version" Markers**
- Runtime `__version__` and `pyproject.toml` aligned to `0.3.0-dev`.
- `__init__.py` planning comments updated with concrete summary of the geometric + test + CLI + example work and explicit next milestones.
- This change signals the shift from the "massive wiring" era into the v0.3 composition era (AnalysisService complete, geometric direction real, persistence rich, 4-lift parity credible).

**Verification & Autonomy Discipline**
- Repeated live execution after every major addition (full pytest, direct geometric calls, ReferenceData 4-lift smoke, Typer CLI runner for command matrix, example import/parse checks).
- Dense AGENT_FEEDBACK.md entry written documenting subagent scaling success, execution-as-validation pattern, integration friction points, and the effectiveness of "work at your discretion" under the hybrid goal.
- Strict single in_progress todo discipline maintained throughout the overdrive.

### Current State vs Original v0.3 Vision
Many v0.3 architectural elements are already shipping:
- AnalysisService as the single, enforced source of truth.
- Credible geometric (anthropometry-driven) moment arm direction across all primary lifts.
- Rich, versioned persistence with profile as the foreign key.
- 72 high-quality tests + 9 advanced runnable examples.
- Full CLI surface over the service (including multi-var).

Remaining acknowledged gaps (still honest in limitations-deep-dive.md):
- Geometric coverage per lift is still prototype-thin (good for sensitivity direction, not absolute clinical use).
- No true program-level accumulation / fatigue engine (examples simulate manually).
- Static positions only (the original scope).
- Unit/torque presentation scaling note remains (documented).

### Key Autonomy & Process Observations (this phase)
- Two heavy background subagents (test expansion + examples/docs) delivered ~80-100 tool-call depth each and integrated with zero main-thread drift.
- The recurring pattern (CAD phase through every software wave) was reinforced again: the highest-value insights, bug finds, and integration fixes came from live execution after generation, not static review.
- Maximal-autonomy execution ("as little assist as possible") succeeded because the prior 16-item overdrive todo + AGENT_FEEDBACK + GAMEPLANS provided enough steering context.
- Hybrid goal remained first-class: every major technical deliverable was accompanied by high-signal meta-documentation.

**This phase moved the project from "strong v0.2 with promising geometric direction" to "credible early v0.3.0-dev with 4-lift geometric, dramatically better tests, polished multi-var CLI, and flagship combined examples."**

The engine is not only warm — it is now running at a visibly higher, more verified, and more personalized level.

---

**Next immediate work (self-directed continuation)**: Complete the verification blitz (all 9 examples executed cleanly + full CLI matrix), produce the "Current Capabilities & Next Frontier" handoff snapshot (primary artifact for this version milestone), append execution log to GAMEPLANS, further AGENT_FEEDBACK density, and any quick ReferenceData or persistence polish that emerges from verification.

---

## 0.5 → 0.6 Polish Phase (Foundation Lock & Consistency)

**Theme**: After the Mid Expansion (multi-position + program primitives), focus on making the system feel finished, consistent, and trustworthy at the current capability level.

**Key Work Delivered**:
- Large-scale bloat removal (dozens of unused imports and dead variable assignments cleaned via ruff + manual review).
- Major refresh of planning and capabilities documentation (GAMEPLANS baseline updated to accurate 0.5+ reality, CURRENT_CAPABILITIES.md framing modernized).
- Systematic cleanup of outdated "future/planned" language across docs and examples.
- Added `ReferenceData.list_geometric_supported()` helper for transparency on current geometric coverage.
- Created high-value new Example 10 (realistic long-femur coaching scenario using personalized multi-position geometric + WeeklyProgram.compare()).
- Improved geometric fallback messaging in builders (clearer notes when user requests geometric but no estimator exists).
- Light internal refactor of `analyze_multi_position` (extracted `_detect_geometric_usage` and `_assemble_multi_position_aggregates` helpers, significantly reducing method length while preserving full behavior).
- Multiple micro UX and error message improvements.
- New flagship example + full examples set audited and kept healthy.
- Continued dense AGENT_FEEDBACK entries on the polish process and autonomy.

**Verification**: All tests green, all examples (including new #10) run cleanly, broad CLI matrix exercised.

This phase moves the project from "powerful but still rough around the edges" to "polished and consistent" on the path to v1.0.

