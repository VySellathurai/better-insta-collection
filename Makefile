VAULT         ?= $(PWD)/Vault
COOKIES       ?=
WHISPER_MODEL ?= small
FILE          ?=
LLM_MODEL     ?= qwen2.5:7b
BATCH         ?= 25

_cookies      = $(if $(COOKIES),--cookies $(COOKIES),)
_whisper_model = $(if $(WHISPER_MODEL),--whisper-model $(WHISPER_MODEL),)
_limite       = $(if $(LIMITE),--limite $(LIMITE),)
_llm_model    = $(if $(LLM_MODEL),--llm-model $(LLM_MODEL),)

.DEFAULT_GOAL := help

.PHONY: help install lint format typecheck check pre-commit \
        collect digest digest-dry publish graph telegram

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
	@echo "  collect       Collect links     FILE=links.txt [COOKIES=firefox] [LIMITE=20]"
	@echo "  digest        Digest raw fiches [LLM_MODEL=qwen2.5:7b] [BATCH=25]"
	@echo "  digest-dry    Preview digest    (no writes)"
	@echo "  graph         Build graph       [VAULT=./Vault]"
	@echo "  publish       Generate gallery  (reads Vault/index.md)"
	@echo "  telegram      Poll Telegram     [VAULT=./Vault] [COOKIES=firefox] [LIMITE=20]"
	@echo ""
	@echo "Variables (defaults shown):"
	@echo "  VAULT=$(VAULT)"
	@echo "  WHISPER_MODEL=$(WHISPER_MODEL) (tiny | base | small | medium)"
	@echo "  LLM_MODEL=$(LLM_MODEL)         (qwen2.5:7b | qwen2.5:3b | mistral:7b)"
	@echo "  BATCH=$(BATCH)                 fiches par session"

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
	uv run mypy src/

check: lint typecheck

# ── pipeline ─────────────────────────────────────────────────────────────────

collect:
ifndef FILE
	$(error FILE is required — usage: make collect FILE=links.txt)
endif
	uv run reels-collect $(FILE) --vault $(VAULT) $(_cookies) $(_whisper_model) $(_limite)

digest:
	uv run reels-digest --vault $(VAULT) $(_llm_model) --batch $(BATCH)

digest-dry:
	uv run reels-digest --vault $(VAULT) $(_llm_model) --batch $(BATCH) --dry-run

graph:
	uv run reels-graph --vault $(VAULT)

publish:
	uv run reels-publish --vault $(VAULT)

telegram:
	uv run reels-telegram --vault $(VAULT) $(_cookies) $(_whisper_model) $(_limite)
