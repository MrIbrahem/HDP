"""

"""

import logging
import time
from pathlib import Path

import mwclient
import mwclient.errors
import requests
from mwclient.client import Site
from tqdm import tqdm


API_URL = "https://meta.wikimedia.org/w/api.php"
BASE_PAGE = "Hardware donation program"
OUTPUT_FILE = Path(__file__).parent / "file.wiki"
OUTPUT_FILE_TABLE = Path(__file__).parent / "table.wiki"

# How many days back counts as "recent" for the recent-edits column.
RECENT_DAYS = 90

logger = logging.getLogger(__name__)

# User-Agent header (required by Wikimedia)
USER_AGENT = "OWID-Commons-Categorizer/1.0 (https://github.com/MrIbrahem/OWID-categories; contact via GitHub)"

# Always include a descriptive User-Agent header per Wikipedia API guidelines
HEADERS = {"User-Agent": USER_AGENT}

def get_category_count(category_name: str) -> int:
    # Ensure the title has the proper prefix
    if not category_name.startswith("Category:"):
        category_name = f"Category:{category_name}"

    url = API_URL
    params = {
        "action": "query",
        "format": "json",
        "prop": "categoryinfo",
        "titles": category_name,
        "utf8": 1,
        "formatversion": "2",
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        logger.error(f"Failed to fetch category info for {category_name}: {e}")
        return 0
    # { "batchcomplete": true, "query": { "pages": [ { "pageid": 718741, "ns": 14, "title": "Category:Yemen", "categoryinfo": { "size": 19, "pages": 3, "files": 0, "subcats": 16, "hidden": false } } ] } }
    # Extract the page data dynamically since the page ID string changes
    pages = data.get("query", {}).get("pages", [{}])
    if not pages:
        return 0

    info = pages[0].get("categoryinfo", {})
    # {'size': 354, 'pages': 1, 'files': 309, 'subcats': 44}
    size = info.get("size") or 0
    return size


def get_category_members_titles(
    site: Site,
    category_name: str,
    namespace: int | None = None,
    total_pages: int | None = None,
    max_items: int | None = None,
) -> list[str]:
    """
    Fetch all file titles from the OWID category using MediaWiki API with pagination.

    Returns:
        List of file titles (strings).
    """
    delay = 0.1  # seconds
    max_delay = 8.0

    total_pages = max_items or total_pages or get_category_count(category_name)
    logger.info(f"Starting to fetch files from {category_name}, total members: {total_pages}")

    params = {
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

    all_files = []
    first_request = True
    cmcontinue = None

    # Initialize tqdm with the total expected items
    with tqdm(total=total_pages, desc="Fetching members", unit="item") as pbar:
        while first_request or cmcontinue is not None:
            first_request = False
            if max_items and len(all_files) >= max_items:
                break

            if cmcontinue:
                params["cmcontinue"] = cmcontinue

            try:
                data = site.get("query", **params)
                members = data.get("query", {}).get("categorymembers", [])

                # Extract titles
                new_titles = [x.get("title", "") for x in members]
                all_files.extend(new_titles)

                # Update the progress bar by the number of items fetched in this batch
                pbar.update(len(new_titles))

                logger.debug(f"Fetched category members: {len(members)} page, (total: {len(all_files)}/{total_pages})")

                if "continue" in data:
                    cmcontinue = data["continue"].get("cmcontinue")
                    time.sleep(delay)
                else:
                    break

            except mwclient.errors.APIError as e:
                if e.code == "invalidcategory":
                    logger.warning(f"Invalid category: {category_name}")
                    break

            except Exception as e:
                logger.error("API request failed %s", str(e))
                if delay >= max_delay:
                    break

                time.sleep(delay)
                delay = min(delay * 2, max_delay)
                continue

    logger.info(f"Finished fetching {len(all_files)} pages.")
    return all_files

