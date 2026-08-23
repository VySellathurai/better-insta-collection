VAULT   ?= $(PWD)/Vault
COOKIES ?=
MODELE  ?= small
FILE    ?=

_cookies = $(if $(COOKIES),--cookies $(COOKIES),)
_modele  = $(if $(MODELE),--modele $(MODELE),)
_limite  = $(if $(LIMITE),--limite $(LIMITE),)

.DEFAULT_GOAL := help

.PHONY: help install lint format typecheck check pre-commit \
        ingest graphe vault telegram

help:
	@echo "Usage: make <target> [VAR=value ...]"
	@echo ""
	@echo "Setup"
	@echo "  install       Install dependencies with uv"
	@echo "  pre-commit    Install git pre-commit hooks"
	@echo ""
	@echo "Code quality"
	@echo "  lint          ruff check (report only)"
	@echo "  format        ruff format (auto-fix)"
	@echo "  typecheck     mypy --strict on all scripts"
	@echo "  check         lint + typecheck (same as CI)"
	@echo ""
	@echo "Pipeline"
	@echo "  ingest        Ingest links   FILE=links.txt [COOKIES=firefox] [LIMITE=20]"
	@echo "  graphe        Build graph    [VAULT=./Vault]"
	@echo "  vault         Generate HTML  (reads Vault/index.md)"
	@echo "  telegram      Poll Telegram  [VAULT=./Vault] [COOKIES=firefox] [LIMITE=20]"
	@echo ""
	@echo "Variables (defaults shown):"
	@echo "  VAULT=$(VAULT)"
	@echo "  MODELE=$(MODELE)   (tiny | base | small | medium)"

# ── setup ────────────────────────────────────────────────────────────────────

install:
	uv sync --group dev

pre-commit:
	pre-commit install

# ── code quality ─────────────────────────────────────────────────────────────

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy ingest.py graphe.py generate_vault.py telegram_inbox.py

check: lint typecheck

# ── pipeline ─────────────────────────────────────────────────────────────────

ingest:
ifndef FILE
	$(error FILE is required — usage: make ingest FILE=links.txt)
endif
	uv run python ingest.py $(FILE) --vault $(VAULT) $(_cookies) $(_modele) $(_limite)

graphe:
	uv run python graphe.py --vault $(VAULT)

vault:
	uv run python generate_vault.py

telegram:
	uv run python telegram_inbox.py --vault $(VAULT) $(_cookies) $(_modele) $(_limite)
