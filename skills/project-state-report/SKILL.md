---
name: project-state-report
description: >
  Build a single, decision-useful "project state" report that cross-references up
  to four sources by issue key: Figma (design), Jira (delivery), GitHub (pull
  requests / engineering) and the code. Produces a styled, deployable HTML report
  with an executive summary, strategic conclusions, an onboarding section, a
  contacts section, per-source snapshots, a cross-source alignment matrix, risks
  and a Figma thumbnail gallery. Use when asked to assess "where a project stands"
  or "the state and direction" of an initiative across design, delivery and
  engineering, to produce a status/health report, or to cross Figma with Jira and
  GitHub. The skill ASKS for the resources it needs (Figma project, GitHub repo,
  Jira scope) and, when a token is missing (Figma / Atlassian / GitHub), helps the
  user obtain it instead of failing.
---

# Project State Report (Figma + Jira + GitHub + Code)

Turn scattered signals into one report a reader can act on. Every section must
earn its place by answering a question a stakeholder actually has. Prefer fewer,
verified facts over exhaustive dumps.

## Guiding principle: data must be useful

- Lead with conclusions, not raw tables. A number is only worth showing if it
  changes a decision.
- Join sources by **issue key** (e.g. `LPD-1234`). The join is what makes the
  report more than four separate dashboards.
- Flag **disagreement** between sources — that is the signal (design ready but
  Jira open, PR merged but design stale, Jira closed but no PR, etc.).
- Never invent correspondences you cannot verify (e.g. matching a Jira display
  name to a GitHub username). State names verbatim per source and say so.
- If a fact is a guess (heuristic status, floor counts), label it as such.

## Step 0 — Gather resources and access (ASK; don't assume)

Before doing anything, confirm the inputs. If any are unknown, **ask the user**.
If a token/credential is missing, **help them get it** (see "Obtaining access").

Resources to confirm (ask for whatever was not provided):

| Input | Question to ask | Example |
| --- | --- | --- |
| Figma project or files | "Which Figma project id, or which file URLs/keys?" | `490735323`, or `figma.com/design/<KEY>/…` |
| GitHub repo | "Which repo/fork holds the engineering work?" | `owner/repo` (public fork readable without auth) |
| Jira scope | "How do I find the Jira items — a JQL, a project, or a text term?" | `key in (…)`, `project = LPD`, or text `"AI Hub"` |
| Jira site | "Which Atlassian site?" (derive cloudId) | `acme.atlassian.net` |
| Code location | "Where does the code live (repo path/module)?" | `modules/.../ai-hub/` |
| Output | "Where should the report go, and do you want it deployed?" | `report/`, GitHub Pages |
| Scope/depth | "Full four-source report, or just a subset?" | Figma+Jira only, etc. |

Then check what you can actually reach:

- **Figma**: needs a token in the env. The script reads `FIGMA_TOKEN`, but the
  value is often stored under a different name — **check `FIGMA_ACCESS_TOKEN`
  too** and map it: `FIGMA_TOKEN="$FIGMA_ACCESS_TOKEN" python3 …`. Verify the
  token is real, not the `figd_xxx` placeholder (a placeholder returns
  `403 {"err":"Invalid token"}`).
- **Jira**: use the connected **Atlassian MCP**. Call `getAccessibleAtlassianResources`
  to get the `cloudId`. If not connected, tell the user to run `/mcp` and pick the
  Atlassian connector.
- **GitHub**: use the `gh` CLI. `gh auth status` to confirm. Public forks are
  readable without auth; private repos need `gh auth login`.

## Obtaining access (help the user get each token)

Only ask for a secret via a method that keeps it out of the chat. Prefer the
user setting it themselves in-session with the `!` prefix, e.g.
`! export FIGMA_TOKEN="figd_…"`. Never print a token, never scan the keychain or
shell profiles for one, never put it in a URL/argument/commit.

- **Figma token** (`FIGMA_TOKEN`): Figma → Settings → Security → *Personal access
  tokens* → generate. Scopes: `file_content:read` and `file_metadata:read`.
  Whole-project listing (`--project`) additionally needs `projects:read`, which is
  only available in a private OAuth app — a plain PAT will `403` on `--project`,
  so fall back to `--files` with keys copied from the project view. If the value
  lives in `FIGMA_ACCESS_TOKEN`, just map it (above) — don't ask the user to
  re-create it.
- **Atlassian**: no PAT needed if the Atlassian MCP is connected — that is the
  intended path. If it isn't, ask the user to run `/mcp` and authorize the
  Atlassian connector, then retry.
- **GitHub**: `gh auth login` (web flow) if `gh auth status` is not logged in.
  For public data, note that no auth is required and proceed read-only.

If a source stays unavailable, **continue with the others** and mark that
source's section as "not captured" with the exact reason and how to fill it —
never silently drop it.

## Step 1 — Figma inventory

```bash
# Whole project (needs projects:read; a plain PAT may 403 → use --files):
FIGMA_TOKEN="$FIGMA_ACCESS_TOKEN" python3 scripts/figma_traverse.py \
    --project <PROJECT_ID> --out figma_state.json
# Or explicit file keys (works with a normal PAT):
FIGMA_TOKEN="$FIGMA_ACCESS_TOKEN" python3 scripts/figma_traverse.py \
    --files KEY1,KEY2,KEY3 --out figma_state.json
```

`figma_state.json` holds, per file: `name`, `last_modified`, `pages`, top-level
section names, a heuristic `status_guess`, and `issue_keys`. Top-level
`all_issue_keys` is the joined key set; `skipped` lists FigJam/Slides files the
file endpoint can't read (this is expected — the script skips 400s and keeps going).

