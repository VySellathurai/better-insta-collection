#!/bin/zsh
cd "$HOME/Documents/private/reels-vault"
source .venv/bin/activate
uv run reels-telegram --vault "./Vault" --cookies firefox