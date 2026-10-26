#!/usr/bin/env python3
"""Report drift between the inlined Obsidian material and its upstream skills.

Each reference carries a header with the upstream raw URL and the SHA-256 of the file as captured.
This script fetches the upstream file, hashes it, and compares. It never rewrites a reference: a
drift means a human re-reads the diff and re-inlines deliberately.

Usage:
    python check_upstream.py            # report, exit 1 on drift
    python check_upstream.py --update   # print the hash lines to paste after re-inlining
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "references"

# reference file -> upstream raw URL
TARGETS = {
    "OBSIDIAN-CLI.md": "https://raw.githubusercontent.com/kepano/obsidian-skills/main/skills/obsidian-cli/SKILL.md",
    "OBSIDIAN-MARKDOWN.md": "https://raw.githubusercontent.com/kepano/obsidian-skills/main/skills/obsidian-markdown/SKILL.md",
}

HEADER_SHA = re.compile(r"upstream-sha256:\s*([0-9a-f]{64})")


def normalize(body: bytes) -> bytes:
    """Compare content, not line endings: a clone with CRLF must not read as drift."""
    return body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def recorded_sha(text: str) -> str | None:
    match = HEADER_SHA.search(text)
    return match.group(1) if match else None


def fetch(url: str, timeout: float = 30.0) -> bytes:
    """Fetch through urllib, falling back to curl.

    Some corporate TLS stacks break urllib's default context while leaving curl working, and a
    drift check that fails on transport is worse than useless.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "obsidian-kglite-skill/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URLs
            return response.read()
    except Exception:  # noqa: BLE001 - fall through to the CLI transports
        import shutil
        import subprocess

        if shutil.which("curl"):
            result = subprocess.run(
                ["curl", "-sSL", "--max-time", str(int(timeout)), url],
                capture_output=True,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout

        if shutil.which("gh") and "raw.githubusercontent.com/" in url:
            parts = url.split("raw.githubusercontent.com/", 1)[1].split("/")
            if len(parts) >= 4:
                owner, repo, ref, *rest = parts
                api = f"repos/{owner}/{repo}/contents/{'/'.join(rest)}?ref={ref}"
                result = subprocess.run(["gh", "api", api, "--jq", ".content"], capture_output=True)
                if result.returncode == 0 and result.stdout.strip():
                    import base64
                    return base64.b64decode(result.stdout.strip())

        raise RuntimeError("could not fetch upstream: urllib, curl and gh all failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--update", action="store_true", help="print the hash lines for a manual re-inline")
    args = parser.parse_args(argv)

    drift = False
    for name, url in TARGETS.items():
        path = REFERENCE_DIR / name
        if not path.is_file():
            print(f"MISSING  {name}")
            drift = True
            continue
        current = recorded_sha(path.read_text(encoding="utf-8"))
        try:
            body = fetch(url)
        except Exception as exc:  # noqa: BLE001 - network is external
            print(f"ERROR    {name}: {exc}")
            return 2
        actual = hashlib.sha256(normalize(body)).hexdigest()
        if current == actual:
            print(f"CURRENT  {name}  {actual[:16]}…")
        else:
            drift = True
            print(f"DRIFT    {name}")
            print(f"         recorded {current}")
            print(f"         upstream {actual}")
            print(f"         source   {url}")
            if args.update:
                print(f"         replace the header line with: upstream-sha256: {actual}")

    if drift:
        print("\nRe-read the upstream diff, re-inline what changed, then update the recorded hash.")
        return 1
    print("\nInlined Obsidian material matches upstream.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
