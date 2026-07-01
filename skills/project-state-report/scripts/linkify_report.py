#!/usr/bin/env python3
"""
linkify_report.py

Post-process a generated report HTML file and turn reference-like tokens into
links, WITHOUT ever creating nested links or touching tag internals:

  - Jira issue keys (e.g. LPD-1234)      -> <jira-base>/browse/KEY
  - Pull request refs (#1234)            -> https://github.com/<repo>/pull/1234
  - The repo slug (owner/name)           -> https://github.com/<repo>
  - Known GitHub usernames               -> https://github.com/<user>
  - A Figma project id                   -> https://www.figma.com/files/project/<id>

Safety model (learned the hard way):
  1. Existing <a>...</a> blocks are stashed first, so text already inside a link
     (e.g. Figma file links) is never re-wrapped -> no invalid nested <a>.
  2. Only text nodes are linkified: tokenize as `<tag>` OR `text`, transform text
     only. This leaves alt="", aria-label="", href="" and other attributes alone.
  3. `#\\d+` is not matched when preceded by `&` so HTML entities like &#8599;
     (the ↗ arrow) are never turned into a bogus /pull/8599 link.

All links open in a new tab with rel="noopener".

Usage:
  python3 linkify_report.py report/index.html \\
      --jira-base https://liferay.atlassian.net \\
      --github-repo liferay-ai-hub/liferay-portal \\
      --figma-project 490735323 \\
      --github-users mariuo,MrJohn1911,DavysonMelo
"""

import argparse
import re


def build(args):
    parts = []
    groups = []  # (name, regex)
    if args.github_repo:
        # Also link a base repo like owner/liferay-portal if provided via --extra-repos
        repos = [args.github_repo] + [r for r in (args.extra_repos or "").split(",") if r.strip()]
        repo_alt = "|".join(re.escape(r) for r in repos)
        groups.append(("repo", repo_alt))
    if args.jira_base:
        groups.append(("jira", r"\b[A-Z]{2,6}-\d+\b"))
    if args.github_repo:
        groups.append(("pr", r"(?<!&)#\d+\b"))
    if args.github_users:
        users = [u.strip() for u in args.github_users.split(",") if u.strip()]
        if users:
            groups.append(("user", r"\b(?:" + "|".join(re.escape(u) for u in users) + r")\b"))
    if args.figma_project:
        groups.append(("proj", r"\b" + re.escape(args.figma_project) + r"\b"))

    named = "|".join(f"(?P<{n}>{p})" for n, p in groups)
    combined = re.compile(named)

    def a(href, text):
        return f'<a href="{href}" target="_blank" rel="noopener">{text}</a>'

    def repl(m):
        d = m.groupdict()
        if d.get("repo"):
            return a(f"https://github.com/{d['repo']}", d["repo"])
        if d.get("jira"):
            return a(f"{args.jira_base.rstrip('/')}/browse/{d['jira']}", d["jira"])
        if d.get("pr"):
            return a(f"https://github.com/{args.github_repo}/pull/{d['pr'][1:]}", d["pr"])
        if d.get("user"):
            return a(f"https://github.com/{d['user']}", d["user"])
        if d.get("proj"):
            return a(f"https://www.figma.com/files/project/{d['proj']}", d["proj"])
        return m.group(0)

    return combined, repl


def main():
    ap = argparse.ArgumentParser(description="Linkify reference tokens in a report HTML file.")
    ap.add_argument("html", help="Path to the report HTML file (edited in place)")
    ap.add_argument("--jira-base", default="", help="Jira base URL, e.g. https://acme.atlassian.net")
    ap.add_argument("--github-repo", default="", help="owner/name of the main repo")
    ap.add_argument("--extra-repos", default="", help="Comma list of extra owner/name repos to link")
    ap.add_argument("--github-users", default="", help="Comma list of GitHub usernames to link")
    ap.add_argument("--figma-project", default="", help="Figma project id to link")
    args = ap.parse_args()

    if not args.jira_base:
        # Jira links are the most valuable; warn but continue for other link types.
        print("warning: --jira-base not set; Jira keys will not be linked", flush=True)

    html = open(args.html, encoding="utf-8").read()

    # 1) stash existing anchors
    anchors = []

    def stash(m):
        anchors.append(m.group(0))
        return f"\x00A{len(anchors) - 1}\x00"

    html = re.sub(r"<a\b[^>]*>.*?</a>", stash, html, flags=re.S)

    # 2) linkify text nodes only
    combined, repl = build(args)

    def on_token(m):
        tok = m.group(0)
        if tok.startswith("<"):
            return tok
        return combined.sub(repl, tok)

    html = re.sub(r"<[^>]+>|[^<]+", on_token, html)

    # 3) restore anchors
    html = re.sub(r"\x00A(\d+)\x00", lambda m: anchors[int(m.group(1))], html)

    open(args.html, "w", encoding="utf-8").write(html)
    print(f"linkified {args.html}")


if __name__ == "__main__":
    main()
