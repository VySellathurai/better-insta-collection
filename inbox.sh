#!/bin/zsh
cd "$HOME/Vault"
source .venv/bin/activate
python3 telegram_inbox.py --vault "./Vault" --cookies firefox