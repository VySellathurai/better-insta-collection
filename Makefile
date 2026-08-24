VAULT     ?= $(PWD)/Vault
COOKIES   ?=
MODELE    ?= small
FILE      ?=
LLM_MODEL ?= qwen2.5:7b
BATCH     ?= 25

_cookies   = $(if $(COOKIES),--cookies $(COOKIES),)
_modele    = $(if $(MODELE),--modele $(MODELE),)
_limite    = $(if $(LIMITE),--limite $(LIMITE),)
_llmmodele = $(if $(LLM_MODEL),--model $(LLM_MODEL),)

.DEFAULT_GOAL := help

.PHONY: help install lint format typecheck check pre-commit \
        ingest graphe vault telegram index index-dry

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
	@echo "  ingest        Ingest links     FILE=links.txt [COOKIES=firefox] [LIMITE=20]"
	@echo "  index         Run Étape 5      [LLM_MODEL=qwen2.5:7b] [BATCH=25]"
	@echo "  index-dry     Preview index    (no writes)"
	@echo "  graphe        Build graph      [VAULT=./Vault]"
	@echo "  vault         Generate HTML    (reads Vault/index.md)"
	@echo "  telegram      Poll Telegram    [VAULT=./Vault] [COOKIES=firefox] [LIMITE=20]"
	@echo ""
	@echo "Variables (defaults shown):"
	@echo "  VAULT=$(VAULT)"
	@echo "  MODELE=$(MODELE)       (tiny | base | small | medium)"
	@echo "  LLM_MODEL=$(LLM_MODEL) (qwen2.5:7b | qwen2.5:3b | mistral:7b)"
	@echo "  BATCH=$(BATCH)         fiches par session"

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
	uv run mypy ingest.py graphe.py generate_vault.py telegram_inbox.py index_agent.py

check: lint typecheck

# ── pipeline ─────────────────────────────────────────────────────────────────

ingest:
ifndef FILE
	$(error FILE is required — usage: make ingest FILE=links.txt)
endif
	uv run python ingest.py $(FILE) --vault $(VAULT) $(_cookies) $(_modele) $(_limite) $(_llmmodele)

index:
	uv run python index_agent.py --vault $(VAULT) --model $(LLM_MODEL) --batch $(BATCH)

index-dry:
	uv run python index_agent.py --vault $(VAULT) --model $(LLM_MODEL) --batch $(BATCH) --dry-run

graphe:
	uv run python graphe.py --vault $(VAULT)

vault:
	uv run python generate_vault.py

telegram:
	uv run python telegram_inbox.py --vault $(VAULT) $(_cookies) $(_modele) $(_limite)
