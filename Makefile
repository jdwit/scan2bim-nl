.DEFAULT_GOAL := help
UV ?= uv

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Install the project and dev tools into .venv
	$(UV) sync --group dev

test: ## Run the test suite
	$(UV) run pytest

cov: ## Run tests with a coverage report
	$(UV) run pytest --cov=scan2bim --cov-report=term-missing

lint: ## Check formatting and lint rules
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt: ## Format the code
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

types: ## Type check
	$(UV) run mypy

check: lint test ## What CI runs

clean: ## Remove build and cache artefacts
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage

.PHONY: help setup test cov lint fmt types check clean
