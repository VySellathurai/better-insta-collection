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
MEME_MUSEUM   ?= src/meme-museum
MEME_MUSEUM_VAULT ?= $(PWD)/$(MEME_MUSEUM)/vault
MEME_MUSEUM_DATABASE_URL ?= postgres://meme_museum:changeme@localhost:5434/meme_museum
# Locked, not a user-overridable variable like COLLECTION above — mm-pipeline
# must never be pointable at a different collection.
MEME_MUSEUM_COLLECTION := Musée des Mêmes

_cookies      = $(if $(COOKIES),--cookies $(COOKIES),)
_whisper_model = $(if $(WHISPER_MODEL),--whisper-model $(WHISPER_MODEL),)
_limite       = $(if $(LIMITE),--limite $(LIMITE),)
_collection   = $(if $(COLLECTION),--collection "$(COLLECTION)",)
_llm_model    = $(if $(LLM_MODEL),--llm-model $(LLM_MODEL),)
_npm          = npm --prefix $(BACKOFFICE) run
_npm_cs       = npm --prefix $(COLLECTIONS_STUDIO) run
_npm_mm       = npm --prefix $(MEME_MUSEUM) run

.DEFAULT_GOAL := help

.PHONY: help \
        install lint format typecheck check pre-commit \
        pipeline collections telegram api jobs job \
        bo-install bo-env bo-images-link bo-setup \
        bo-db-up bo-db-down bo-db-generate bo-db-migrate \
        bo-dev bo-build bo-start bo-lint bo-typecheck bo-check \
        cs-install cs-env cs-images-link cs-setup cs-dev cs-build cs-start cs-lint cs-typecheck cs-check \
        mm-install mm-env mm-images-link mm-setup mm-pipeline \
        mm-db-up mm-db-down mm-db-generate mm-db-migrate \
        mm-dev mm-build mm-start mm-lint mm-typecheck mm-check

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
	@echo "  api             Serve the FastAPI trigger (POST /content/ingestor)  [API_HOST=127.0.0.1] [API_PORT=8000]"
	@echo "  jobs            List API jobs (needs 'make api' running)"
	@echo "  job             Tail a job's log  JOB=<id> [TAIL=40] [FOLLOW=1]"
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
	@echo "Meme Museum (src/meme-museum — own Postgres + vault, grid locked to \"$(MEME_MUSEUM_COLLECTION)\")"
	@echo "  mm-setup        First-time bootstrap: install, .env, images symlink, db up, migrate"
	@echo "  mm-install      Install Node dependencies (npm)"
	@echo "  mm-pipeline     Run the pipeline, locked to \"$(MEME_MUSEUM_COLLECTION)\"  [FILE=...] [COOKIES=firefox] [LIMIT=20] [DRY_RUN=1]"
	@echo "  mm-db-up        Start Postgres (Docker), wait until healthy  (host port 5434)"
	@echo "  mm-db-down      Stop Postgres"
	@echo "  mm-db-generate  Generate a Drizzle migration from db/schema.ts"
	@echo "  mm-db-migrate   Apply pending Drizzle migrations"
	@echo "  mm-dev          Run the Next.js dev server (http://localhost:3200)"
	@echo "  mm-build        Production build"
	@echo "  mm-start        Run the production build (after mm-build)"
	@echo "  mm-lint         eslint ."
	@echo "  mm-typecheck    tsc --noEmit"
	@echo "  mm-check        mm-lint + mm-typecheck"
	@echo ""
	@echo "Variables (defaults shown):"
	@echo "  VAULT=$(VAULT)"
	@echo "  WHISPER_MODEL=$(WHISPER_MODEL) (tiny | base | small | medium)"
	@echo "  LLM_MODEL=$(LLM_MODEL)         (qwen2.5:7b | qwen2.5:3b | mistral:7b)"
	@echo "  DATABASE_URL=$(DATABASE_URL)"
	@echo "  BACKOFFICE=$(BACKOFFICE)       Next.js/Postgres subproject path"
	@echo "  COLLECTIONS_STUDIO=$(COLLECTIONS_STUDIO)  Next.js collection-picker subproject path"
	@echo "  MEME_MUSEUM=$(MEME_MUSEUM)     Next.js/Postgres subproject path"

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

