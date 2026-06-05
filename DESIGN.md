# FiberForce — Design Document (v0.1.1 Foundation)

## Project Vision

FiberForce aims to be a high-fidelity, personalized biomechanical modeling tool that helps serious lifters target specific muscle sub-regions with precision by understanding the force and mechanical demands of different exercise setups.

## Current Scope for v0.1.1 (Foundation Lock)

**Goal of this version**: Stabilize the core domain models and deliver the first genuinely usable end-to-end experience for one primary lift (Bench Press), with a focus on the sternal fibers of the pectoralis major as the driving example.

**In Scope for v0.1.1**:
- Thorough audit and hardening of all existing domain models.
- Improved robustness and error handling in the `SimplePeakForceCalculator`.
- Expanded reference moment arm data for multiple bench press positions.
- Rich example data for realistic bench press configurations.
- A polished, useful CLI command for analyzing bench press setups.
- Clear documentation of modeling assumptions and limitations.
- Active, high-quality logging in `AGENT_FEEDBACK.md`.

**Explicitly Out of Scope for v0.1.1**:
- Any lifts other than Bench Press variations.
- Dynamic force modeling across the full ROM.
- Sensitivity analysis engine.
- Comprehensive test suite.
- Major new features.

## Core Domain Concepts (Stabilized in v0.1.1)

- `UserAnthropometry`
- `Muscle`, `MuscleRegion`, `MuscleArchitecture`, `MuscleAttachment`
- `PrimaryLift`, `LiftConfiguration`, `JointAngles`, `ExternalLoad`
- `Pose`, `AnalyzedPosition`
- `Subject`
- Basic biomechanics primitives (`MomentArm`, `Lever`, etc.)

## Technology

Python CLI + Library (strong emphasis on clean domain modeling).

## Success Criteria for v0.1.1

- All core models are consistent, well-documented, and have good helper methods.
- The calculator can run on realistic example data without crashing and produces plausible results.
- A user can run a CLI command and get useful output for bench press analysis.
- Significant, honest observations have been recorded in `AGENT_FEEDBACK.md`.

*This document will be updated per micro-version.*