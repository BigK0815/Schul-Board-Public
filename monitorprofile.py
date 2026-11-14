"""Stable monitor identities and profile settings."""
from pathlib import Path

FIELDS = (
    ('port', 'Port', 5001, 1024, 65535),
    ('board_width', 'Breite (Pixel)', 1920, 320, 16384),
    ('board_height', 'Höhe (Pixel)', 1080, 240, 16384),
    ('info_width', 'Infobreite (%)', 33, 10, 60),
    ('display_rows', 'Jahrgänge nebeneinander', 2, 1, 3),
    ('start_grade', 'Start-Jahrgang', 5, 1, 13),
    ('switch_seconds', 'Jahrgangswechsel (Sek.)', 15, 0, 3600),
    ('course_seconds', 'Kurswechsel (Sek.)', 4, 1, 3600),
    ('pdf_seconds', 'Aushangwechsel (Sek.)', 12, 2, 3600),
    ('cutoff_hour', 'Frühester Tageswechsel (Uhr)', 15, 0, 23),
)


def default_profile(number):
    return {**{key: default for key, _, default, _, _ in FIELDS},
            'id': number, 'name': f'Monitor {number}', 'port': 5000 + number,
            'visible_periods': list(range(1, 9)), 'hidden_grades': [], 'pdf_folder': ''}


def load_profiles(config):
    if 'monitors' in config:
        return config['monitors']
    profile = default_profile(1)
    for key in profile.keys() - {'id', 'name'}:
        if key in config:
            profile[key] = config[key]
    return [profile]


def validate_profiles(profiles, editor_port=None):
    if not 1 <= len(profiles) <= 10:
        raise ValueError('Bitte 1 bis 10 Monitore auswählen.')
    ports = {editor_port} if editor_port is not None else set()
    names = set()
    for item in profiles:
        name = item['name'].strip()
        if not name or name.casefold() in names:
            raise ValueError('Jeder Monitor benötigt einen eindeutigen Namen.')
        names.add(name.casefold())
        item['name'] = name
        for key, label, _, lower, upper in FIELDS:
            value = int(item[key])
            if not lower <= value <= upper:
                raise ValueError(f'{name}: {label} muss zwischen {lower} und {upper} liegen.')
            item[key] = value
        if item['port'] in ports:
            raise ValueError(f"{name}: Port {item['port']} ist bereits vergeben.")
        ports.add(item['port'])
        if not item['visible_periods']:
            raise ValueError(f'{name}: Bitte mindestens eine Stunde auswählen.')
        folder = item['pdf_folder'].strip()
        item['pdf_folder'] = str(Path(folder).expanduser().resolve()) if folder else ''
