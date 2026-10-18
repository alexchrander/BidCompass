"""Diário da República notices can reveal Portuguese procurement announcements."""

from __future__ import annotations

from datetime import date as Date


def fetch_notices(date: Date | str) -> list[dict[str, str]]:
    """Fetch DRE notices for a date; this source currently has no known public API."""
    # TODO: Diário da República 2.ª série Parte L has no known public API.
    _ = date
    return []


if __name__ == "__main__":
    print(f"Fetched {len(fetch_notices(Date.today()))} DRE notices.")
