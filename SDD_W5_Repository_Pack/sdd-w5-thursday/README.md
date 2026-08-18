# Thursday — Full-Day Client Scenario Lab

`order_service_legacy.py` is deliberately 600+ lines and mixes multiple responsibilities.

## Phase 1 — Characterize
1. Do not refactor first.
2. Write tests that capture current behaviour.
3. Aim for 80%+ coverage.
4. Complete `dependency_map_template.md`.

Suggested command:
```bash
pytest sdd-w5-thursday --cov=sdd-w5-thursday --cov-report=term-missing
```

## Phase 2 — Identify and Plan
Record SOLID violations, pattern opportunities, and a sequenced refactoring plan in `SPEC.md`.

## Phase 3 — Refactor
Keep commits small and tests green. Apply naming/readability rules plus at least one pattern.

## Phase 4 — Capstone Increment
Port the clean skeleton into `capstone/`; ensure interfaces, directory structure, placeholder implementations, and final SPEC sections are present.
