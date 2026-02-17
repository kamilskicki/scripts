# Contributing

## Branching

- create focused branches per topic (`feat/...`, `fix/...`, `docs/...`)
- keep pull requests small and reviewable

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r YouTube/requirements.txt
pip install -e .[dev]
```

## Quality checks

```bash
ruff check YouTube
pytest
```

## Commit conventions

- `feat:` new functionality
- `fix:` bug fix
- `docs:` documentation-only changes
- `refactor:` behavior-preserving code cleanup
- `test:` test updates

## Pull request checklist

- include problem statement and scope
- include CLI examples for changed behavior
- update README/docs when flags, output, or workflows change
- pass CI on all supported Python versions
