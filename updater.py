"""Release-Prüfung für Schul-Board. Installiert niemals ungefragt Updates."""
import re
import requests

VERSION = "0.1.0"
RELEASES_URL = "https://github.com/BigK0815/Schul-Board-Public/releases"
API_URL = "https://api.github.com/repos/BigK0815/Schul-Board-Public/releases/latest"

def version_parts(value):
    """Nur numerische Versionsnummern vergleichen (z.B. v0.2.1)."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
    return tuple(map(int, match.groups())) if match else None

def check_for_update(session=None):
    """Gibt ('available'|'current'|'unavailable', Nachricht, URL) zurück.

    Private Repositories liefern ohne GitHub-Authentifizierung HTTP 404.
    Niemals den beste.schule-Token an GitHub senden.
    """
    http = session or requests
    try:
        response = http.get(API_URL, headers={"Accept": "application/vnd.github+json",
                                             "User-Agent": "Schul-Board-Updatecheck"},
                            timeout=8)
        if response.status_code in (401, 403, 404):
            return ("unavailable",
                    "GitHub Releases sind nicht öffentlich abrufbar. "
                    "Bei einem privaten Repository ist dafür eine separate "
                    "GitHub-Authentifizierung nötig. Bitte Releases im Browser prüfen.",
                    RELEASES_URL)
        response.raise_for_status()
        release = response.json()
        latest = str(release.get("tag_name") or "")
        latest_parts = version_parts(latest)
        current_parts = version_parts(VERSION)
        if latest_parts is None or current_parts is None:
            return ("unavailable", "Die Release-Versionsnummer ist nicht auswertbar.", RELEASES_URL)
        url = release.get("html_url") or RELEASES_URL
        if latest_parts > current_parts:
            return ("available", f"Version {latest} ist verfügbar (installiert: v{VERSION}).", url)
        return ("current", f"Schul-Board v{VERSION} ist aktuell.", url)
    except (requests.RequestException, ValueError, TypeError) as exc:
        return ("unavailable", "Updateprüfung derzeit nicht möglich: " + str(exc), RELEASES_URL)
