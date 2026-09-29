"""
Category membership helpers for MediaWiki.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import mwclient.errors
from mwclient.client import Site
from tqdm import tqdm

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
        category_name = self._ensure_prefix(category_name)
        params = {
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

        pages = data.get("query", {}).get("pages") or []
        if not pages:
            return 0
        info = pages[0].get("categoryinfo") or {}
        return int(info.get("size") or 0)

    def member_titles(
        self,
        category_name: str,
        *,
        namespace: Optional[int] = None,
        total_pages: Optional[int] = None,
        max_items: Optional[int] = None,
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
            "format": "json",
            "list": "categorymembers",
            "cmtitle": category_name,
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
        cmcontinue: Optional[str] = None
        first = True
        delay = 0.1
        max_delay = 8.0

        with tqdm(total=limit, desc="Fetching members", unit="item") as pbar:
            while first or cmcontinue is not None:
                first = False
                if max_items is not None and len(all_titles) >= max_items:
                    break

                if cmcontinue:
                    params["cmcontinue"] = cmcontinue

                try:
                    data = self._site.get("query", **params)
                    delay = 0.1
                    members = data.get("query", {}).get("categorymembers") or []
                    new_titles = [m.get("title", "") for m in members]
                    all_titles.extend(new_titles)
                    pbar.update(len(new_titles))

                    if "continue" in data:
                        cmcontinue = data["continue"].get("cmcontinue")
                        time.sleep(delay)
                    else:
                        break

                except mwclient.errors.APIError as e:
                    if e.code == "invalidcategory":
                        logger.warning("Invalid category: %s", category_name)
                        break
                    logger.error("API error (code=%s): %s", e.code, e)
                    if delay >= max_delay:
                        break
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)

                except Exception as e:
                    logger.error("API request failed: %s", e)
                    if delay >= max_delay:
                        break
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)

        logger.info("Finished fetching %s members", len(all_titles))
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
