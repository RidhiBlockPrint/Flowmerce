# ADR 0001: Python-first development

- Status: approved (owner instruction, 2026-10-29)
- Date: 2026-10-29

## Decision
Python is the primary language. Any other programming language requires an explanation and the owner's explicit approval before code is written. Markdown and ordinary configuration files are permitted.

## Rationale
One language keeps the codebase maintainable and hand-over friendly.

## Alternatives considered
Polyglot stack (as in planning v0.1, which listed a Next.js dashboard and SQL schema). Superseded for those parts by ADR 0002.

## Advantages
Single toolchain, simpler hiring and review.

## Disadvantages
Rich web UIs are harder in pure Python.

## Consequences and dependencies
See ADR 0002 for approved exceptions. Dependencies are kept minimal; the foundation has none at runtime.
