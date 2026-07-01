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
  GitHub. The skill asks for the resources it needs (Figma project, GitHub repo,
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
- Join sources by **issue key** (e.g. `PROJ-1234`). The join is what makes the
  report more than four separate dashboards.
- Flag **disagreement** between sources — that is the signal (design ready but
  Jira open, PR merged but design stale, Jira closed but no PR, etc.).
- Never invent correspondences you cannot verify (for example matching a Jira
  display name to a GitHub username). State names verbatim per source and say so.
- If a fact is a guess (heuristic status, floor counts), label it as such.

## Step 0 — Gather resources and access (ask; don't assume)

Before doing anything, confirm the inputs. If any are unknown, **ask the user**.
If a token or credential is missing, **help them get it** (see "Obtaining
access"). Nothing here is hardcoded — every id, repo, key prefix and site is a
parameter the user supplies.

Resources to confirm (ask for whatever was not provided):

| Input | Question to ask |
| --- | --- |
| Figma project or files | "Which Figma project id, or which file URLs / keys?" |
| GitHub repo | "Which repo/fork holds the engineering work?" (`owner/repo`) |
| Jira scope | "How do I find the Jira items — a JQL, a project, or a text term?" |
| Jira site | "Which Atlassian site?" (used to derive the cloudId) |
| Code location | "Where does the code live (repo path / module)?" |
| Output | "Where should the report go, and do you want it deployed?" |
| Scope / depth | "Full four-source report, or a subset?" |

Then check what you can actually reach:

- **Figma**: needs a personal access token in the environment as `FIGMA_TOKEN`.
- **Jira**: use the connected **Atlassian MCP**. Call
  `getAccessibleAtlassianResources` to get the `cloudId`. If not connected, ask
  the user to run `/mcp` and authorize the Atlassian connector.
- **GitHub**: use the `gh` CLI. `gh auth status` to confirm. Public repos/forks
  are readable without auth; private repos need `gh auth login`.

## Obtaining access (help the user get each token)

Only request a secret in a way that keeps it out of the chat. Prefer the user
setting it themselves in-session with the `!` prefix, e.g.
`! export FIGMA_TOKEN="…"`. Never print a token, never scan the keychain or shell
profiles for one, and never put it in a URL, argument or commit.

- **Figma token** (`FIGMA_TOKEN`): Figma → Settings → Security → *Personal access
  tokens* → generate. Scopes: `file_content:read` and `file_metadata:read`.
  Whole-project listing (`--project`) additionally needs `projects:read`, which is
  only available in a private OAuth app; a plain PAT returns `403` on `--project`,
  so fall back to `--files` with keys copied from the project view. A placeholder
  or invalid token returns `403 {"err":"Invalid token"}`.
- **Atlassian**: no PAT needed when the Atlassian MCP is connected — that is the
  intended path. If it isn't, ask the user to run `/mcp` and authorize it.
- **GitHub**: `gh auth login` (web flow) when `gh auth status` is not logged in.
  For public data no auth is required; proceed read-only.

If a source stays unavailable, **continue with the others** and mark that
source's section as "not captured" with the exact reason and how to fill it —
never silently drop it.

## Step 1 — Figma inventory

```bash
# Whole project (needs projects:read; a plain PAT may 403 → use --files):
python3 scripts/figma_traverse.py --project <PROJECT_ID> --out figma_state.json
# Or explicit file keys (works with a normal PAT):
python3 scripts/figma_traverse.py --files KEY1,KEY2,KEY3 --out figma_state.json
```

The script reads the token from `FIGMA_TOKEN`. `figma_state.json` holds, per
file: `name`, `last_modified`, `pages`, top-level section names, a heuristic
`status_guess`, and `issue_keys`. Top-level `all_issue_keys` is the joined key
set; `skipped` lists files the file endpoint can't read (FigJam / Slides return
`400` — the script skips them and keeps going).

Then **vendor the thumbnails locally** — each file's `thumbnail_url` is a signed,
short-lived link, so download them to `<out>/thumbs/<fileKey>.<ext>` (a small curl
loop over the `thumbnail_url` values; detect `png`/`jpg` from the response
header/magic bytes). Reference the local copies from the report, not the Figma URLs.

## Step 2 — Join to Jira (Atlassian MCP)

Query all keys at once:

```
JQL: key in (PROJ-1234, PROJ-5678, …)
fields: summary, status, priority, assignee, updated, project, issuetype
```

The MCP result can be large enough to exceed the context budget; when that
happens it is saved to a file — extract only what you need with `jq` (e.g.
`.issues.nodes[] | [.key, .fields.status.name, …] | @tsv`) instead of reading the
whole file. Keep statuses verbatim (they may be localized).

## Step 3 — Join to GitHub PRs

```bash
gh pr list --repo <owner/repo> --state all --search "<KEY> in:title" \
    --json number,title,state,mergedAt
# or pull the whole open set once and match keys locally:
gh pr list --repo <owner/repo> --state open --limit 300 \
    --json number,title,isDraft,reviewDecision,statusCheckRollup
```

PR titles carry the same issue keys — that is the join. Capture CI and review
state. A design key with **no PR at all** is itself a finding (design leads
engineering), not a row to pad with "No PR".

## Step 4 — Build the report (sections, in this order)

Style it with **Lexicon Vanilla** (`liferay-design/lexicon-vanilla`,
https://github.com/liferay-design/lexicon-vanilla) — use its design tokens and
components as the visual base. How you wire it in is your call: vendor the token
and component CSS, pull just the pieces you need, or build a thin layout layer on
top of its tokens. Keep the accessibility floor: semantic landmarks, heading
order, visible focus, alt/aria on non-text, AA contrast, reduced-motion.

1. **Executive overview** — one-line title + a lead paragraph naming the sources
   and the through-line of where the product is heading.
2. **The strategic picture** — 3 conclusion cards (`ah-concl`, kickers such as
   Commercial / Product / Watch) + one *general* chart (e.g. strength per pillar
   across the sources). This is the "summary with charts", first.
3. **New to this project? You should know…** — a brief orientation card: how work
   is organized, where code lives, the product pillars, whether design leads code,
   the top risk, and any localization quirks.
4. **Who you can talk to** — a table mapping each area to its design owner (from
   Jira assignees) and engineering (from GitHub PR authors). State the source of
   each column; do not match identities across systems.
5. **Jira snapshot** — spread by project, priority mix, recent completions.
6. **GitHub pull requests** — open PRs by theme + a table with CI/review pills.
7. **Code map** — verified module / package inventory.
8. **Cross-source alignment matrix** — themes × sources with filled / half /
   empty dots; the half dot means partial presence. This is the payoff view.
9. **Risks and open questions** — lead with the single biggest delivery risk.
10. **Figma gallery** — a 16:9 thumbnail card per file (keyed files first, with
    their live Jira status), each card linking to its Figma file. Above it, one
    strategic "what design tells us" card. No per-row "GitHub PR" column.
11. **Footer / provenance** — exactly where each number came from and its caveats.

**Add links while you generate the HTML** (not as a post-pass) so every
reference is clickable:

- Jira keys → `https://<site>.atlassian.net/browse/<KEY>`
- PR refs `#N` → `https://github.com/<owner/repo>/pull/<N>`
- the repo slug → `https://github.com/<owner/repo>`
- GitHub usernames → `https://github.com/<user>`
- the Figma project id → `https://www.figma.com/files/project/<PROJECT_ID>`
- each Figma card → its file URL `https://www.figma.com/design/<fileKey>`

Open external links in a new tab with `rel="noopener"`, and never nest an `<a>`
inside another `<a>` (e.g. a Jira key that sits inside a card that already links
to Figma stays plain text).

## Step 5 — Verify, then optionally deploy

- Validate the HTML parses and that **no `<a>` is nested inside another `<a>`**
  (the linkifier guards this — confirm anyway).
- Confirm every referenced thumbnail exists on disk.
- Sanity-check that charts actually render.
- Deploy (if asked): GitHub Pages serves root or `/docs`. For a clean URL, push
  the report contents to the repo root with a `.nojekyll` file, enable Pages
  (`main` / root), wait for the build, and curl the URL for `200`.

## Refinement loop

After the first pass, offer to refine and take direction:

- **Scope**: add / remove a source; narrow to a theme or a set of keys.
- **Framing**: change the strategic conclusions, the pillar list, the risk.
- **Presentation**: chart types, gallery aspect ratio / link targets, order.
- **Depth**: floor counts vs full extraction; more / less commentary.

Re-run only the affected step (the JSON inventory, the Jira/GitHub join, or just
the HTML) rather than everything. Keep `figma_state.json` and the raw joins so a
refinement doesn't re-hit the APIs unnecessarily.

## Implementation notes (whatever CSS you build)

- **Bar charts**: the fill element must be `display:block`; an inline element
  ignores width/height and renders as an empty track.
- **Thumbnails**: use `object-fit: contain` with a fixed `aspect-ratio` and
  `height:auto`, and do not set `width`/`height` HTML attributes on the `<img>`
  (a fixed `height` attribute makes the browser ignore `aspect-ratio`).
  `object-fit: cover` crops/zooms — use only when that is intended.

## Files

- `scripts/figma_traverse.py` — Figma REST traversal (stdlib), skips unsupported files.

Everything else is done inline: thumbnails downloaded with a short curl loop
(Step 1), links added while generating the HTML (Step 4), and styling taken from
Lexicon Vanilla (`liferay-design/lexicon-vanilla`, referenced above). Only the
Figma traversal ships as a script because it encodes multi-request logic and edge
cases worth keeping tested.
