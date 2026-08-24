# Contributing Guidelines

Thank you for contributing to CompassX! This guide covers our development workflow, coding standards, and documentation guidelines.

---

## Development Workflow

- **Create a Feature Branch**:
  ```bash
  git checkout -b feature/your-feature-name
  ```
- **Follow Code Conventions**:
  - Backend: Python 3.11 with PEP 8 standards, type annotations, and docstrings.
  - Frontend: React + TypeScript with strict type checking and ESLint rules.
- **Run Automated Tests**:
  - Backend tests: `pytest` in `backend/`.
  - Frontend linting: `npm run lint` in `frontend/`.

---

## Writing & Previewing Documentation

We follow the **Docs-as-Code** philosophy: any new feature or architectural change must include corresponding documentation updates.

### Install Documentation Tools

```bash
pip install -r requirements-docs.txt
```

### Run Local Documentation Server

```bash
python -m mkdocs serve -a localhost:8008
```

Open `http://localhost:8008` in your browser. As you edit markdown files in `docs/`, the browser will automatically live-reload.

### Verify Links & Syntax

Before submitting a Pull Request, run the strict build test to ensure there are no broken links or formatting errors:

```bash
mkdocs build --strict
```

---

## Pull Request Checklist

- [ ] Code builds cleanly and passes all unit tests.
- [ ] Documentation updated in `docs/` for any new endpoints, configuration options, or features.
- [ ] `mkdocs build --strict` completes with zero warnings or errors.
- [ ] PR title is descriptive and follows conventional commit standards.
