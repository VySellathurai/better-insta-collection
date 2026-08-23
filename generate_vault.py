#!/usr/bin/env python3
"""
generate_vault.py

Regenere vault.html a partir de index.md.

Usage :
    python3 generate_vault.py

Le script lit Vault/index.md (format : entrees "### titre" suivies de lignes
"- lien :", "- auteur :", "- themes :", "- contenu :"), construit une liste
d'entrees en JSON, et l'injecte dans un template HTML autonome (pas de
dependance externe, fonctionne hors ligne) qui est ecrit dans Vault/vault.html.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
VAULT_DIR = ROOT / "Vault"
INDEX_PATH = VAULT_DIR / "index.md"
OUTPUT_PATH = VAULT_DIR / "vault.html"


def parse_index(text: str) -> list[dict[str, Any]]:
    """Parse index.md en une liste de dicts {titre, lien, auteur, themes, contenu}."""
    entries: list[dict[str, Any]] = []
    # Coupe le texte en blocs qui commencent par "### "
    blocks = re.split(r"(?m)^### ", text)
    for block in blocks[1:]:  # le premier bloc est l'en-tete "# Index..."
        lines = block.splitlines()
        titre = lines[0].strip()
        lien, auteur, themes_raw, contenu = "", "", "", ""
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("- lien"):
                lien = line.split(":", 1)[1].strip()
            elif line.startswith("- auteur"):
                auteur = line.split(":", 1)[1].strip()
            elif line.startswith("- th") and "me" in line.split(":")[0]:
                themes_raw = line.split(":", 1)[1].strip()
            elif line.startswith("- contenu"):
                contenu = line.split(":", 1)[1].strip()

        themes = [t.strip() for t in themes_raw.split(",") if t.strip()]
        # Normalise le cas "aucun theme identifiable" -> pas de theme filtrable
        themes = [t for t in themes if "aucun th" not in t.lower()]

        entries.append(
            {
                "titre": titre,
                "lien": lien,
                "auteur": auteur,
                "themes": themes,
                "contenu": contenu,
            }
        )
    return entries


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vault — Index des vidéos Instagram</title>
<style>
  :root {
    --bg: #0f1115;
    --panel: #171a21;
    --panel-2: #1e222b;
    --border: #2a2f3a;
    --text: #e8e9ec;
    --text-dim: #9aa1ac;
    --accent: #6ea8fe;
    --accent-bg: rgba(110, 168, 254, 0.15);
    --chip-bg: #232833;
    --chip-active-bg: #6ea8fe;
    --chip-active-text: #0f1115;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    padding: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .wrap {
    max-width: 860px;
    margin: 0 auto;
    padding: 16px 14px 60px;
  }
  header h1 {
    font-size: 1.35rem;
    margin: 6px 0 2px;
  }
  header .subtitle {
    color: var(--text-dim);
    font-size: 0.85rem;
    margin: 0 0 16px;
  }
  .search-box {
    position: sticky;
    top: 0;
    background: var(--bg);
    padding: 8px 0 10px;
    z-index: 10;
  }
  #search {
    width: 100%;
    padding: 12px 14px;
    font-size: 1rem;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    outline: none;
  }
  #search:focus {
    border-color: var(--accent);
  }
  .themes-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 10px 0 4px;
  }
  .theme-chip {
    border: 1px solid var(--border);
    background: var(--chip-bg);
    color: var(--text);
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 0.8rem;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    user-select: none;
  }
  .theme-chip .count {
    color: var(--text-dim);
    font-size: 0.75rem;
  }
  .theme-chip.active {
    background: var(--chip-active-bg);
    color: var(--chip-active-text);
    border-color: var(--chip-active-bg);
  }
  .theme-chip.active .count {
    color: rgba(15, 17, 21, 0.65);
  }
  .status-line {
    color: var(--text-dim);
    font-size: 0.8rem;
    margin: 10px 0 6px;
  }
  .entries {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 8px;
  }
  .entry {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
  }
  .entry h2 {
    font-size: 1rem;
    margin: 0 0 8px;
    line-height: 1.35;
  }
  .entry h2 a {
    color: var(--text);
    text-decoration: none;
  }
  .entry h2 a:hover {
    color: var(--accent);
    text-decoration: underline;
  }
  .entry .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
  }
  .entry .auteur {
    color: var(--text-dim);
    font-size: 0.8rem;
    margin-bottom: 8px;
  }
  .tag {
    background: var(--accent-bg);
    color: var(--accent);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 600;
  }
  .entry p.contenu {
    margin: 0 0 10px;
    font-size: 0.88rem;
    line-height: 1.5;
    color: var(--text);
  }
  .entry a.lien {
    font-size: 0.82rem;
    color: var(--accent);
    text-decoration: none;
    word-break: break-all;
  }
  .entry a.lien:hover {
    text-decoration: underline;
  }
  .no-results {
    text-align: center;
    color: var(--text-dim);
    padding: 40px 0;
    font-size: 0.9rem;
  }
  mark {
    background: rgba(110, 168, 254, 0.35);
    color: inherit;
    border-radius: 3px;
    padding: 0 1px;
  }
  footer {
    text-align: center;
    color: var(--text-dim);
    font-size: 0.72rem;
    margin-top: 30px;
  }
  @media (max-width: 480px) {
    .entry { padding: 12px 12px; }
    header h1 { font-size: 1.15rem; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>🎬 Vault — Vidéos Instagram sauvegardées</h1>
    <p class="subtitle">__TOTAL_COUNT__ vidéos indexées — généré automatiquement depuis index.md</p>
  </header>

  <div class="search-box">
    <input id="search" type="text" placeholder="Rechercher un titre, un auteur, un mot-clé...">
  </div>

  <div class="themes-bar" id="themes-bar"></div>

  <div class="status-line" id="status-line"></div>

  <div class="entries" id="entries"></div>
  <div class="no-results" id="no-results" style="display:none;">Aucune entrée ne correspond à cette recherche.</div>

  <footer>Fichier autonome, généré par generate_vault.py — fonctionne hors ligne.</footer>
</div>

<script>
const DATA = __DATA_JSON__;

let activeTheme = null;
let searchQuery = "";

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function highlight(text, query) {
  if (!query) return escapeHtml(text);
  const escaped = escapeHtml(text);
  const q = query.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&");
  const re = new RegExp("(" + q + ")", "ig");
  return escaped.replace(re, "<mark>$1</mark>");
}

function buildThemeCounts() {
  const counts = {};
  DATA.forEach(function (e) {
    e.themes.forEach(function (t) {
      counts[t] = (counts[t] || 0) + 1;
    });
  });
  return counts;
}

function renderThemeBar() {
  const bar = document.getElementById("themes-bar");
  const counts = buildThemeCounts();
  const themes = Object.keys(counts).sort(function (a, b) {
    return counts[b] - counts[a] || a.localeCompare(b);
  });

  let html = '<button class="theme-chip' + (activeTheme === null ? " active" : "") +
    '" data-theme="">Tous <span class="count">' + DATA.length + '</span></button>';

  themes.forEach(function (t) {
    html += '<button class="theme-chip' + (activeTheme === t ? " active" : "") +
      '" data-theme="' + escapeHtml(t) + '">' + escapeHtml(t) +
      ' <span class="count">' + counts[t] + '</span></button>';
  });

  bar.innerHTML = html;

  bar.querySelectorAll(".theme-chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      const t = chip.getAttribute("data-theme");
      activeTheme = t === "" ? null : t;
      renderThemeBar();
      renderEntries();
    });
  });
}

function matchesSearch(entry, q) {
  if (!q) return true;
  const hay = (entry.titre + " " + entry.auteur + " " + entry.contenu).toLowerCase();
  return hay.indexOf(q) !== -1;
}

function renderEntries() {
  const container = document.getElementById("entries");
  const noResults = document.getElementById("no-results");
  const statusLine = document.getElementById("status-line");
  const q = searchQuery.trim().toLowerCase();

  const filtered = DATA.filter(function (e) {
    const themeOk = activeTheme === null || e.themes.indexOf(activeTheme) !== -1;
    return themeOk && matchesSearch(e, q);
  });

  statusLine.textContent = filtered.length + " résultat" + (filtered.length !== 1 ? "s" : "") +
    (activeTheme ? " — thème : " + activeTheme : "");

  if (filtered.length === 0) {
    container.innerHTML = "";
    noResults.style.display = "block";
    return;
  }
  noResults.style.display = "none";

  container.innerHTML = filtered.map(function (e) {
    const tags = e.themes.map(function (t) {
      return '<span class="tag">' + escapeHtml(t) + "</span>";
    }).join("");
    const titre = searchQuery ? highlight(e.titre, searchQuery.trim()) : escapeHtml(e.titre);
    const contenu = searchQuery ? highlight(e.contenu, searchQuery.trim()) : escapeHtml(e.contenu);
    const auteur = searchQuery ? highlight(e.auteur, searchQuery.trim()) : escapeHtml(e.auteur);
    const lienHtml = e.lien
      ? '<a class="lien" href="' + escapeHtml(e.lien) + '" target="_blank" rel="noopener">' + escapeHtml(e.lien) + "</a>"
      : "";
    return (
      '<article class="entry">' +
      "<h2>" + (e.lien ? '<a href="' + escapeHtml(e.lien) + '" target="_blank" rel="noopener">' + titre + "</a>" : titre) + "</h2>" +
      '<div class="meta">' + tags + "</div>" +
      '<div class="auteur">👤 ' + auteur + "</div>" +
      '<p class="contenu">' + contenu + "</p>" +
      lienHtml +
      "</article>"
    );
  }).join("");
}

document.getElementById("search").addEventListener("input", function (e) {
  searchQuery = e.target.value;
  renderEntries();
});

renderThemeBar();
renderEntries();
</script>
</body>
</html>
"""


def main() -> None:
    if not INDEX_PATH.exists():
        print("index.md introuvable a cote du script :", INDEX_PATH, file=sys.stderr)
        sys.exit(1)

    text = INDEX_PATH.read_text(encoding="utf-8")
    entries = parse_index(text)

    if not entries:
        print("Aucune entree trouvee dans index.md.", file=sys.stderr)
        sys.exit(1)

    data_json = json.dumps(entries, ensure_ascii=False, indent=None)
    html = HTML_TEMPLATE.replace("__DATA_JSON__", data_json)
    html = html.replace("__TOTAL_COUNT__", str(len(entries)))

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print("vault.html regenere avec", len(entries), "entrees ->", OUTPUT_PATH)


if __name__ == "__main__":
    main()
