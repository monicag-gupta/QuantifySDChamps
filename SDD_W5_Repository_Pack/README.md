# Quantiphi Campus Training — SD Track — Week 5 Repository Pack

**Week 5: Software Design & Clean Code**  
Domain: **RetailCo Order Fulfilment**

This repository pack implements the learner-facing starter assets and instructor/reference solutions described in the Week 5 Learner Workbook.

## Exercise map

| Workbook item | Starter asset | Reference solution |
|---|---|---|
| Exercise 1 — Domain Modelling | `sdd-w5-monday/domain_model_starter.py`, root `SPEC.md` | `solutions/monday/SolutionEx01domain_model.py`, `SolutionEx01SPEC.md` |
| Exercise 2 — Refactor a God Class | `sdd-w5-monday/god_class_starter.py` | `solutions/monday/SolutionEx02god_class_starter.py` + tests/SPEC |
| Exercise 3 — Rename & Restructure | `sdd-w5-tuesday/payment_utils_dirty.py` | `solutions/tuesday/SolutionEx03payment_utils_dirty.py` + tests/SPEC |
| Exercise 4 — SOLID Violation Hunt | `sdd-w5-wednesday/solid_violations.py` | `solutions/wednesday/SolutionEx04solid_violations.py` + tests/SPEC |
| Exercise 5 — Apply a Design Pattern | `sdd-w5-wednesday/design_pattern_starter.py` | `solutions/wednesday/SolutionEx05design_pattern_starter.py` + tests/SPEC |
| Thursday full-day lab (unnumbered) | `sdd-w5-thursday/order_service_legacy.py` | `solutions/thursday/SolutionEx00order_service_legacy.py` + characterization tests/SPEC |
| Exercise 6 — SBI Role-play | `sdd-w5-friday/SBI_role_play.md` | `solutions/friday/SolutionEx06SBI_role_play.md` |
| Capstone Week 5 increment | `capstone/` | `solutions/capstone/SolutionEx00capstone_*.py` + SPEC/test |

> `Ex00` is intentionally reserved for the workbook's **unnumbered Thursday lab / capstone integration** so the workbook's numbered Exercises 1–6 remain unchanged.

## Setup

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## SDD discipline

1. Update `SPEC.md` **before** the corresponding production code change.
2. Make small commits and keep tests green.
3. Record design decisions using Problem / Options Considered / Decision / Consequences.
4. Treat generated AI code as a draft: review, test, and document it.

## Suggested learner commit sequence

```text
spec: document RetailCo domain model
refactor: split OrderManager responsibilities
refactor: clean payment utility naming and functions
spec: record SOLID review and payment strategy DDR
refactor: characterize and split legacy order service
feat: port clean skeleton into capstone
```

## Notes for facilitators

- Starter tests preserve current behaviour; learners should add the tests required by each exercise.
- Reference solutions are examples, not the only acceptable implementation.
- Thursday's legacy file is deliberately long and contains design smells. Learners should characterize behaviour before refactoring.
