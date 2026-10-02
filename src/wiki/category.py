"""
Category membership helpers for MediaWiki.
"""

from __future__ import annotations

import logging
import time

import mwclient
import mwclient.errors
from mwclient.client import Site
from tqdm import tqdm

from ..config import TQDM_DISABLE

logger = logging.getLogger(__name__)


class CategoryService:
    """Fetch category size and member titles with retry/backoff."""

    def __init__(self, site: Site):
        self._site = site

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def count(self, category_name: str) -> int:
        """Return the total number of members (pages + files + subcats)."""
        # Ensure the title has the proper prefix
        category_name = self._ensure_prefix(category_name)
        params = {
            # "action": "query",
            "format": "json",
            "prop": "categoryinfo",
            "titles": category_name,
            "utf8": 1,
            "formatversion": "2",
        }
        try:
            data = self._site.get("query", **params)
        except Exception as e:
            logger.error("Failed to fetch category info for %s: %s", category_name, e)
            return 0

        # { "batchcomplete": true, "query": { "pages": [ { "pageid": 718741, "ns": 14, "title": "Category:Yemen", "categoryinfo": { "size": 19, "pages": 3, "files": 0, "subcats": 16, "hidden": false } } ] } }

        # Extract the page data dynamically since the page ID string changes
        pages = data.get("query", {}).get("pages") or []
        if not pages:
            return 0

        info = pages[0].get("categoryinfo") or {}
        # {'size': 354, 'pages': 1, 'files': 309, 'subcats': 44}
        return int(info.get("size") or 0)

    def member_titles(
        self,
        category_name: str,
        *,
        namespace: int | None = None,
        total_pages: int | None = None,
        max_items: int | None = None,
    ) -> list[str]:
        """
        Paginate ``list=categorymembers`` and return all member titles.

        ``namespace``:
          - ``0``  → articles only (``cmnamespace``)
          - ``6``  → files (``cmtype=file``)
          - ``14`` → subcategories (``cmtype=subcat``)
        """
        category_name = self._ensure_prefix(category_name)
        limit = max_items or total_pages
        logger.info(
            "Fetching members of %s (expected ≈ %s)",
            category_name,
            limit,
        )

        params: dict = {
            # "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": category_name,
            # "cmtype": "file",
            "cmlimit": "max",
        }

        if namespace is not None:
            if namespace == 14:
                params["cmtype"] = "subcat"
            elif namespace == 6:
                params["cmtype"] = "file"
            else:
                params["cmnamespace"] = str(namespace)

        all_titles: list[str] = []
        cmcontinue: str | None = None
        delay = 0.1
        max_delay = 8.0

        # Initialize tqdm with the total expected items
        with tqdm(total=limit, desc="Fetching members", unit="item", disable=TQDM_DISABLE) as pbar:
            while True:
                if max_items is not None and len(all_titles) >= max_items:
                    break

                if cmcontinue:
                    params["cmcontinue"] = cmcontinue

                try:
                    data = self._site.get("query", **params)
                    delay = 0.1
                    members = data.get("query", {}).get("categorymembers") or []

                    # Extract titles
                    new_titles = [x.get("title", "") for x in members]
                    all_titles.extend(new_titles)

                    # Update the progress bar by the number of items fetched in this batch
                    pbar.update(len(new_titles))

                    logger.debug(
                        f"Fetched category members: {len(members)} page, (total: {len(all_titles)}/{total_pages})"
                    )

                    cmcontinue = data.get("continue", {}).get("cmcontinue")
                    if not cmcontinue:
                        break

                    time.sleep(delay)

                except mwclient.errors.APIError as e:
                    if e.code == "invalidcategory":
                        logger.warning("Invalid category: %s", category_name)
                        break
                    # Non-invalidcategory API errors: log and retry with backoff
                    logger.error("API error (code=%s): %s", e.code, e)
                    if delay >= max_delay:
                        logger.error("Max delay reached, stopping retries")
                        break

                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
                    continue

                except Exception as e:
                    logger.error("API request failed: %s", e)
                    if delay >= max_delay:
                        break

                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
                    continue

        logger.info("Finished fetching %s members", len(all_titles))

        if max_items is not None:
            return all_titles[:max_items]

        return all_titles

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_prefix(name: str) -> str:
        if not name.startswith("Category:"):
            return f"Category:{name}"
        return name


__all__ = ["CategoryService"]
