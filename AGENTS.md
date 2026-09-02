# Repository Guidelines

## Project Structure & Module Organization

The distributable skill lives in `content-to-editable-ppt/`. Python and Node.js runtime entry points are under `content-to-editable-ppt/scripts/`; JSON contracts are in `schemas/`, agent role definitions in `agents/`, and runtime guidance in `references/`. Repository-level design decisions and implementation plans live in `docs/`. Automated tests are in `tests/runtime/`, while durable validation artifacts belong in `reports/`. Treat `work/`, virtual environments, caches, and generated runtime manifests as local-only outputs.

## Build, Test, and Development Commands

Install the pinned runtimes before development:

```powershell
python -m pip install -r content-to-editable-ppt/scripts/requirements.txt
pnpm --dir content-to-editable-ppt/scripts install --frozen-lockfile
```

Run the complete regression suite with:

```powershell
python -m unittest discover -s tests/runtime -p "test_*.py"
```

Use `python content-to-editable-ppt/scripts/run.py --help` to inspect the multi-slide entry point. PowerPoint integration requires Windows and Microsoft PowerPoint:

```powershell
$env:IVT_RUN_POWERPOINT_SMOKE = "1"
python -m unittest tests.runtime.test_reconstruction_plan_compiler.ReconstructionPlanCompilerTests.test_powerpoint_single_page_smoke
```

Run `git diff --check` before committing.

## Coding Style & Naming Conventions

Use four-space indentation, type hints, `snake_case` functions, and `UPPER_CASE` constants in Python. Keep deterministic logic separate from filesystem or CLI adapters. JavaScript uses ESM, two-space indentation, `camelCase`, and explicit imports. Preserve existing JSON schema versions and structured error codes. Name schemas and contract artifacts with kebab-case; name Python tests `test_<behavior>.py` and test methods `test_<expected_behavior>`.

## Testing Guidelines

Tests use Python’s `unittest`; no percentage coverage target is enforced. Every bug fix or contract change needs a focused regression test, plus the full runtime suite. Prefer temporary directories and in-memory fixtures. Keep Planner/Reviewer tests deterministic unless a task explicitly calls for live-agent evidence. Visual or PowerPoint changes should include rendered output and QA evidence under `reports/`.

## Commit & Pull Request Guidelines

Follow the repository’s Conventional Commit pattern: `feat:`, `fix:`, `test:`, or `docs:` followed by an imperative summary. Keep commits scoped to one architectural step. Pull requests should describe the affected runtime path, contract compatibility, and exact validation commands. Link relevant issues or ADRs, and attach rendered screenshots for visual changes. Do not commit secrets, absolute machine paths, or files generated under `work/`.
