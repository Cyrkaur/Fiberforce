# Project Rules for FiberForce

This file contains instructions for AI agents (especially Grok Build) working on this repository.

## Primary Goals

1. Build a high-quality, scientifically grounded tool for advanced lifters.
2. Deliberately generate high-quality, specific feedback on Grok Build's capabilities through this project.

## Working Style

- **Dual Tracking**: Always maintain both the software quality and the agent performance observations (see `AGENT_FEEDBACK.md`).
- Use the `todo_write` tool for any multi-step work.
- Prefer **Plan Mode** when tackling ambiguous or architecturally significant tasks.
- When making significant changes, consider whether a subagent (reviewer, researcher, implementer) would improve quality or generate better feedback.

## Code Quality Expectations

- Keep the core domain logic clean and well-tested.
- Use type hints.
- Prefer small, focused modules.
- Document non-obvious biomechanical or modeling decisions.

## Feedback Mindset

When working on this project, actively notice and record:
- Where the agent excels
- Where friction or repeated mistakes occur
- Long-term context management behavior
- Quality of planning and architectural decisions
- Effectiveness of subagents and personas

Record observations in `AGENT_FEEDBACK.md` with context.

## Current Scope (as of May 2026)

- Peak force calculations only (no dynamic ROM modeling yet)
- Primary compound lifts
- Personalized user measurements supported
- Focus on regional muscle targeting + force requirements

## Communication

- Be direct and structured.
- When proposing architecture or major decisions, present clear options with trade-offs.
- Surface uncertainty early.