# Locked to $(MEME_MUSEUM_COLLECTION) — --vault/--collection/--database-url are
# hardcoded, not driven by the generic VAULT/COLLECTION/DATABASE_URL above, so
# this can never accidentally write into the wrong project's vault/database.
mm-pipeline:
	uv run reels-pipeline $(if $(FILE),$(FILE),your_instagram_activity/saved/saved_collections.json) \
		--vault $(MEME_MUSEUM_VAULT) $(_cookies) $(_whisper_model) $(_limite) $(_llm_model) \
		--collection "$(MEME_MUSEUM_COLLECTION)" --database-url $(MEME_MUSEUM_DATABASE_URL) \
		$(if $(DRY_RUN),--dry-run,)

telegram:
	uv run reels-telegram --vault $(VAULT) $(_cookies) $(_whisper_model) $(_limite)

# HTTP trigger for the pipeline — POST /content/ingestor does the same job as
# `reels-pipeline` (an empty body replays the locked mm-pipeline config). Binds
# to localhost, no auth: local-tool only, same as the rest of the repo.
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
API_BASE ?= http://$(API_HOST):$(API_PORT)
TAIL     ?= 40
api:
	REELS_API_HOST=$(API_HOST) REELS_API_PORT=$(API_PORT) uv run reels-api

# List API jobs, newest first (needs 'make api' running).
jobs:
	@curl -s "$(API_BASE)/content/ingestor" | python3 -m json.tool

# Tail a job's log (needs 'make api' running).
#   make job JOB=<id> [TAIL=40] [FOLLOW=1] [API_PORT=8000]
job:
ifndef JOB
	$(error JOB is required — usage: make job JOB=<id>  (list ids with 'make jobs'))
endif
	@while :; do \
		[ -n "$(FOLLOW)" ] && { clear 2>/dev/null || true; }; \
		curl -s "$(API_BASE)/content/ingestor/$(JOB)/logs?tail=$(TAIL)"; echo; \
		[ -n "$(FOLLOW)" ] || break; \
		curl -s "$(API_BASE)/content/ingestor/$(JOB)" \
			| grep -q '"phase": *"\(running\|queued\)"' || break; \
		sleep 2; \
	done

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

# ── meme museum: setup ───────────────────────────────────────────────────────
# Namespaced with an mm- prefix, same pattern as bo-/cs- above. Its own
# Postgres (own docker-compose, own port 5434) and its own pipeline vault —
# fully independent of the other two subprojects.

mm-install:
	npm --prefix $(MEME_MUSEUM) install

mm-env:
	@test -f $(MEME_MUSEUM)/.env || cp $(MEME_MUSEUM)/.env.example $(MEME_MUSEUM)/.env
	@echo "$(MEME_MUSEUM)/.env ready"

mm-images-link:
	@if [ ! -L $(MEME_MUSEUM)/public/images ]; then \
		rm -rf $(MEME_MUSEUM)/public/images; \
		mkdir -p $(MEME_MUSEUM)/public; \
		ln -s ../vault/images $(MEME_MUSEUM)/public/images; \
		echo "created $(MEME_MUSEUM)/public/images -> vault/images"; \
	fi

mm-setup: mm-install mm-env mm-images-link mm-db-up mm-db-generate mm-db-migrate
	@echo "Meme Museum ready — run 'make mm-dev' and open http://localhost:3200"
	@echo "Nothing to seed: run 'make mm-pipeline COOKIES=firefox' to populate Postgres directly."

# ── meme museum: database ────────────────────────────────────────────────────

mm-db-up:
	$(_npm_mm) db:up
	@cd $(MEME_MUSEUM) && for i in $$(seq 1 60); do \
		docker compose ps postgres --format json | grep -q '"Health":"healthy"' && exit 0; \
		sleep 1; \
	done; \
	echo "Postgres did not become healthy within 60s — check 'docker compose logs postgres'" >&2; exit 1
	@echo "Postgres healthy"

mm-db-down:
	$(_npm_mm) db:down

mm-db-generate:
	$(_npm_mm) db:generate

mm-db-migrate:
	$(_npm_mm) db:migrate

# ── meme museum: app ─────────────────────────────────────────────────────────

mm-dev:
	$(_npm_mm) dev

mm-build:
	$(_npm_mm) build

mm-start:
	$(_npm_mm) start

mm-lint:
	$(_npm_mm) lint

mm-typecheck:
	$(_npm_mm) typecheck

mm-check: mm-lint mm-typecheck
