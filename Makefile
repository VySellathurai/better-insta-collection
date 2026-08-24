VAULT         ?= $(PWD)/Vault
COOKIES       ?=
WHISPER_MODEL ?= small
FILE          ?=
LLM_MODEL     ?= qwen2.5:7b
BATCH         ?= 25
BACKOFFICE    ?= src/backoffice

_cookies      = $(if $(COOKIES),--cookies $(COOKIES),)
_whisper_model = $(if $(WHISPER_MODEL),--whisper-model $(WHISPER_MODEL),)
_limite       = $(if $(LIMITE),--limite $(LIMITE),)
_llm_model    = $(if $(LLM_MODEL),--llm-model $(LLM_MODEL),)
_npm          = npm --prefix $(BACKOFFICE) run

.DEFAULT_GOAL := help

.PHONY: help \
        install lint format typecheck check pre-commit \
        collect digest digest-dry publish graph telegram \
        bo-install bo-env bo-images-link bo-setup \
        bo-db-up bo-db-down bo-db-generate bo-db-migrate bo-db-seed bo-refresh \
        bo-dev bo-build bo-start bo-lint bo-typecheck bo-check

help:
	@echo "Usage: make <target> [VAR=value ...]"
	@echo ""
	@echo "Setup"
	@echo "  install         Install Python dependencies with uv"
	@echo "  pre-commit      Install git pre-commit hooks"
	@echo ""
	@echo "Code quality (Python pipeline)"
	@echo "  lint            ruff check (report only)"
	@echo "  format          ruff format (auto-fix)"
	@echo "  typecheck       mypy --strict on all scripts"
	@echo "  check           lint + typecheck (same as CI)"
	@echo ""
	@echo "Pipeline (src/reels_vault — collect, digest, publish)"
	@echo "  collect         Collect links     FILE=links.txt [COOKIES=firefox] [LIMITE=20]"
	@echo "  digest          Digest raw fiches [LLM_MODEL=qwen2.5:7b] [BATCH=25]"
	@echo "  digest-dry      Preview digest    (no writes)"
	@echo "  graph           Build graph       [VAULT=./Vault]"
	@echo "  publish         Generate gallery  (reads Vault/index.md, writes gallery.html)"
	@echo "  telegram        Poll Telegram     [VAULT=./Vault] [COOKIES=firefox] [LIMITE=20]"
	@echo ""
	@echo "Backoffice (src/backoffice — Next.js + Postgres, reads the same Vault)"
	@echo "  bo-setup        First-time bootstrap: install, .env, images symlink, db up, migrate, seed"
	@echo "  bo-install      Install Node dependencies (npm)"
	@echo "  bo-db-up        Start Postgres (Docker), wait until healthy"
	@echo "  bo-db-down      Stop Postgres"
	@echo "  bo-db-generate  Generate a Drizzle migration from db/schema.ts"
	@echo "  bo-db-migrate   Apply pending Drizzle migrations"
	@echo "  bo-db-seed      Reload Vault data into Postgres (safe to re-run)"
	@echo "  bo-refresh      publish + bo-db-seed — resync gallery.html and Postgres together"
	@echo "  bo-dev          Run the Next.js dev server (http://localhost:3000)"
	@echo "  bo-build        Production build"
	@echo "  bo-start        Run the production build (after bo-build)"
	@echo "  bo-lint         eslint ."
	@echo "  bo-typecheck    tsc --noEmit"
	@echo "  bo-check        bo-lint + bo-typecheck"
	@echo ""
	@echo "Variables (defaults shown):"
	@echo "  VAULT=$(VAULT)"
	@echo "  WHISPER_MODEL=$(WHISPER_MODEL) (tiny | base | small | medium)"
	@echo "  LLM_MODEL=$(LLM_MODEL)         (qwen2.5:7b | qwen2.5:3b | mistral:7b)"
	@echo "  BATCH=$(BATCH)                 fiches par session"
	@echo "  BACKOFFICE=$(BACKOFFICE)       Next.js/Postgres subproject path"

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

# ── backoffice: setup ────────────────────────────────────────────────────────
# Namespaced with a bo- prefix so its npm/docker world stays visibly separate
# from the uv/Python world above, in the same Makefile, with no target
# collisions (both need e.g. an "install").

bo-install:
	npm --prefix $(BACKOFFICE) install

bo-env:
	@test -f $(BACKOFFICE)/.env || cp $(BACKOFFICE)/.env.example $(BACKOFFICE)/.env
	@echo "$(BACKOFFICE)/.env ready"

bo-images-link:
	@if [ ! -L $(BACKOFFICE)/public/images ]; then \
		rm -rf $(BACKOFFICE)/public/images; \
		ln -s ../../../Vault/images $(BACKOFFICE)/public/images; \
		echo "created $(BACKOFFICE)/public/images -> Vault/images"; \
	fi

bo-setup: bo-install bo-env bo-images-link bo-db-up bo-db-generate bo-db-migrate bo-db-seed
	@echo "Backoffice ready — run 'make bo-dev' and open http://localhost:3000"

# ── backoffice: database ─────────────────────────────────────────────────────

bo-db-up:
	$(_npm) db:up
	@cd $(BACKOFFICE) && for i in $$(seq 1 60); do \
		docker compose ps postgres --format json | grep -q '"Health":"healthy"' && exit 0; \
		sleep 1; \
	done; \
	echo "Postgres did not become healthy within 60s — check 'docker compose logs postgres'" >&2; exit 1
	@echo "Postgres healthy"

bo-db-down:
	$(_npm) db:down

bo-db-generate:
	$(_npm) db:generate

bo-db-migrate:
	$(_npm) db:migrate

bo-db-seed:
	$(_npm) db:seed

bo-refresh: publish bo-db-seed

# ── backoffice: app ──────────────────────────────────────────────────────────

bo-dev:
	$(_npm) dev

bo-build:
	$(_npm) build

bo-start:
	$(_npm) start

bo-lint:
	$(_npm) lint

bo-typecheck:
	$(_npm) typecheck

bo-check: bo-lint bo-typecheck
