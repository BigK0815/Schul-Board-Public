"""Release-Prüfung für Schul-Monitor. Installiert niemals ungefragt Updates."""
import re
import requests

VERSION = "0.2.0"
RELEASES_URL = "https://github.com/BigK0815/Schul-Monitor/releases"
API_URL = "https://api.github.com/repos/BigK0815/Schul-Monitor/releases/latest"
PREVIOUS_API_URL = "https://api.github.com/repos/BigK0815/Schul-Board-Public/releases/latest"

def version_parts(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
    return tuple(map(int, match.groups())) if match else None

def check_for_update(session=None):
    """Gibt ('available'|'current'|'unavailable', Nachricht, URL) zurück."""
    http = session or requests
    try:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Schul-Monitor-Updatecheck"
        }
        response = http.get(API_URL, headers=headers, timeout=8)
        releases_url = RELEASES_URL
        if response.status_code == 404:
            response = http.get(PREVIOUS_API_URL, headers=headers, timeout=8)
            releases_url = response.url.replace("api.github.com/repos/", "github.com/").removesuffix("/latest")
        if response.status_code == 404:
            return ("unavailable", "Für die Updateprüfung ist derzeit kein Release erreichbar.", releases_url)
        if response.status_code in (401, 403):
            return ("unavailable",
                    "Das GitHub-Repository ist privat oder nicht öffentlich erreichbar. "
                    "Für die automatische Prüfung ist eine separate GitHub-Authentifizierung nötig.",
                    RELEASES_URL)
        response.raise_for_status()
        release = response.json()
        latest = str(release.get("tag_name") or "")
        latest_parts = version_parts(latest)
        current_parts = version_parts(VERSION)
        if latest_parts is None or current_parts is None:
            return ("unavailable", "Die Release-Versionsnummer ist nicht auswertbar.", RELEASES_URL)
        url = release.get("html_url") or releases_url
        if latest_parts > current_parts:
            return ("available", f"Version {latest} ist verfügbar (installiert: v{VERSION}).", url)
        return ("current", f"Schul-Monitor v{VERSION} ist aktuell.", url)
    except (requests.RequestException, ValueError, TypeError) as exc:
        return ("unavailable", "Updateprüfung derzeit nicht möglich: " + str(exc), RELEASES_URL)
