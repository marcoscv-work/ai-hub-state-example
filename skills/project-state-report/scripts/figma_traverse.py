#!/usr/bin/env python3
"""
figma_traverse.py

Walk a Figma project (or an explicit list of file keys) via the Figma REST API
and emit a compact JSON state summary: per file its name, last modified date,
pages, top-level sections/frames, a heuristic "status" read from those names,
and any Jira-style issue keys (e.g. PROJ-1234) found in names.

Auth: reads the token from the FIGMA_TOKEN environment variable and sends it as
the X-Figma-Token header (personal access token style). Never pass the token on
the command line and never hardcode it.

Usage:
  export FIGMA_TOKEN="<your-figma-token>"
  # Whole project (needs projects:read; a plain PAT may get 403, see notes):
  python3 figma_traverse.py --project <PROJECT_ID> --out figma_state.json
  # Or an explicit list of file keys (works with a normal PAT):
  python3 figma_traverse.py --files KEY1,KEY2,KEY3 --out figma_state.json

Notes:
  - Listing a project (GET /v1/projects/:id/files) requires the Projects
    endpoints, gated by Figma (projects:read is only available in a private
    OAuth app). If you get 403, grab the file keys from the project view and
    use --files instead.
  - The token only needs file_metadata:read and file_content:read for --files.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://api.figma.com/v1"


class FigmaFileError(Exception):
    """Non-fatal per-file error (skip the file, keep traversing)."""

    def __init__(self, code, body):
        super().__init__(f"HTTP {code}: {body}")
        self.code = code
        self.body = body
KEY_RE = re.compile(r"\b([A-Z]{2,5}-\d+)\b")
# Heuristic status vocabulary read from page / section / frame names.
STATUS_HINTS = [
    ("done", "Done"), ("delivered", "Delivered"), ("shipped", "Shipped"),
    ("ready", "Ready"), ("approved", "Approved"), ("final", "Final"),
    ("review", "In review"), ("qa", "In review"),
    ("wip", "WIP"), ("in progress", "WIP"), ("progress", "WIP"),
    ("draft", "Draft"), ("explor", "Exploration"), ("idea", "Exploration"),
    ("backlog", "Backlog"), ("todo", "Backlog"), ("to do", "Backlog"),
    ("archive", "Archived"), ("deprecated", "Archived"),
]


def _get(path, token, params=None, retries=4):
    url = API + path
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limited, respect Retry-After
                wait = int(e.headers.get("Retry-After", "5"))
                time.sleep(min(wait, 30))
                continue
            if e.code in (401, 403):
                body = e.read().decode("utf-8", "replace")
                raise SystemExit(
                    f"HTTP {e.code} for {path}. Check the token scopes / access.\n{body}"
                )
            if e.code == 400:
                # Per-file error (e.g. FigJam / Slides: "File type not supported
                # by this endpoint"). Non-fatal: let the caller skip this file.
                body = e.read().decode("utf-8", "replace")
                raise FigmaFileError(e.code, body)
            if e.code >= 500 and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise SystemExit(f"HTTP {e.code} for {path}: {e.read().decode('utf-8','replace')}")
        except urllib.error.URLError as e:
            raise SystemExit(
                f"Network error reaching Figma ({e}). This environment must be able "
                f"to reach api.figma.com."
            )
    raise SystemExit(f"Gave up after {retries} attempts on {path}")


def infer_status(names):
    text = " ".join(names).lower()
    for needle, label in STATUS_HINTS:
        if needle in text:
            return label
    return "Unknown"


def keys_in(names):
    found = set()
    for n in names:
        for m in KEY_RE.findall(n):
            found.add(m)
    return sorted(found)


def summarize_file(key, token):
    # depth=2 returns pages plus their direct children (sections / top frames),
    # which is where status columns and screen names usually live.
    data = _get(f"/files/{key}", token, params={"depth": "2"})
    doc = data.get("document", {})
    pages = []
    all_names = [data.get("name", "")]
    for page in doc.get("children", []):
        child_names = [c.get("name", "") for c in page.get("children", [])]
        all_names.append(page.get("name", ""))
        all_names.extend(child_names)
        pages.append({
            "id": page.get("id"),
            "name": page.get("name"),
            "top_level_count": len(child_names),
            "top_level_names": child_names[:40],
        })
    return {
        "key": key,
        "name": data.get("name"),
        "last_modified": data.get("lastModified"),
        "version": data.get("version"),
        "editor_type": data.get("editorType"),
        "thumbnail_url": data.get("thumbnailUrl"),
        "pages": pages,
        "status_guess": infer_status(all_names),
        "issue_keys": keys_in(all_names),
    }


def main():
    ap = argparse.ArgumentParser(description="Traverse a Figma project or file list.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--project", help="Figma project id (needs projects:read).")
    g.add_argument("--files", help="Comma separated file keys.")
    ap.add_argument("--out", default="figma_state.json")
    args = ap.parse_args()

    token = os.environ.get("FIGMA_TOKEN")
    if not token:
        raise SystemExit("Set FIGMA_TOKEN in the environment first (do not paste it anywhere shared).")

    files = []
    project_name = None
    if args.project:
        listing = _get(f"/projects/{args.project}/files", token)
        project_name = listing.get("name")
        files = [{"key": f["key"], "name": f.get("name")} for f in listing.get("files", [])]
        if not files:
            raise SystemExit("Project returned no files (check the project id and access).")
    else:
        files = [{"key": k.strip()} for k in args.files.split(",") if k.strip()]

    results = []
    skipped = []
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] reading {f['key']} ...", file=sys.stderr)
        try:
            results.append(summarize_file(f["key"], token))
        except FigmaFileError as e:
            print(f"    skipped {f['key']} ({e})", file=sys.stderr)
            skipped.append({"key": f["key"], "name": f.get("name"), "reason": str(e)})

    all_keys = sorted({k for r in results for k in r["issue_keys"]})
    out = {
        "project_id": args.project,
        "project_name": project_name,
        "file_count": len(results),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "all_issue_keys": all_keys,
        "files": results,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {args.out}: {len(results)} files, {len(all_keys)} unique issue keys.", file=sys.stderr)
    print("Unique issue keys:", ", ".join(all_keys) or "(none found in names)", file=sys.stderr)


if __name__ == "__main__":
    main()
