VAULT         ?= $(PWD)/Vault
COOKIES       ?=
WHISPER_MODEL ?= small
FILE          ?=
LIMIT         ?=
LIMITE        ?= $(LIMIT)
COLLECTION    ?=
LLM_MODEL     ?= qwen2.5:7b
DATABASE_URL  ?= postgres://backoffice:changeme@localhost:5433/backoffice
BACKOFFICE    ?= src/backoffice
COLLECTIONS_STUDIO ?= src/collections-studio

_cookies      = $(if $(COOKIES),--cookies $(COOKIES),)
_whisper_model = $(if $(WHISPER_MODEL),--whisper-model $(WHISPER_MODEL),)
_limite       = $(if $(LIMITE),--limite $(LIMITE),)
_collection   = $(if $(COLLECTION),--collection "$(COLLECTION)",)
_llm_model    = $(if $(LLM_MODEL),--llm-model $(LLM_MODEL),)
_npm          = npm --prefix $(BACKOFFICE) run
_npm_cs       = npm --prefix $(COLLECTIONS_STUDIO) run

.DEFAULT_GOAL := help

.PHONY: help \
        install lint format typecheck check pre-commit \
        pipeline collections telegram \
        bo-install bo-env bo-images-link bo-setup \
        bo-db-up bo-db-down bo-db-generate bo-db-migrate \
        bo-dev bo-build bo-start bo-lint bo-typecheck bo-check \
        cs-install cs-env cs-images-link cs-setup cs-dev cs-build cs-start cs-lint cs-typecheck cs-check

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
	@echo "Pipeline (src/reels_pipeline — collect+transcribe, images, enrich, publish to Postgres)"
	@echo "  pipeline        Run the pipeline  FILE=links.txt [COOKIES=firefox] [LIMIT=20]"
	@echo "                  [COLLECTION=Comprendre] [LLM_MODEL=qwen2.5:7b] [DATABASE_URL=postgres://...] [DRY_RUN=1]"
	@echo "  collections     List collection names + link counts  [FILE=saved_collections.json]"
	@echo "  telegram        Poll Telegram     [VAULT=./Vault] [COOKIES=firefox] [LIMIT=20]"
	@echo ""
	@echo "Backoffice (src/backoffice — Next.js + Postgres; the pipeline writes here directly)"
	@echo "  bo-setup        First-time bootstrap: install, .env, images symlink, db up, migrate"
	@echo "  bo-install      Install Node dependencies (npm)"
	@echo "  bo-db-up        Start Postgres (Docker), wait until healthy"
	@echo "  bo-db-down      Stop Postgres"
	@echo "  bo-db-generate  Generate a Drizzle migration from db/schema.ts"
	@echo "  bo-db-migrate   Apply pending Drizzle migrations"
	@echo "  bo-dev          Run the Next.js dev server (http://localhost:3000)"
	@echo "  bo-build        Production build"
	@echo "  bo-start        Run the production build (after bo-build)"
	@echo "  bo-lint         eslint ."
	@echo "  bo-typecheck    tsc --noEmit"
	@echo "  bo-check        bo-lint + bo-typecheck"
	@echo ""
	@echo "Collections Studio (src/collections-studio — pick a saved collection, digest up to N posts)"
	@echo "  cs-setup        First-time bootstrap: install, .env, images symlink"
	@echo "  cs-install      Install Node dependencies (npm)"
	@echo "  cs-images-link  Symlink public/images -> Vault/images"
	@echo "  cs-dev          Run the Next.js dev server (http://localhost:3100)"
	@echo "  cs-build        Production build"
	@echo "  cs-start        Run the production build (after cs-build)"
	@echo "  cs-lint         eslint ."
	@echo "  cs-typecheck    tsc --noEmit"
	@echo "  cs-check        cs-lint + cs-typecheck"
	@echo ""
	@echo "Variables (defaults shown):"
	@echo "  VAULT=$(VAULT)"
	@echo "  WHISPER_MODEL=$(WHISPER_MODEL) (tiny | base | small | medium)"
	@echo "  LLM_MODEL=$(LLM_MODEL)         (qwen2.5:7b | qwen2.5:3b | mistral:7b)"
	@echo "  DATABASE_URL=$(DATABASE_URL)"
	@echo "  BACKOFFICE=$(BACKOFFICE)       Next.js/Postgres subproject path"
	@echo "  COLLECTIONS_STUDIO=$(COLLECTIONS_STUDIO)  Next.js collection-picker subproject path"

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

pipeline:
ifndef FILE
	$(error FILE is required — usage: make pipeline FILE=links.txt)
endif
	uv run reels-pipeline $(FILE) --vault $(VAULT) $(_cookies) $(_whisper_model) $(_limite) \
		$(_llm_model) $(_collection) --database-url $(DATABASE_URL) $(if $(DRY_RUN),--dry-run,)

collections:
	uv run reels-collections $(if $(FILE),$(FILE),your_instagram_activity/saved/saved_collections.json)

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

bo-setup: bo-install bo-env bo-images-link bo-db-up bo-db-generate bo-db-migrate
	@echo "Backoffice ready — run 'make bo-dev' and open http://localhost:3000"
	@echo "Nothing to seed: run 'make pipeline FILE=links.txt' to populate Postgres directly."

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

# ── collections-studio ───────────────────────────────────────────────────────
# Namespaced with a cs- prefix, same pattern as bo- above. File-based (reads/
# writes Vault/ directly) — no Docker/Postgres dependency for this one.

cs-install:
	npm --prefix $(COLLECTIONS_STUDIO) install

cs-env:
	@test -f $(COLLECTIONS_STUDIO)/.env || cp $(COLLECTIONS_STUDIO)/.env.example $(COLLECTIONS_STUDIO)/.env
	@echo "$(COLLECTIONS_STUDIO)/.env ready"

cs-images-link:
	@if [ ! -L $(COLLECTIONS_STUDIO)/public/images ]; then \
		rm -rf $(COLLECTIONS_STUDIO)/public/images; \
		mkdir -p $(COLLECTIONS_STUDIO)/public; \
		ln -s ../../../Vault/images $(COLLECTIONS_STUDIO)/public/images; \
		echo "created $(COLLECTIONS_STUDIO)/public/images -> Vault/images"; \
	fi

cs-setup: cs-install cs-env cs-images-link
	@echo "Collections Studio ready — run 'make cs-dev' and open http://localhost:3100"

cs-dev:
	$(_npm_cs) dev

cs-build:
	$(_npm_cs) build

cs-start:
	$(_npm_cs) start

cs-lint:
	$(_npm_cs) lint

cs-typecheck:
	$(_npm_cs) typecheck

cs-check: cs-lint cs-typecheck
