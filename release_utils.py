#!/usr/bin/env python3
"""Shared helpers for release scripts."""

import hashlib
import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def load_dotenv():
    env_file = Path(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def get_current_version() -> str:
    path = Path("version.py")
    if not path.exists():
        raise RuntimeError("version.py not found — run from the project root")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=")[1].strip().strip('"').strip("'")
    raise RuntimeError("Could not read __version__ from version.py")


def parse_version(v: str) -> tuple:
    try:
        parts = [int(x) for x in v.split(".")]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except ValueError:
        return (0, 0, 0)


def fmt(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


def prompt_version_bump() -> str | None:
    current = get_current_version()
    major, minor, patch = parse_version(current)
    while True:
        print()
        print("=" * 60)
        print("  VERSION BUMP")
        print("=" * 60)
        print(f"  Current : {current}")
        print()
        print(f"  1. Patch   (bug fix)    → {fmt(major, minor, patch + 1)}")
        print(f"  2. Minor   (feature)    → {fmt(major, minor + 1, 0)}")
        print(f"  3. Major   (breaking)   → {fmt(major + 1, 0, 0)}")
        print(f"  4. Custom")
        print(f"  5. Keep current         → {current}")
        print()
        choice = input("  Choice (1-5): ").strip()
        if choice == "1":   new = fmt(major, minor, patch + 1)
        elif choice == "2": new = fmt(major, minor + 1, 0)
        elif choice == "3": new = fmt(major + 1, 0, 0)
        elif choice == "4": new = input("  Enter version (e.g. 1.2.3): ").strip()
        elif choice == "5": new = current
        else:
            print("  Invalid choice.")
            continue
        print(f"\n  New version: {new}")
        if input("  Proceed? (y/n): ").strip().lower() != "y":
            print("  Cancelled.")
            return None
        return new


def update_version_file(new_version: str):
    path = Path("version.py")
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        for line in lines:
            if line.startswith("__version__"):
                f.write(f'__version__ = "{new_version}"\n')
            else:
                f.write(line)
    print(f"  ✓ version.py updated → {new_version}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def artifact_summary(label: str, path: Path | None, checksum: str | None):
    if path is None or not path.exists():
        print(f"  {label:<12}: (not produced)")
        return
    size_mb = path.stat().st_size / 1_048_576
    chk = (checksum[:16] + "…") if checksum else "n/a"
    print(f"  {label:<12}: {path.name}  ({size_mb:.1f} MB)  SHA-256: {chk}")