Then vendor the thumbnails locally (the Figma URLs are signed and expire):

```bash
python3 scripts/fetch_thumbnails.py --state figma_state.json --out <out>/thumbs
```

## Step 2 — Join to Jira (Atlassian MCP)

Query all keys at once:

```
JQL: key in (LPD-1234, LPD-5678, …)
fields: summary, status, priority, assignee, updated, project, issuetype
```

The MCP result can be large and blow the context budget. If it errors with
"exceeds maximum allowed tokens", it is saved to a file — extract just what you
need with `jq` (e.g. `.issues.nodes[] | [.key, .fields.status.name, …] | @tsv`),
don't Read the whole file. Statuses may be localized (mixed English/Spanish);
keep them verbatim.

## Step 3 — Join to GitHub PRs

```bash
gh pr list --repo <owner/repo> --state all --search "<KEY> in:title" \
    --json number,title,state,mergedAt
# or pull the whole open set once and match keys locally:
gh pr list --repo <owner/repo> --state open --limit 300 \
    --json number,title,isDraft,reviewDecision,statusCheckRollup
```

PR titles carry the same issue keys — that is the join. Capture CI state and
review state. A design key with **no PR at all** is itself a finding (design
leads engineering), not a row to pad with "No PR".

## Step 4 — Build the report (sections, in this order)

Use the vendored CSS in `assets/css/` (Lexicon Vanilla tokens + the report
layout). Keep the accessibility floor: semantic landmarks, heading order, visible
focus, alt/aria on non-text, AA contrast, reduced-motion.

1. **Executive overview** — one-line title + a lead paragraph naming the sources
   and the through-line of where the product is heading.
2. **The strategic picture** — 3 conclusion cards (`ah-concl`, kickers like
   Commercial / Product / Watch) + one *general* chart (e.g. investment/strength
   per pillar across the sources). This is the "summary with charts", first.
3. **New to this project? You should know…** — a brief orientation card: how work
   is organized (not one Jira project), where code lives, product pillars, that
   design leads code, the top risk, and any localization quirks.
4. **Who you can talk to** — a table mapping each area to its design owner (from
   Jira assignees) and engineering (from GitHub PR authors). State the source of
   each column; do NOT match identities across systems.
5. **Jira snapshot** — spread by project, priority mix, recent completions.
6. **GitHub pull requests** — open PRs by theme + a table with CI/review pills.
7. **Code map** — verified module/package inventory.
8. **Cross-source alignment matrix** — themes × sources with filled / half /
   empty dots; the half dot means partial presence. This is the payoff view.
9. **Risks and open questions** — lead with the single biggest delivery risk.
10. **Figma gallery** — a 16:9 thumbnail card per file (keyed files first, with
    their live Jira status), each card linking to its Figma file. Above it, one
    strategic "what design tells us" card. No per-row "GitHub PR" column.
11. **Footer / provenance** — exactly where each number came from and its caveats.

Then linkify every reference-like token:

```bash
python3 scripts/linkify_report.py <out>/index.html \
    --jira-base https://<site>.atlassian.net \
    --github-repo <owner/repo> \
    --figma-project <PROJECT_ID> \
    --github-users user1,user2,user3
```

## Step 5 — Verify, then optionally deploy

- Validate the HTML parses and that **no `<a>` is nested inside another `<a>`**
  (the linkifier guards this — confirm anyway).
- Confirm every referenced thumbnail exists on disk.
- Sanity-check the charts actually render (bar fills need `display:block`; an
  inline `<span>` fill shows an empty gray track — a real bug we hit).
- Deploy (if asked): GitHub Pages serves root or `/docs`. For a clean URL, push
  the report contents to the repo root with a `.nojekyll` file, enable Pages
  (`main` / root), wait for the build, and curl the URL for `200`.

## Refinement loop

After the first pass, offer to refine and take direction:

- **Scope**: add/remove a source; narrow to a theme or a set of keys.
- **Framing**: change the strategic conclusions, the pillar list, the risk.
- **Presentation**: chart types, gallery aspect ratio/link targets, section order.
- **Depth**: floor counts vs full extraction; more/less commentary.

Re-run only the affected step (the JSON inventory, the Jira/GitHub join, or just
the HTML) rather than everything. Keep `figma_state.json` and the raw joins so a
refinement doesn't re-hit the APIs unnecessarily.

## Gotchas (learned in practice)

- `FIGMA_TOKEN` vs `FIGMA_ACCESS_TOKEN` — the script wants the former; map it.
- `--project` 403 on a plain PAT → use `--files`.
- FigJam/Slides files 400 on the file endpoint → skipped by design.
- Figma thumbnail URLs expire → always vendor them locally.
- Thumbnails: use `object-fit: contain` with a fixed `aspect-ratio` and
  `height:auto`; DON'T set `width`/`height` HTML attributes on the `<img>` (a
  fixed `height` attribute makes the browser ignore `aspect-ratio` and breaks
  card heights). `object-fit: cover` zooms/crops — avoid unless intended.
- Bar charts: the fill element must be `display:block` (inline spans ignore
  width/height and render as empty gray tracks).
- Jira MCP responses can exceed the context budget → extract with `jq`.
- Never scan credential stores for tokens; ask the user to set them via `!export`.

## Files

- `scripts/figma_traverse.py` — Figma REST traversal (stdlib), skips unsupported files.
- `scripts/fetch_thumbnails.py` — vendor Figma thumbnails locally.
- `scripts/linkify_report.py` — safe linkifier (no nested links, tag-aware).
- `assets/css/` — `tokens.css`, `components.css` (Lexicon Vanilla), `report.css`
  (the report layout, including the fixed bar and thumbnail rules).
