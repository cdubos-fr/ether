[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Checked with ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)

# ether

A tool to manage world building and story writing. `ether` indexes an ether
**project root** — a folder with a fixed shape (`univers/`, `stories/`, `config/`;
see `ether.project.find_issues` for the exact rules ether enforces, and the
convention documented in `saga-eveil-univers/README.md`):

```
<project-root>/
  univers/<category>/{_index.md,_template.md,<subject>.md}
  stories/_index.md, <saga>/_manifest.md, <saga>/<tome>/<act>/_chapter/<chapitre>.md
  config/
```

Univers fiches (frontmatter `id/type/name/aliases/status/tags/related/updated`)
build a bidirectional link graph from the `related:` field. `ether` provides:

- **Browse** — categories, fiches, outgoing `related` links and computed backlinks.
- **Edit** — in place, on the markdown itself (whole-fiche or a single `##` section),
  preserving the file's existing YAML formatting.
- **AI-assisted creation** — draft a new fiche (from a category's `_template.md`) or
  a new/edited section, reviewed by you before it's saved.
- **Style manifest** (`/style`) — a per-saga tone/intention/prose-rules file
  (`stories/<saga>/_manifest.md`), injected into every generation prompt.
- **Stories index** — sagas/one-shots → tomes → acts → chapters, indexed from
  `stories/` the same way univers fiches are (see `ether.stories`).
- **Sequencer** (`/sequencer`) — Tome → Acte → Chapitre → Partie, with AI-assisted
  scene generation pulling context from linked fiches and prior validated scenes.

The runtime SQLite index (`data/ether.db`) is a **disposable cache**: markdown is
always the source of truth, and `ether index` rebuilds it from scratch at any time.

## Setup

```bash
uv sync --group dev
```

Required: `ETHER_PROJECT_ROOT`, pointing at an ether project root, e.g.:

```bash
export ETHER_PROJECT_ROOT=/path/to/saga-eveil-univers
```

Optional: `ETHER_DB_PATH` (default `./data/ether.db`), `AI_BACKEND`
(`stub` \| `gemini` \| `claude`, default `stub` — no live API call unless explicitly
configured), `GEMINI_API_KEY`/`GEMINI_MODEL`, `ANTHROPIC_API_KEY`/`CLAUDE_MODEL`,
`ETHER_HOST`/`ETHER_PORT`.

## Run

```bash
uv run ether index "$ETHER_PROJECT_ROOT"   # build/refresh the index
just run                                    # http://127.0.0.1:8000, autoreload
```
