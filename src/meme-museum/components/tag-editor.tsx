"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, useTransition } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";

import { setPostTags } from "@/app/actions";
import { slugifyTagName } from "@/lib/tags";

type ThemeOption = { slug: string; name: string; count: number };

const POPOVER_W = 260;
const GAP = 6;
const MARGIN = 8;
const SHEET_QUERY = "(max-width: 560px)";

type Pos = { top: number; left: number };

// Rendered inside each tile via react-photo-album's `render.extras` slot — so
// the trigger <button> lives INSIDE the tile's wrapping <a href={instagram}
// target="_blank"> (there is no render slot that escapes that anchor). Hence
// every pointer/touch handler on the trigger stops propagation (so the
// anchor's long-press "peek" in photo-album.tsx never arms) and the click
// handler also preventDefault()s (so the tile doesn't navigate).
//
// The popover panel itself is portaled to document.body: it must not be
// clipped by the album grid or `.wrap { max-width }`, and keeping the heavy
// interactive UI out of the <a> sidesteps invalid-nesting quirks.
export function TagEditor({
  postId,
  tagNames,
  allThemes,
}: {
  postId: string;
  tagNames: string[];
  allThemes: ThemeOption[];
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<string[]>(tagNames);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [pos, setPos] = useState<Pos | null>(null);
  const [isSheet, setIsSheet] = useState(false);
  const [pending, startTransition] = useTransition();

  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const router = useRouter();
  const listboxId = useId();

  const draftSlugs = useMemo(() => new Set(draft.map(slugifyTagName)), [draft]);

  const { matches, showCreate } = useMemo(() => {
    const nq = query.trim().toLowerCase();
    const m = allThemes.filter(
      (t) => !draftSlugs.has(t.slug) && (nq === "" || t.name.toLowerCase().includes(nq)),
    );
    const qSlug = slugifyTagName(query);
    const create = qSlug !== "" && !draftSlugs.has(qSlug) && !allThemes.some((t) => t.slug === qSlug);
    return { matches: m, showCreate: create };
  }, [query, allThemes, draftSlugs]);

  const optionCount = matches.length + (showCreate ? 1 : 0);
  const activeClamped = optionCount === 0 ? 0 : Math.min(activeIndex, optionCount - 1);

  const addTag = useCallback(
    (name: string) => {
      const slug = slugifyTagName(name);
      if (!slug) return;
      setDraft((prev) => {
        if (prev.some((d) => slugifyTagName(d) === slug)) return prev;
        const canonical = allThemes.find((t) => t.slug === slug)?.name ?? name.trim();
        return [...prev, canonical];
      });
      setQuery("");
      setActiveIndex(0);
      inputRef.current?.focus();
    },
    [allThemes],
  );

  const removeTag = useCallback((name: string) => {
    setDraft((prev) => prev.filter((d) => d !== name));
    inputRef.current?.focus();
  }, []);

  const selectIndex = useCallback(
    (i: number) => {
      if (i < matches.length) {
        const opt = matches[i];
        if (opt) addTag(opt.name);
        return;
      }
      if (showCreate) addTag(query);
    },
    [matches, showCreate, query, addTag],
  );

  const openPopover = useCallback(() => {
    setDraft(tagNames);
    setQuery("");
    setActiveIndex(0);
    setError(null);
    setIsSheet(typeof window !== "undefined" && window.matchMedia(SHEET_QUERY).matches);
    setOpen(true);
  }, [tagNames]);

  const close = useCallback(() => {
    setOpen(false);
    triggerRef.current?.focus();
  }, []);

  const computePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const r = trigger.getBoundingClientRect();
    const h = popoverRef.current?.offsetHeight ?? 280;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const left = Math.min(Math.max(r.right - POPOVER_W, MARGIN), vw - POPOVER_W - MARGIN);
    let top = r.bottom + GAP;
    if (top + h > vh - MARGIN) {
      const above = r.top - GAP - h;
      top = above >= MARGIN ? above : Math.max(MARGIN, vh - MARGIN - h);
    }
    setPos({ top, left });
  }, []);

  // Position before paint, and recompute as the panel grows/shrinks.
  useLayoutEffect(() => {
    if (!open || isSheet) return;
    computePosition();
  }, [open, isSheet, computePosition, draft.length, query, optionCount]);

  useEffect(() => {
    if (!open || isSheet) return;
    const onMove = () => computePosition();
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, true);
    return () => {
      window.removeEventListener("resize", onMove);
      window.removeEventListener("scroll", onMove, true);
    };
  }, [open, isSheet, computePosition]);

  // Click-outside + Escape. Attached after the opening click has fully
  // dispatched (it runs in an effect), so it can't self-close.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (popoverRef.current?.contains(t) || triggerRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        close();
      }
    };
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown, true);
    };
  }, [open, close]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const save = () => {
    setError(null);
    startTransition(async () => {
      const res = await setPostTags(postId, draft);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setOpen(false);
      router.refresh();
    });
  };

  const onInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (optionCount === 0 ? 0 : (i + 1) % optionCount));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (optionCount === 0 ? 0 : (i - 1 + optionCount) % optionCount));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (optionCount > 0) selectIndex(activeClamped);
    } else if (e.key === "Backspace" && query === "" && draft.length > 0) {
      setDraft((prev) => prev.slice(0, -1));
    }
  };

  // Small focus trap: keep Tab within the panel while it is open, so focus
  // never lands on the underlying <a>.
  const onPopoverKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Tab") return;
    const focusables = popoverRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input, [tabindex]:not([tabindex="-1"])',
    );
    if (!focusables || focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (!first || !last) return;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const optionId = (i: number) => `${listboxId}-opt-${i}`;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={`tag-edit-trigger${open ? " is-open" : ""}`}
        aria-label="Modifier les tags"
        aria-haspopup="dialog"
        aria-expanded={open}
        onPointerDown={(e) => e.stopPropagation()}
        onTouchStart={(e) => e.stopPropagation()}
        onTouchEnd={(e) => e.stopPropagation()}
        onTouchMove={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (open) close();
          else openPopover();
        }}
      >
        <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" focusable="false">
          <path
            fill="currentColor"
            d="M11.013 1.427a1.75 1.75 0 0 1 2.474 0l1.086 1.086a1.75 1.75 0 0 1 0 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 0 1-.927-.928l.929-3.25c.081-.286.235-.547.445-.758l8.61-8.61Zm1.414 1.06a.25.25 0 0 0-.354 0L10.811 3.75l1.439 1.44 1.263-1.263a.25.25 0 0 0 0-.354l-1.086-1.086ZM11.189 6.25 9.75 4.81l-6.286 6.287a.25.25 0 0 0-.064.108l-.558 1.953 1.953-.558a.25.25 0 0 0 .108-.064L11.189 6.25Z"
          />
        </svg>
      </button>

      {open &&
        typeof document !== "undefined" &&
        createPortal(
          <>
            {isSheet && <div className="te-backdrop" onClick={close} />}
            <div
              ref={popoverRef}
              className={`te-popover${isSheet ? " te-popover--sheet" : ""}`}
              role="dialog"
              aria-modal="true"
              aria-label="Modifier les tags"
              style={
                isSheet ? undefined : { top: pos?.top ?? -9999, left: pos?.left ?? -9999 }
              }
              onKeyDown={onPopoverKeyDown}
            >
              <div className="te-chips">
                {draft.length === 0 && <span className="te-empty">Aucun tag</span>}
                {draft.map((name) => (
                  <span key={name} className="te-chip">
                    #{name}
                    <button type="button" aria-label={`retirer ${name}`} onClick={() => removeTag(name)}>
                      ×
                    </button>
                  </span>
                ))}
              </div>

              <input
                ref={inputRef}
                className="te-input"
                type="text"
                role="combobox"
                aria-expanded={optionCount > 0}
                aria-controls={listboxId}
                aria-autocomplete="list"
                aria-activedescendant={optionCount > 0 ? optionId(activeClamped) : undefined}
                placeholder="Ajouter un tag…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActiveIndex(0);
                }}
                onKeyDown={onInputKeyDown}
              />

              {optionCount > 0 && (
                <ul id={listboxId} role="listbox" className="te-listbox">
                  {matches.map((t, i) => (
                    <li
                      key={t.slug}
                      id={optionId(i)}
                      role="option"
                      aria-selected={i === activeClamped}
                      className={`te-option${i === activeClamped ? " is-active" : ""}`}
                      onMouseEnter={() => setActiveIndex(i)}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => addTag(t.name)}
                    >
                      <span>#{t.name}</span>
                      <span className="count">{t.count}</span>
                    </li>
                  ))}
                  {showCreate && (
                    <li
                      id={optionId(matches.length)}
                      role="option"
                      aria-selected={activeClamped === matches.length}
                      className={`te-option te-option--create${
                        activeClamped === matches.length ? " is-active" : ""
                      }`}
                      onMouseEnter={() => setActiveIndex(matches.length)}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => addTag(query)}
                    >
                      Créer « {query.trim()} »
                    </li>
                  )}
                </ul>
              )}

              {error && <p className="te-error">{error}</p>}

              <div className="te-actions">
                <button type="button" className="te-cancel" onClick={close} disabled={pending}>
                  Annuler
                </button>
                <button type="button" className="te-save" onClick={save} disabled={pending}>
                  {pending ? "…" : "Enregistrer"}
                </button>
              </div>
            </div>
          </>,
          document.body,
        )}
    </>
  );
}
