import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

users_redirects = {
    "vinoda mamatharai": "Vinoda mamatharai",
    "cbrescia": "Felino Volador",
    "abubakar a gwanki": "Gwanki",
    "sardeeq": "Sardeeq",
    "muralikrishna m": "Muralikrishna m",
    "brazal.dang": "Ballardmaize",
    "babulbaishya": "BabulB",
    "micheal kaluba": "MichealKal",
    "mp1999": "TypeInfo",
    "premchand murmu thakur": "Nacharhopon",
    "учитель": "Валентина Кодола",
    "bhupendra shrestha": "श्रेष्ठ भूपेन्द्र",
}


def load_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Load credentials from .env file.

    Returns:
        Tuple of (username, password) or (None, None) if not found
    """
    username = os.getenv("WIKIPEDIA_BOT_USERNAME")
    password = os.getenv("WIKIPEDIA_BOT_PASSWORD")

    if not username or not password:
        logger.error("WIKIPEDIA_BOT_USERNAME and/or WIKIPEDIA_BOT_PASSWORD not found in .env file")
        return None, None

    return username, password


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
