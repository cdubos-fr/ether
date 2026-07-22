set shell := ["zsh", "-uc"]

alias list := default

# Show list of availables recipes"
default:
    @just --list

help cmd:
    @just --usage {{ cmd }}

# Start the ether web app (autoreload)
run:
    @uv run ether index "$ETHER_PROJECT_ROOT"
    @uv run ether serve --reload

# Run all checks
checks:
    @echo "Running dedicated hooks"
    -@uv run prek run trailing-whitespace end-of-file-fixer \
    check-yaml check-toml debug-statements \
    check-merge-conflict  mixed-line-ending
    @echo "Running Tox checks"
    @tox -q

# Run check command
[arg('cmd', pattern='lint|types|docs|security|test')]
check cmd:
    tox -e {{ cmd }} -q

# Run formatters
format:
    @uv run ruff format
    @uv run ruff check --fix
    @uv run ssort
    @uv run zizmor --fix=all .
    @uv run just --fmt

# Manage the documentation
[arg('cmd', pattern='build|serve')]
docs cmd:
    @uv run zensical {{ cmd }}

# Clear cache and temporary files
clean:
    @find . -type d -name .venv -exec rm -rf {} +
    @find . -type d -name __pycache__ -exec rm -rf {} +
    @find . -type d -name .ruff_cache -exec rm -rf {} +
    @find . -type d -name dist -exec rm -rf {} +
    @find . -type d -name build -exec rm -rf {} +
    @find . -type d -name .pytest_cache -exec rm -rf {} +
    @find . -type d -name "*.egg-info" -exec rm -rf {} +
    @find . -type d -name .mypy_cache -exec rm -rf {} +
    @find . -type d -name .tox -exec rm -rf {} +
    @find . -type d -name site -exec rm -rf {} +
    @find . -type f -name .coverage -exec rm -rf {} +
    @find . -type d -name result -exec rm -rf {} +

# Build package
build:
    @uv build

# Bump version
release-version:
    @uv run cz bump
