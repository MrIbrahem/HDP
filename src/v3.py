""" """

import logging
import re
from typing import Any

from .api.home_wiki_cached import get_home_wikis_cached
from .api.mwclient_req import MwclientApi
from .api.xtools_cached import get_recent_editcounts_cached, get_recent_editcounts_offline
from .utils import calculate_age, users_redirects

BASE_PAGE = "Hardware donation program"

logger = logging.getLogger(__name__)


def extract_country(wikitext: str) -> str:
    """Extract the 'country your from' value from an application's wikitext.

    Handles patterns like:
        ; country your from:Rwanda
        ;country your from: Rwanda
        ; Country your from: Germany
    """
    pattern = r";\s*country\s+your\s+from\s*:\s*(.+)"
    match = re.search(pattern, wikitext, re.IGNORECASE)
    if match:
        country = match.group(1).strip()
        # Take only the first line (strip trailing wikitext artifacts)
        country = country.split("\n")[0].strip()
        # Remove trailing carriage return if present
        country = country.rstrip("\r").strip()
        return country
    return ""


def build_wikitable(rows) -> str:
    """rows: list of rows data."""
    lines = [
        '{| class="wikitable sortable"',
        "! Page",
        "! Last edited to application",
        "! User ",
        "! Country",
        "! Global edits",
        "! Edits in last 3 months",
        "! Age of account",
        "! Home Wiki",
        "! Approved",
    ]
    for _, row in rows.items():
        lines.append("|-")
        lines.append(f"| {row['page_link']}")
        lines.append(f"| {row['last_update']}")
        lines.append(f"| {row['user_link']}")
        lines.append(f"| {row.get('country', '')}")
        lines.append(f"| {row['editcount_str']}")
        lines.append(f"| {row['recent_editcount_str']}")
        lines.append(f"| {row['age']}")
        lines.append(f"| {row['home_wiki']}")
        lines.append("| ")

    lines.append("|}")

    return "\n".join(lines)


def solve_users_redirects(api: MwclientApi, data) -> list[dict[str, str]]:
    users = []
    for x in data:
        if not x["username"]:
            continue
        user_str = f"User:{x['username']}"
        users.append(user_str)

    users_redirects_api = api.solve_pages_redirects(users)

    new_data = []
    for x in data[:]:
        username = x["username"]
        user_str = f"User:{username}"
        if users_redirects_api.get(user_str):
            x["username"] = users_redirects_api[user_str].removeprefix("User:")

            if user_str == "User:Johnjoy12":
                logger.info(f"Johnjoy12 is a redirect to {x["username"]}")
                logger.info(x)

        new_data.append(x)

    return new_data


def load_rows(
    api: MwclientApi,
    subpages: list[str],
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
    base_page: str = BASE_PAGE,
) -> dict[str, Any]:

    data = []

    for sub in subpages:
        sub = sub.replace("_", " ")
        full_title = f"{base_page}/{sub}"
        user_name = sub.replace("(2nd Application)", "").split("/")[0].strip()
        username = users_redirects.get(user_name.lower()) or user_name

        # first letter upper (guard against empty username)
        if username:
            username = username[0].upper() + username[1:]

        data.append(
            {
                "full_title": full_title,
                "sub": sub,
                "username": username,
            }
        )

    new_data = solve_users_redirects(api, data)

    users = [x["username"] for x in new_data if x["username"]]

    # Batch-fetch application page wikitexts to extract country
    application_titles = [x["full_title"] for x in new_data]
    application_wikitexts = api.get_pages_wikitext(application_titles)
    logger.info(f"Fetched wikitext for {len(application_wikitexts)} application pages")

    editcounts = api.get_global_editcounts(users)
    logger.info(f"Loaded {len(editcounts)} editcounts for {len(users)} users")

    recent_editcounts = {}

    if not load_recent_editcounts:
        recent_editcounts = get_recent_editcounts_offline(users)
        logger.info(f"Loaded {len(recent_editcounts)} recent editcounts for {len(users)} users")
    else:
        recent_editcounts = get_recent_editcounts_cached(users)
        logger.info(f"Loaded {len(recent_editcounts)} recent editcounts for {len(users)} users")

    home_wikis = get_home_wikis_cached(api, users)
    logger.info(f"Loaded {len(home_wikis)} home wikis and registration for {len(users)} users")

    rows = {}
    for sub in new_data:
        editcount_str = unknown_placeholder
        age = ""
        user_link = unknown_placeholder
        home_wiki = unknown_placeholder
        recent_editcount_str = unknown_placeholder

        username = sub["username"]

        if username:
            user_link = f"[[User:{username}]]"

            home_data = home_wikis.get(username, {})
            if not home_data or not home_data.get("home"):
                logger.warning(f"Home data not found for {username}")

            home_wiki = home_data.get("home", unknown_placeholder)
            registration = home_data.get("registration", "")
            if registration:
                age = calculate_age(registration)

            # logger.debug(f"User: {username}, {age=}, {home_wiki=}")

            editcount = editcounts.get(username)
            if isinstance(editcount, int):
                editcount_str = f"{editcount:,}"

            recent_editcount = recent_editcounts.get(username)
            if recent_editcount is not None:
                recent_editcount_str = f"{recent_editcount:,}"
        else:
            logger.warning(f"Username not found for {sub['full_title']}")

        # Extract country from application page wikitext
        app_wikitext = application_wikitexts.get(sub["full_title"], "")
        country = extract_country(app_wikitext) if app_wikitext else ""

        row_data = {
            "age": age,
            "page_link": f"[[{sub['full_title']}]]",
            "last_update": f"{{{{#time:Y-m-d|{{{{REVISIONTIMESTAMP:{sub['full_title']}}}}}}}}}",
            "full_title": sub["full_title"],
            "user_link": user_link,
            "country": country,
            "editcount_str": editcount_str,
            "home_wiki": home_wiki,
            "recent_editcount_str": recent_editcount_str,
        }

        rows[sub["full_title"]] = row_data

    return rows


__all__ = [
    "load_rows",
    "build_wikitable",
]
