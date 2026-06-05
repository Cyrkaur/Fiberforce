# FiberForce — Scope of Work (v0.1 → v1.0)

This document defines the high-level contract for the project from the current state through a completed v1.0.

It exists to protect the "ground-up, deep biomechanics, personalized regional hypertrophy" vision while preventing scope explosion.

---

## Core Vision (Unchanging)

A high-fidelity, **personalized biomechanical modeling tool** that lets serious lifters understand the force demands on **specific muscle sub-regions** during primary compound lifts by providing their own anthropometric measurements.

Key non-negotiables:
- Users **must** be able to provide detailed personal measurements (bone lengths joint-to-joint, etc.)
- Focus on **regional** modeling (sternal vs clavicular pecs, upper vs lower glute max, etc.)
- Calculations are **peak force at static positions** (not full dynamic ROM in v1)
- Primary lifts only for v1.0

---

## Version Roadmap (High Level)

### v0.1.x — Foundation & First Useful Tool (Current Focus)

**v0.1.1** (Complete)
- Solid domain models (Subject, Pose, MuscleAttachment, Anthropometry, etc.)
- Working `SimplePeakForceCalculator`
- `fiberforce analyze bench` with personalization
- Good examples + reference data for bench
- `docs/how-the-model-works.md`
- 10+ tests + strong feedback logging

**v0.1.2** (In Progress — This Run)
- Full CLI support for Bench + Squat + basic OHP
- Confidence scoring in results
- Expanded reference data + muscle regions for lower body and overhead
- Working squat analysis (high-bar/low-bar, glute & quad targets)
- Continued high-quality AGENT_FEEDBACK entries

**v0.1.3** — Reference Data & Validation
- Much richer reference tables (15-25+ literature-inspired values)
- Stronger validation + warnings when data is weak
- `ReferenceData` loader
- Better documentation of every assumption

**v0.1.4** — Sensitivity Analysis (first version)
- Single-variable "what if" (grip width, load, bar position, femur length, etc.)
- Tabular output

**v0.1.5** — Quality & Testing
- 20-30 meaningful tests
- Type checking (pyright/mypy)
- Basic CI

### v0.2.0 — First Major Release Candidate

- All three main lifts (Bench, Squat, OHP, + basic deadlift consideration)
- Multi-variable sensitivity
- Strong user-facing documentation ("How to use this for programming")
- Public README + installation story
- A motivated lifter can make non-obvious training decisions with the tool

### v0.3.0 – v0.5.0 — Mid Expansion

- Remaining primary lifts (Deadlift variations, etc.)
- Limited dynamic elements (bottom/mid/top force snapshots)
- More muscle groups
- AnalysisService layer
- Program-level insights (volume by region)
- First visualizations

### v0.6.0 – v0.8.0 — Deepening

- Real length-tension modeling
- User profile persistence
- Better multi-joint handling
- Educational explanations

### v0.9.0 – v1.0.0 — Polish & Completion

- Comprehensive documentation (user guide + modeling guide + limitations)
- High test coverage
- Clean public library API
- Final major agent feedback round
- Release-quality packaging

---

## Explicit Non-Goals (for v1.0)

- Full continuous dynamic ROM simulation
- Program generation / auto-programming
- Web UI or mobile app
- Non-primary lifts as first-class citizens
- Real-time coaching
- Medical / diagnostic claims

These can be considered post-v1 or as separate projects.

---

## Success Criteria for v1.0

A knowledgeable lifter who provides their own measurements can:
1. Get plausible, explainable peak force numbers for specific muscle regions on Bench, Squat, and Overhead Press variations.
2. Use the sensitivity and comparison tools to make better-informed decisions about grip, stance, bar position, and ROM emphasis.
3. Understand exactly where the model is weak (via confidence scores and explicit limitations).

---

## Dual Tracking Requirement (Hybrid Goal)

This project is deliberately a **hybrid test**:
- Ship genuinely high-quality, ambitious software in the weightlifting biomechanics domain.
- Simultaneously generate high-signal, specific feedback on Grok Build / agent capabilities (planning, autonomy, long-context execution, tool use, scope discipline, etc.).

Every major micro-version must produce meaningful additions to `AGENT_FEEDBACK.md`.

---

*Last updated during record-beating autonomous run (v0.1.2 push)*