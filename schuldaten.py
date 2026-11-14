"""Local cache and refresh intervals for beste.schule."""
import hashlib
import json
import os
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic

import requests

BASE = 'https://beste.schule/api'
# Historischer Datenordner: identisch mit verwaltung.py halten.
CACHE_DIR = Path(os.environ.get('APPDATA', str(Path.home()))) / 'StundenplanBoard'
SUBSTITUTION_SECONDS = 300


def student_id(student):
    value = student['id']
    if value is None or value == '':
        raise ValueError('Ein Mitglied hat keine Schüler-ID.')
    return str(value)


class SchoolData:
    """Use under the board's cache lock, including manual refreshes."""

    def __init__(self, token):
        self.token = token
        self.token_key = hashlib.sha256(token.encode()).hexdigest()
        self.session = requests.Session()
        self.session.headers.update({'Authorization': 'Bearer ' + token,
                                     'Accept': 'application/json'})
        self.days = {}
        self.snapshots = {}
        self.group_retry_at = 0
        self.group_error = ''
        self.timetable_retry_at = 0
        self.timetable_error = None

    def get(self, path, params=None, optional=False):
        response = self.session.get(BASE + path, params=params, timeout=30)
        if optional and response.status_code in (204, 404):
            return None
        response.raise_for_status()
        return response.json()

    def read(self, name):
        if name not in self.snapshots:
            self.snapshots[name] = self.load_snapshot(name, self.token_key)
        return self.snapshots[name]

    @staticmethod
    def load_snapshot(name, token_key):
        try:
            payload = json.loads((CACHE_DIR / (name + '.json')).read_text(encoding='utf-8'))
            if payload['scope'] == token_key:
                return datetime.fromisoformat(payload['updated']), payload['data']
        except (OSError, KeyError, TypeError, ValueError):
            pass
        return None, None

    def write(self, name, updated, data):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=CACHE_DIR,
                                delete=False) as output:
            temporary = Path(output.name)
            try:
                json.dump({'scope': self.token_key, 'updated': updated.isoformat(),
                           'data': data}, output, ensure_ascii=False)
                output.close()
                temporary.replace(CACHE_DIR / (name + '.json'))
            finally:
                output.close()
                temporary.unlink(missing_ok=True)
        self.snapshots[name] = (updated, data)

    def timetable(self, now):
        updated, saved = self.read('stundenplan-cache')
        if updated and updated.date() == now.date():
            return saved
        if self.timetable_error is not None and monotonic() < self.timetable_retry_at:
            raise self.timetable_error
        try:
            payload = self.get('/time-tables/current')
            plan = payload.get('data', payload)
            if not isinstance(plan, dict) or not isinstance(plan.get('lessons'), list):
                raise ValueError('Unbekanntes Format des Stundenplans.')
            self.write('stundenplan-cache', now, plan)
        except (requests.RequestException, ValueError, AttributeError, OSError) as error:
            self.timetable_error = error
            self.timetable_retry_at = monotonic() + SUBSTITUTION_SECONDS
            raise
        self.timetable_error = None
        return plan

    def lesson_times(self, now):
        updated, saved = self.read('unterrichtszeiten-cache')
        if updated and updated.date() == now.date():
            return saved
        try:
            payload = self.get('/time-table-times/current', optional=True) or {}
            lessons = (payload.get('data') or {}).get('lessons') or []
            times = {}
            for lesson in lessons:
                number = int(lesson['nr'])
                start, end = (time.fromisoformat(lesson[key]) for key in ('from', 'to'))
                if number >= 0 and start < end:
                    times[str(number)] = {'start': start.strftime('%H:%M'),
                                          'end': end.strftime('%H:%M')}
        except (requests.RequestException, AttributeError, KeyError, TypeError, ValueError):
            times = {}
        self.snapshots['unterrichtszeiten-cache'] = (now, times)
        if times:
            try:
                self.write('unterrichtszeiten-cache', now, times)
            except OSError:
                pass
        return times

    def substitution_days(self, days):
        wanted = {day.isoformat() for day in days}
        self.days = {key: value for key, value in self.days.items()
                     if key in wanted or monotonic() - value[0] < SUBSTITUTION_SECONDS}
        for day in days:
            day_iso = day.isoformat()
            previous = self.days.get(day_iso)
            if previous is None or monotonic() - previous[0] >= SUBSTITUTION_SECONDS:
                try:
                    payload = self.get('/substitution-plans/days/' + day_iso, optional=True)
                    day_data = None if payload is None else payload['data']
                    if day_data is not None and (not isinstance(day_data, dict)
                                                 or str(day_data.get('date', ''))[:10] != day_iso
                                                 or not isinstance(day_data.get('lessons'), list)):
                        raise ValueError('Unerwartete Antwort zum Vertretungsplan: ' + day_iso)
                    self.days[day_iso] = (monotonic(), day_data)
                except (requests.RequestException, ValueError, KeyError, TypeError) as error:
                    self.days[day_iso] = (monotonic(), error)
        for key in wanted:
            _, value = self.days[key]
            if isinstance(value, Exception):
                raise value
        return tuple(self.days[day.isoformat()] for day in days)

    def collection(self, path, params=None):
        page = 1
        while page <= 1000:
            payload = self.get(path, {**(params or {}), 'page': page})
            rows = payload['data']
            if not isinstance(rows, list):
                raise ValueError('Ungültige Liste von der API.')
            yield from rows
            meta = payload.get('meta') or {}
            links = payload.get('links') or {}
            if page >= int(meta.get('last_page', page)) and not links.get('next'):
                return
            page += 1
        raise ValueError('Die API-Liste konnte nicht vollständig geladen werden.')

    def group_snapshot(self, now, force=False):
        updated, saved = self.read('gruppen-cache')
        if not force and ((updated and now - updated < timedelta(days=7))
                          or monotonic() < self.group_retry_at):
            return updated, saved
        try:
            groups = list(self.collection('/groups', {'include': 'students,level'}))
            years = {str(group['year_id']) for group in groups if group.get('year_id') is not None}
            if len(years) > 1:
                today = now.date().isoformat()
                year_ids = {str(year['id']) for year in self.collection('/years')
                            if str(year['from'])[:10] <= today <= str(year['to'])[:10]}
                if len(year_ids) != 1:
                    raise ValueError('Das aktuelle Schuljahr konnte nicht eindeutig bestimmt werden.')
                groups = [group for group in groups if str(group.get('year_id')) in year_ids]
            groups = [group for group in groups if group.get('local_id') or group.get('name')]
            if not groups or any(not isinstance(group.get('students'), list) for group in groups):
                raise ValueError('Die API liefert keine vollständigen Gruppenmitgliedschaften.')
            classes_by_student = {}
            mapping = {}
            grades = {}
            for group in groups:
                if group.get('meta') in (1, '1'):
                    name = group.get('local_id') or group['name']
                    mapping[name] = [name]
                    level = group.get('level') or {}
                    label = str(level.get('name', ''))
                    match = re.fullmatch(r'(?:Jahrgang|Klassenstufe|Klasse|Stufe|Jg\.?)?\s*(1[0-3]|[1-9])',
                                         label.strip(), re.IGNORECASE)
                    if match:
                        grades[name] = int(match[1])
                    for student in group['students']:
                        classes_by_student.setdefault(student_id(student), set()).add(name)
            if not mapping:
                raise ValueError('Die API liefert keine Hauptklassen.')
            for group in groups:
                if group.get('meta') in (0, '0'):
                    name = group.get('local_id') or group['name']
                    targets = set(mapping.get(name, ()))
                    for student in group['students']:
                        targets.update(classes_by_student.get(student_id(student), ()))
                    mapping[name] = sorted(targets)
            self.write('jahrgaenge-cache', now, grades)
            self.write('gruppen-cache', now, mapping)
        except (requests.RequestException, TypeError, ValueError, KeyError, OSError) as error:
            self.group_retry_at = monotonic() + 3600
            self.group_error = str(error)
            if force:
                raise
            return updated, saved
        self.group_retry_at = 0
        self.group_error = ''
        return now, mapping
