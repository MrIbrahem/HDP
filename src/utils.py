import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)
# User-Agent header (required by Wikimedia)
USER_AGENT = "OWID-Meta Wiki-Categorizer/1.0 (https://github.com/MrIbrahem/OWID-categories; contact via GitHub)"

# -----------------------------------------
# wiki text parsers
# -----------------------------------------

_users_redirects = {
    "vinoda mamatharai": "Vinoda mamatharai",
    "cbrescia": "Felino Volador",
    "abubakar a gwanki": "Gwanki",
    "jaluj i": "Jaluj",
    "the living love": "Em-mustapha",
    "wiki ruhan": "Ruhan",
    "sardeeq": "Sardeeq",
    "muddyb 2": "Muddyb",
    "muralikrishna m": "Muralikrishna m",
    "brazal.dang": "Ballardmaize",
    "babulbaishya": "BabulB",
    "micheal kaluba": "MichealKal",
    "mp1999": "TypeInfo",
    "eugene233 2": "Eugene233",
    "premchand murmu thakur": "Nacharhopon",
    "учитель": "Валентина Кодола",
    "bhupendra shrestha": "श्रेष्ठ भूपेन्द्र",
}

users_redirects = {x.lower(): y for x, y in _users_redirects.items()}


def calculate_age(registration: str) -> str:
    """
    Input example:
        registration: "2008-07-24T01:18:05Z"
    Returns example:
        {{age in years and months |2008|07|24}}
    """
    try:
        # Parse the ISO 8601 string into a datetime object
        # Replacing 'Z' with '+00:00' to ensure compatibility with fromisoformat
        reg_date = datetime.fromisoformat(registration.replace("Z", "+00:00"))

        # Extract year, month, and day with zero-padding for month and day
        year = reg_date.year
        month = f"{reg_date.month:02d}"
        day = f"{reg_date.day:02d}"

        # Return the formatted template string
        return f"{{{{age in years and months|{year}|{month}|{day}}}}}"

    except Exception as e:
        logger.error(f"Error formatting age template: {e}")

        # Fallback template format in case of an error
        return registration


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
