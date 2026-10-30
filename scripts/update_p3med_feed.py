#!/usr/bin/env python3
"""Bygger om P3 med-flodet och pushar till GitHub om nagot andrats.

Anvandning:  python scripts/update_p3med_feed.py

Skriver ut en rad forst:
    NO_CHANGE                  - flodet var redan aktuellt
    CHANGED <antal> avsnitt    - ny p3med.xml pushad
    ERROR <meddelande>         - nagot gick fel
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "p3med.xml"
GENERATOR = ROOT / "scripts" / "make_p3med_rss.py"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def main() -> int:
    build = subprocess.run(
        [sys.executable, str(GENERATOR)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if build.returncode != 0:
        print("ERROR generatorn misslyckades")
        print(build.stdout[-800:])
        print(build.stderr[-800:])
        return 1

    status = git("status", "--porcelain", "--", "p3med.xml")
    if status.returncode != 0:
        print("ERROR git status misslyckades")
        print(status.stderr[-500:])
        return 1
    if not status.stdout.strip():
        print("NO_CHANGE")
        return 0

    items = FEED.read_text(encoding="utf-8", errors="replace").count("<item>")

    add = git("add", "--", "p3med.xml")
    if add.returncode != 0:
        print("ERROR git add misslyckades")
        print(add.stderr[-500:])
        return 1

    commit = git("commit", "-m", f"Uppdaterar P3 med-flodet ({date.today().isoformat()})", "--", "p3med.xml")
    if commit.returncode != 0:
        print("ERROR commit misslyckades")
        print(commit.stdout[-500:] + commit.stderr[-500:])
        return 1

    push = git("push", "origin", "main")
    if push.returncode != 0:
        print("ERROR push misslyckades (andringen finns lokalt)")
        print(push.stderr[-500:])
        return 1

    print(f"CHANGED {items} avsnitt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
