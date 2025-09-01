"""Standalone cleanup script used by GitHub Actions cleanup_only mode.
Removes stale WR_*.xlsx files in generated_docs keeping only the most recent
variant per (WR, WeekEnding) identity. Safe if directory absent.
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional, Tuple

OUTPUT_DIR = "generated_docs"

def identify(filename: str) -> Optional[Tuple[str, str]]:
    if not filename.startswith("WR_") or "_WeekEnding_" not in filename:
        return None
    parts = filename.split('_')
    try:
        wr = parts[1]
        week = parts[3]
    except IndexError:
        return None
    return wr, week

def find_latest(files: List[str]) -> Dict[Tuple[str,str], str]:
    latest: Dict[Tuple[str,str], str] = {}
    for f in files:
        ident = identify(f)
        if not ident:
            continue
        # lexical comparison works due to timestamp+hash ordering in name
        if ident not in latest or f > latest[ident]:
            latest[ident] = f
    return latest

def cleanup() -> None:
    if not os.path.isdir(OUTPUT_DIR):
        print("No output directory; nothing to clean")
        return
    files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("WR_") and f.lower().endswith('.xlsx')]
    latest = find_latest(files)
    keep = set(latest.values())
    removed: List[str] = []
    for f in files:
        if f not in keep:
            try:
                os.remove(os.path.join(OUTPUT_DIR, f))
                removed.append(f)
            except Exception as e:  # pragma: no cover - defensive
                print("Failed to remove", f, e)
    print(f"Kept {len(keep)} current files; removed {len(removed)} stale files")
    if removed:
        print("Removed list:")
        for r in removed:
            print(" -", r)

if __name__ == "__main__":
    cleanup()
