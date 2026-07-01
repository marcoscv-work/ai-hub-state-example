#!/usr/bin/env python3
"""
fetch_thumbnails.py

Download the per-file thumbnails referenced in a figma_state.json (produced by
figma_traverse.py) into a local folder, named <fileKey>.<ext>. Figma thumbnail
URLs are short-lived signed S3 links, so they MUST be vendored locally if the
report is meant to keep working over time.

No token needed: the thumbnail URLs are already signed. Stdlib only.

Usage:
  python3 fetch_thumbnails.py --state figma_state.json --out ../report/thumbs
"""

import argparse
import json
import os
import sys
import urllib.request


def main():
    ap = argparse.ArgumentParser(description="Download Figma file thumbnails locally.")
    ap.add_argument("--state", default="figma_state.json", help="Path to figma_state.json")
    ap.add_argument("--out", default="thumbs", help="Output directory for images")
    args = ap.parse_args()

    with open(args.state, encoding="utf-8") as fh:
        data = json.load(fh)
    os.makedirs(args.out, exist_ok=True)

    ok, fail = 0, []
    files = data.get("files", [])
    for i, f in enumerate(files, 1):
        key = f.get("key")
        url = f.get("thumbnail_url")
        if not url:
            fail.append((key, "no thumbnail_url"))
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "figma-thumbs/1.0"})
            blob = urllib.request.urlopen(req, timeout=60).read()
            ext = "png" if blob[:8] == b"\x89PNG\r\n\x1a\n" else ("jpg" if blob[:3] == b"\xff\xd8\xff" else "png")
            with open(os.path.join(args.out, f"{key}.{ext}"), "wb") as out:
                out.write(blob)
            ok += 1
            print(f"[{i}/{len(files)}] {key}.{ext}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - report and continue
            fail.append((key, str(e)))
            print(f"[{i}/{len(files)}] FAILED {key}: {e}", file=sys.stderr)

    print(f"\nDownloaded {ok}/{len(files)} thumbnails into {args.out}", file=sys.stderr)
    if fail:
        print(f"Failed: {fail}", file=sys.stderr)


if __name__ == "__main__":
    main()
