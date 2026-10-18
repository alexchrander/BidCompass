"""TED publishes EU tender notices, including Portuguese contract notices."""

from __future__ import annotations

from typing import Any

from ingest.common import post, save_raw

SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
QUERY = 'buyer-country=PRT AND notice-type=cn-standard'
SCOPE = "ALL"
PAGE_SIZE = 100


def fetch_notices() -> list[dict[str, Any]]:
    """Fetch all matching TED notices, saving each returned page as raw JSON."""
    notices: list[dict[str, Any]] = []
    page = 1
    while True:
        response = post(
            SEARCH_URL,
            {
                "query": QUERY,
                "scope": SCOPE,
                "page": page,
                "limit": PAGE_SIZE,
            },
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected TED API response on page {page}: expected a JSON object.")
        save_raw("ted", f"page-{page:04d}.json", payload)

        page_notices = payload.get("notices", [])
        if not isinstance(page_notices, list):
            raise ValueError(f"Unexpected TED API response on page {page}: 'notices' is not a list.")
        notices.extend(page_notices)
        if not page_notices or len(page_notices) < PAGE_SIZE:
            break
        page += 1

    return notices


def main() -> None:
    notices = fetch_notices()
    print(f"Fetched {len(notices)} matching TED notices.")


if __name__ == "__main__":
    main()
