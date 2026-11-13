"""Lokale Windows-Verwaltung des Stundenplan-Boards."""
import json
import os
import re
import socket
import threading
import tkinter as tk
import webbrowser
from datetime import time
from pathlib import Path
from tkinter import ttk, messagebox, filedialog, font

import keyring
import requests
from waitress import create_server
import board_engine
import updater
from zeitauswahl import choose_time
from verwaltungsstil import SettingsViewport, apply_style, card, toggle, flow_buttons, wrapping_label

ROOT = Path(os.environ.get('APPDATA', str(Path.home()))) / 'StundenplanBoard'
CONFIG = ROOT / 'einstellungen.json'
SERVICE = 'StundenplanBoard-beste.schule'
ACCOUNT = 'api-token'
DEFAULT = {'port':5000,'lan':False,'refresh_seconds':300,'switch_seconds':15,
           'course_seconds':4,'cutoff_hour':15,'start_grade':5,'display_rows':2,'pdf_folder':'','pdf_seconds':12,'group_mappings':{},'group_name_display':{},'lesson_times':{},'teacher_mappings':{},'room_mappings':{},'school_name':'Musterschule','school_logo':'','automatic_group_mapping':False}

def lesson_end(start, duration):
    if not 1 <= duration < 1440:
        raise ValueError('Bitte eine gültige Stundenlänge in ganzen Minuten eingeben.')
    start_time = time.fromisoformat(start)
    minutes = start_time.hour * 60 + start_time.minute + duration
    if minutes >= 1440:
        raise ValueError('Das Stundenende muss vor Mitternacht liegen.')
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def saved_duration(config):
    if 'lesson_duration' in config:
        return config['lesson_duration']
    for period in config['lesson_times'].values():
        start, end = (time.fromisoformat(period[key]) for key in ('start', 'end'))
        return (end.hour - start.hour) * 60 + end.minute - start.minute
    return 45


class Window:
    def __init__(self, root):
        self.root = root
        self.root.title('Schul-Board – Verwaltung')
        width = min(1200, max(1, root.winfo_screenwidth() - 64))
        height = min(920, max(1, root.winfo_screenheight() - 120))
        self.root.minsize(min(880, width), min(420, height))
        self.root.geometry(f'{width}x{height}')
        apply_style(root)
        ROOT.mkdir(parents=True, exist_ok=True)
        try: self.config = {**DEFAULT, **json.loads(CONFIG.read_text(encoding='utf-8'))}
        except (FileNotFoundError, ValueError): self.config = dict(DEFAULT)
        self.values = {}
        self.server = None
        self.running = False

        shell = ttk.Frame(root, padding=12)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='Schul-Board – Verwaltung',
                  font=('Segoe UI', 17, 'bold')).pack(anchor='w', pady=(0,10))
        body = ttk.Frame(shell)
        body.pack(fill='both', expand=True, side='top')
        navigation = ttk.Frame(body, style='Navigation.TFrame', padding=(8, 12))
        navigation.pack(side='left', fill='y', padx=(0,10))
        self.viewport = SettingsViewport(body)
        self.viewport.pack(side='left', fill='both', expand=True)
        self.pages = {}
        self.nav_buttons = {}
        self.nav_markers = {}
        for name in ('Allgemein', 'API & Server', 'Anzeige & PDFs',
                     'Lehrer', 'Räume', 'Klassen & Gruppen'):
            page = ttk.Frame(self.viewport.content, padding=12)
            self.pages[name] = page
            ttk.Label(page, text=name, style='Page.TLabel').pack(anchor='w', pady=(0, 16))
            nav_row = ttk.Frame(navigation, style='Navigation.TFrame')
            nav_row.pack(fill='x', pady=2)
            marker = ttk.Frame(nav_row, width=3, style='Navigation.TFrame')
            marker.pack(side='left', fill='y', pady=6)
            btn = ttk.Button(nav_row, text=name, width=19, style='Nav.TButton',
                             command=lambda n=name: self.show_page(n))
            btn.pack(side='left', fill='x', expand=True)
            self.nav_buttons[name] = btn
            self.nav_markers[name] = marker

        general = self.pages['Allgemein']
        tabs = ttk.Frame(general)
        tabs.pack(fill='x', pady=(0, 10))
        school_tab = ttk.Frame(general)
        times_tab = ttk.Frame(general)

        def select_tab(selected):
            for panel, button in tab_buttons.items():
                panel.pack_forget()
                button.configure(style='SelectedNav.TButton' if panel is selected else 'Nav.TButton')
            selected.pack(fill='x')
            self.viewport.canvas.yview_moveto(0)
            self.viewport.after_idle(self.viewport.refresh)

        tab_buttons = {}
        for panel, label in ((school_tab, 'Schule'), (times_tab, 'Unterrichtszeiten')):
            button = ttk.Button(tabs, text=label, command=lambda p=panel: select_tab(p))
            button.pack(side='left', padx=(0, 6))
            tab_buttons[panel] = button
        select_tab(school_tab)
        school = card(school_tab, 'Schule')
        fields = ttk.Frame(school, style='Card.TFrame')
        fields.pack(fill='x')
        fields.columnconfigure(1, weight=1)
        ttk.Label(fields, text='Schulname im Kopfbereich', style='Card.TLabel').grid(
            row=0, column=0, sticky='w', padx=(0, 16))
        self.school_name = tk.StringVar(value=self.config.get('school_name', ''))
        ttk.Entry(fields, textvariable=self.school_name).grid(row=0, column=1, sticky='ew')
        ttk.Separator(fields).grid(row=1, column=0, columnspan=2, sticky='ew', pady=12)
        logo_label = ttk.Frame(fields, style='Card.TFrame')
        logo_label.grid(row=2, column=0, sticky='w', padx=(0, 16))
        ttk.Label(logo_label, text='Schullogo (PNG)', style='Card.TLabel').pack(anchor='w')
        ttk.Label(logo_label, text='Leer = mitgeliefertes Logo',
                  style='CardMuted.TLabel').pack(anchor='w')
        logo_row = ttk.Frame(fields, style='Card.TFrame')
        logo_row.grid(row=2, column=1, sticky='ew')
        self.school_logo = tk.StringVar(value=self.config.get('school_logo', ''))
        ttk.Entry(logo_row, textvariable=self.school_logo, width=12).pack(
            side='left', fill='x', expand=True)
        ttk.Button(logo_row, text='Auswählen …', command=self.choose_school_logo).pack(
            side='left', padx=(8, 0))
        self.automatic_group_mapping = tk.BooleanVar(value=self.config.get('automatic_group_mapping', True))
        grouping = card(school_tab, 'Automatische Gruppenzuordnung')
        toggle(grouping, 'Gruppenregeln anwenden', self.automatic_group_mapping).pack(side='right')
        ttk.Label(grouping, text='Nur aktivieren, wenn die Gruppenkennungen zu den eingebauten Regeln passen.',
                  style='CardMuted.TLabel', wraplength=310).pack(side='left', fill='x', expand=True)

        times_card = card(times_tab, 'Unterrichtszeiten')
        duration_row = ttk.Frame(times_card, style='Card.TFrame')
        duration_row.pack(fill='x', pady=(0, 12))
        ttk.Label(duration_row, text='Stundenlänge (Minuten)', style='CardTitle.TLabel').pack(side='left')
        self.lesson_duration = tk.StringVar(value=str(saved_duration(self.config)))
        ttk.Entry(duration_row, textvariable=self.lesson_duration, width=6).pack(side='left', padx=12)
        times_table = ttk.Frame(times_card, style='Card.TFrame')
        times_table.pack(fill='x')
        for column, heading in enumerate(('Stunde', 'Beginn', 'Ende (automatisch)')):
            ttk.Label(times_table, text=heading, style='CardTitle.TLabel').grid(
                row=0, column=column, sticky='w', padx=6)
        self.lesson_times = {}
        for period in range(1, 11):
            ttk.Label(times_table, text=str(period), style='Card.TLabel').grid(
                row=period, column=0, padx=6)
            saved = self.config['lesson_times'].get(str(period), {})
            value = tk.StringVar(value=saved.get('start', ''))
            self.lesson_times[period] = value
            button_text = tk.StringVar()
            end_text = tk.StringVar()

            def refresh_time(*args, start=value, button=button_text, end=end_text):
                beginning = start.get()
                button.set(beginning or '—')
                try:
                    end.set(lesson_end(beginning, int(self.lesson_duration.get())) if beginning else '—')
                except ValueError:
                    end.set('—')

            value.trace_add('write', refresh_time)
            self.lesson_duration.trace_add('write', refresh_time)
            refresh_time()
            ttk.Button(times_table, textvariable=button_text, width=9,
                       command=lambda v=value, title=f'Beginn der {period}. Stunde':
                           choose_time(self.root, title, v)).grid(
                               row=period, column=1, padx=6, pady=2, sticky='ew')
            ttk.Label(times_table, textvariable=end_text, style='Card.TLabel').grid(
                row=period, column=2, padx=6, sticky='w')

        api = self.pages['API & Server']
        access = card(api, 'beste.schule API')
        ttk.Label(access, text='Token (sicher im Windows-Anmeldespeicher)',
                  style='Card.TLabel').pack(anchor='w')
        self.token = ttk.Entry(access, show='•')
        self.token.pack(fill='x', pady=7)
        ttk.Button(access, text='Token-Verbindung testen', command=self.test).pack(anchor='w')
        self.lan = tk.BooleanVar(value=self.config['lan'])
        server = card(api, 'Server')
        toggle(server, 'Im Schulnetz erreichbar', self.lan).pack(anchor='w')

        settings = self.pages['Anzeige & PDFs']
        options = ttk.Frame(card(settings, 'Anzeigeeinstellungen'), style='Card.TFrame')
        options.pack(fill='x')
        entries = [
            ('port','Server-Port',[5000,5050,8080]),
            ('refresh_seconds','Daten aktualisieren (Sekunden)',[60,120,300,600,900]),
            ('switch_seconds','Jahrgang wechseln (Sekunden)',[0,10,15,20,25,30]),
            ('course_seconds','Kurse durchblättern (Sekunden)',[2,3,4,5,6,8]),
            ('cutoff_hour','Tageswechsel (Uhrzeit)',[12,13,14,15,16,17,18]),
            ('start_grade','Start-Jahrgang',[5,6,7,8,9,10]),
            ('display_rows','Klassenstufen übereinander (Zeilen)',[1,2,3]),
            ('pdf_seconds','PDF-Seite anzeigen (Sekunden)',[5,8,10,12,15,20,30,45,60])]
        for i, (key, label, choices) in enumerate(entries):
            row = ttk.Frame(options, style='Card.TFrame')
            row.grid(row=i//2, column=i%2, sticky='ew', padx=(0, 8), pady=2)
            ttk.Label(row, text=label, style='Card.TLabel').pack(anchor='w')
            v = tk.StringVar(value=str(self.config[key]))
            self.values[key] = v
            ttk.Combobox(row, textvariable=v, values=choices,
                         state='readonly', width=12, style='Compact.TCombobox').pack(anchor='w')
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        pdf = card(settings, 'Infoboard-PDFs')
        ttk.Label(pdf, text='Ordner für Info-PDFs', style='Card.TLabel').pack(anchor='w')
        self.pdf_folder = tk.StringVar(value=str(self.config['pdf_folder']))
        pdfrow = ttk.Frame(pdf, style='Card.TFrame')
        pdfrow.pack(fill='x', pady=5)
        ttk.Entry(pdfrow, textvariable=self.pdf_folder).pack(side='left', fill='x', expand=True)
        ttk.Button(pdfrow, text='Auswählen …', command=self.choose_pdf_folder).pack(side='left', padx=5)

        for name, kind, desc in [
            ('Lehrer','teachers','Lehrerbezeichnungen und Anzeigenamen verwalten'),
            ('Räume','rooms','Raumbezeichnungen und Anzeigenamen verwalten'),
            ('Klassen & Gruppen','groups','Hauptklassen und bis zu 16 Gruppen zuordnen')]:
            page = card(self.pages[name], 'Zuordnungen')
            ttk.Label(page, text=desc, style='Card.TLabel').pack(anchor='w', pady=(0, 12))
            ttk.Button(page, text='Tabelle bearbeiten / Excel einfügen …',
                       command=lambda k=kind: self.open_mapping_editor(k)).pack(anchor='w')
            ttk.Label(page, text='Der Tabelleneditor öffnet sich in einem eigenen Fenster.',
                      style='CardMuted.TLabel').pack(anchor='w', pady=(8, 0))

        group_display = card(self.pages['Klassen & Gruppen'], 'Anzeige im Plan')
        ttk.Label(group_display, text='Mit Häkchen erscheint der Gruppenname, ohne Häkchen das Fachkürzel.',
                  style='CardMuted.TLabel', wraplength=420).pack(anchor='w', pady=(0, 10))
        self.group_name_options = {}
        self.group_name_list = ttk.Frame(group_display, style='Card.TFrame')
        self.group_name_list.pack(fill='x')
        self.group_name_list.bind('<Configure>', self.layout_group_name_options)
        self.group_name_columns = 0
        self.refresh_group_name_options()

        bottom = ttk.Frame(shell)
        bottom.pack(side='bottom', fill='x', before=body)
        ttk.Separator(bottom).pack(fill='x', pady=(8, 6))
        footer = ttk.Frame(bottom)
        footer.pack(side='bottom', fill='x', pady=(6, 0))
        ttk.Button(footer, text='Speichern', command=self.save, style='Accent.TButton')
        ttk.Button(footer, text='Im Browser öffnen', command=self.open)
        self.start_btn = ttk.Button(footer, text='Board starten', command=self.start)
        self.stop_btn = ttk.Button(footer, text='Server stoppen', command=self.stop, state='disabled')
        ttk.Button(footer, text='Beenden', command=self.close)
        ttk.Button(footer, text='Auf Updates prüfen', command=self.check_updates)
        flow_buttons(footer)
        statusbar = ttk.Frame(bottom)
        statusbar.pack(side='bottom', fill='x', pady=(7,0))
        self.status = tk.StringVar(value='Server ist gestoppt')
        ttk.Label(statusbar, textvariable=self.status, font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        self.address = tk.StringVar(value='')
        ttk.Label(statusbar, textvariable=self.address, style='Muted.TLabel').pack(anchor='w')
        self.viewport.bind_controls(self.viewport.content)
        self.show_page('Allgemein')
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def show_page(self, name):
        self.viewport.show(self.pages[name])
        for label, button in self.nav_buttons.items():
            button.configure(style='SelectedNav.TButton' if label == name else 'Nav.TButton')
            self.nav_markers[label].configure(
                style='Selection.TFrame' if label == name else 'Navigation.TFrame')


    def refresh_group_name_options(self):
        mapping = self.config.get('group_mappings') or {}
        groups = {group for group, targets in mapping.items()
                  if any(target.strip() != group for target in
                         (re.split('[,;]', targets) if isinstance(targets, str) else targets or [])
                         if target.strip())}
        for child in self.group_name_list.winfo_children():
            child.destroy()
        self.group_name_options = {
            group: self.group_name_options.get(group) or tk.BooleanVar(
                value=self.config['group_name_display'].get(
                    group, board_engine.default_group_name_display(group)))
            for group in sorted(groups, key=lambda name: [
                int(part) if part.isascii() and part.isdigit() else part
                for part in re.split(r'([0-9]+)', name.casefold().translate(str.maketrans('äöü', 'aou')))
            ])
        }
        for group, checked in self.group_name_options.items():
            option = ttk.Checkbutton(self.group_name_list, text=group, variable=checked,
                                     style='GroupName.TCheckbutton')
            self.viewport.bind_controls(option)
        if not self.group_name_options:
            ttk.Label(self.group_name_list, text='Noch keine Gruppen in der Zuordnungstabelle.',
                      style='CardMuted.TLabel').pack(anchor='w')
        self.group_name_columns = 0
        self.layout_group_name_options()

    def layout_group_name_options(self, _event=None):
        if not self.group_name_options:
            return
        options = self.group_name_list.winfo_children()
        column_width = max(option.winfo_reqwidth() for option in options) + 16
        columns = min(4, max(1, self.group_name_list.winfo_width() // column_width))
        if columns == self.group_name_columns:
            return
        for column in range(4):
            self.group_name_list.columnconfigure(column, weight=int(column < columns))
        for index, option in enumerate(options):
            row, column = divmod(index, columns)
            option.grid(row=row, column=column, sticky='w', pady=3, padx=(0, 8))
        self.group_name_columns = columns

    def open_mapping_editor(self, kind):
        """Editable mapping table with tab-separated Excel clipboard import/export."""
        if kind == "groups":
            return self.open_class_group_editor()
        specs = {
            'rooms': ('Räume', 'room_mappings', 'Raum laut API', 'Anzeige auf Board'),
            'teachers': ('Lehrer', 'teacher_mappings', 'Lehrer laut API', 'Anzeige auf Board'),
            'groups': ('Hauptklassen und Gruppen', 'group_mappings', 'API-Gruppe', 'Hauptklasse(n)'),
        }
        title, key, left_label, right_label = specs[kind]
        dialog = tk.Toplevel(self.root)
        dialog.title('Schul-Board – ' + title)
        dialog.geometry(f'{min(900, dialog.winfo_screenwidth() - 32)}x{min(710, dialog.winfo_screenheight() - 90)}')
        dialog.transient(self.root)
        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text=title, font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        wrapping_label(outer, text='Excel: zwei Spalten markieren, Strg+C und hier Strg+V. Mehrere Zeilen werden gemeinsam eingefügt. '
                  'Bei Gruppen: eine Zeile je Zuordnung oder mehrere Klassen durch Komma trennen.').pack(anchor='w', pady=(5, 9))
        data = dict(self.config.get(key) or {})
        if kind == 'groups':
            data = {k: (v if isinstance(v, list) else [v]) for k,v in data.items()}
        columns = ('source', 'target')
        table_area = ttk.Frame(outer)
        tree = ttk.Treeview(table_area, columns=columns, show='headings', selectmode='extended')
        tree.heading('source', text=left_label)
        tree.heading('target', text=right_label)
        tree.column('source', width=350)
        tree.column('target', width=440)
        sb = ttk.Scrollbar(table_area, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        xscroll = ttk.Scrollbar(table_area, orient='horizontal', command=tree.xview)
        tree.configure(xscrollcommand=xscroll.set)
        table_area.columnconfigure(0, weight=1)
        table_area.rowconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew')
        sb.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        def as_text(value):
            return ', '.join(value) if isinstance(value,list) else str(value)
        def redraw():
            tree.delete(*tree.get_children())
            for name in sorted(data, key=str.casefold):
                tree.insert('', 'end', iid=name, values=(name, as_text(data[name])))
        redraw()
        row = ttk.Frame(outer)

        row.columnconfigure(1, weight=1)
        source = tk.StringVar()
        target = tk.StringVar()
        ttk.Label(row,text=left_label+':').grid(row=0, column=0, sticky='w')
        ttk.Entry(row,textvariable=source,width=12).grid(row=0, column=1, sticky='ew', padx=5)
        ttk.Label(row,text=right_label+':').grid(row=1, column=0, sticky='w')
        ttk.Entry(row,textvariable=target,width=12).grid(row=1, column=1, sticky='ew', padx=5)
        def selected(_=None):
            ids=tree.selection()
            if len(ids)==1:
                source.set(ids[0]);target.set(as_text(data[ids[0]]))
        tree.bind('<<TreeviewSelect>>',selected)
        import re
        def parse_classes(value):
            parts=[x.strip() for x in re.split(r'[,;]',value) if x.strip()]
            invalid=[x for x in parts if not re.fullmatch(r'(?:10|[5-9])/\d+',x)]
            if invalid: raise ValueError('Ungültige Hauptklasse: '+', '.join(invalid))
            return list(dict.fromkeys(parts))
        def put(name,value,append=False):
            name=name.strip();value=value.strip()
            if not name:raise ValueError('Die API-Bezeichnung darf nicht leer sein.')
            if kind=='groups':
                classes=parse_classes(value)
                if append: classes=list(dict.fromkeys(data.get(name,[])+classes))
                if classes:data[name]=classes
                else:data.pop(name,None)
            else:
                if value:data[name]=value
                else:data.pop(name,None)
        def apply():
            try:put(source.get(),target.get());redraw()
            except ValueError as exc:messagebox.showerror('Eingabe prüfen',str(exc),parent=dialog)
        ttk.Button(row,text='Übernehmen',command=apply).grid(row=1, column=2)
        tools=ttk.Frame(outer)
        def delete():
            for name in tree.selection():data.pop(name,None)
            redraw()
        ttk.Button(tools,text='Ausgewählte entfernen',command=delete)
        def copy_rows(_=None):
            ids=tree.selection() or tree.get_children()
            content='\n'.join(name+'\t'+as_text(data[name]) for name in ids)
            dialog.clipboard_clear();dialog.clipboard_append(content)
            return 'break'
        ttk.Button(tools,text='Auswahl nach Excel kopieren',command=copy_rows)
        def paste_rows(_=None):
            try:raw=dialog.clipboard_get()
            except tk.TclError:return 'break'
            count=0;errors=[]
            for lineno,line in enumerate(raw.splitlines(),1):
                if not line.strip():continue
                cells=line.split('\t')
                if len(cells)<2:
                    errors.append(f'Zeile {lineno}: zwei Excel-Spalten benötigt');continue
                name=cells[0].strip();value=cells[1].strip()
                if name.casefold() in ('api-gruppe','raum laut api','lehrer laut api','hauptklasse'):
                    continue
                try:put(name,value,append=(kind=='groups'));count+=1
                except ValueError as exc:errors.append(f'Zeile {lineno}: {exc}')
            redraw()
            status.set(f'{count} Zeilen übernommen.' + (' Fehler: '+'; '.join(errors[:4]) if errors else ''))
            return 'break'
        ttk.Button(tools,text='Aus Excel einfügen (Strg+V)',command=paste_rows)
        tree.bind('<Control-v>',paste_rows)
        tree.bind('<Control-V>',paste_rows)
        tree.bind('<Control-c>',copy_rows)
        status=tk.StringVar(value='Noch nicht gespeicherte Änderungen werden erst durch „Speichern“ übernommen.')
        status_label = wrapping_label(outer,textvariable=status)
        def fetch():
            token=self.get_token()
            if not token:
                messagebox.showwarning('API-Token fehlt','Bitte zuerst einen API-Token eingeben.',parent=dialog);return
            status.set('Lade Bezeichnungen aus beste.schule …')
            def work():
                try:
                    headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
                    if kind=='groups':
                        response=requests.get('https://beste.schule/api/groups',headers=headers,timeout=40)
                        response.raise_for_status()
                        payload=response.json();items=payload.get('data',payload) if isinstance(payload,dict) else payload
                        names={str(x.get('local_id') or x.get('name') or '').strip() for x in items if isinstance(x,dict)}
                    else:
                        response=requests.get('https://beste.schule/api/time-tables/current',headers=headers,timeout=60)
                        response.raise_for_status()
                        payload=response.json();table=payload.get('data',payload)
                        field='rooms' if kind=='rooms' else 'teachers'
                        names={str(x.get('local_id') or x.get('name') or '').strip()
                               for lesson in table.get('lessons',[]) for x in (lesson.get(field) or []) if isinstance(x,dict)}
                    names.discard('')
                    def show():
                        for name in names:
                            if kind=='groups':data.setdefault(name,[])
                            else:data.setdefault(name,name)
                        redraw();status.set(f'{len(names)} API-Bezeichnungen geladen; vorhandene Zuordnungen beibehalten.')
                    dialog.after(0,show)
                except Exception as exc:
                    msg=str(exc)
                    dialog.after(0,lambda:status.set('API-Abruf fehlgeschlagen: '+msg))
            threading.Thread(target=work,daemon=True).start()
        ttk.Button(tools,text='Bezeichnungen aus API übernehmen',command=fetch)
        flow_buttons(tools)
        def save_mapping():
            try:
                self.config[key]=data
                CONFIG.parent.mkdir(parents=True,exist_ok=True)
                CONFIG.write_text(json.dumps(self.config,indent=2,ensure_ascii=False),encoding='utf-8')
                board_engine.SETTINGS[key]=dict(data)
                board_engine.cache['at']=0
                dialog.destroy()
                self.status.set(title+' gespeichert – Änderungen beim nächsten Datenabruf sichtbar')
            except Exception as exc:messagebox.showerror('Speichern fehlgeschlagen',str(exc),parent=dialog)
        save_button = ttk.Button(outer,text='Zuordnungen speichern', style='Accent.TButton', command=save_mapping)
        save_button.pack(side='bottom', anchor='e',pady=5)
        status_label.pack(side='bottom', anchor='w',pady=6)
        tools.pack(side='bottom', fill='x',pady=3)
        row.pack(side='bottom', fill='x', pady=7)
        table_area.pack(fill='both', expand=True)

    def open_class_group_editor(self):
        """One main class per row, 16 group columns; Excel TSV and semicolons supported."""
        import re
        dialog = tk.Toplevel(self.root)
        dialog.title('Schul-Board – Hauptklassen und Gruppen')
        dialog.geometry(f'{min(1250, dialog.winfo_screenwidth() - 32)}x{min(730, dialog.winfo_screenheight() - 90)}')
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Hauptklassen und Gruppen', font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        wrapping_label(frame, text='Spalte A: Hauptklasse; Spalten B–Q: bis zu 16 Gruppen. Excel-Bereich kopieren und mit Strg+V einfügen. '
                  'Alternativ mehrere Gruppen mit Semikolon in einer Zelle trennen. Die Hauptklasse gilt automatisch als Gruppe.').pack(anchor='w', pady=(4, 8))

        # Stored format is API group -> list of main classes. Convert for editing.
        old = self.config.get('group_mappings') or {}
        data = {}
        for group, classes in old.items():
            if isinstance(classes, str):
                classes = [x.strip() for x in re.split('[,;]', classes) if x.strip()]
            for cls in classes:
                cls = str(cls).strip()
                if cls and group != cls:
                    data.setdefault(cls, [])
                    if group not in data[cls]:
                        data[cls].append(group)
        # Also expose classes without extra groups if they were explicitly stored.
        for group, classes in old.items():
            if group in classes if isinstance(classes, list) else False:
                data.setdefault(group, [])

        cols = ('class',) + tuple(f'g{i}' for i in range(1, 17))
        table_area = ttk.Frame(frame)
        tree = ttk.Treeview(table_area, columns=cols, show='headings', selectmode='extended')
        tree.heading('class', text='Hauptklasse')
        table_font = font.nametofont('TkDefaultFont', root=dialog)
        class_width = max(115, table_font.measure('Hauptklasse') + 24)
        tree.column('class', width=class_width, stretch=False)
        for i in range(1, 17):
            col = f'g{i}'
            tree.heading(col, text=f'Gruppe {i}')
            tree.column(col, width=max(115, table_font.measure('Gruppe 16') + 24), stretch=False)
        yscroll = ttk.Scrollbar(table_area, orient='vertical', command=tree.yview)
        xscroll = ttk.Scrollbar(table_area, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        table_area.columnconfigure(0, weight=1)
        table_area.rowconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        status = tk.StringVar(value='Änderungen werden erst mit „Zuordnungen speichern“ übernommen.')

        def sort_class(cls):
            match = re.fullmatch(r'(\d+)/(\d+)', cls)
            return (int(match.group(1)), int(match.group(2))) if match else (999, cls)

        def redraw():
            tree.delete(*tree.get_children())
            for cls in sorted(data, key=sort_class):
                groups = data[cls]
                tree.insert('', 'end', iid=cls, values=[cls] + groups[:16] + [''] * max(0, 16-len(groups)))

        def parse_groups(cells):
            result = []
            for cell in cells:
                for group in str(cell).split(';'):
                    group = group.strip()
                    if group and group not in result:
                        result.append(group)
            return result

        def put(cls, cells, append=False):
            cls = cls.strip()
            if not cls or len(cls) > 60:
                raise ValueError('Ungültige Hauptklasse: ' + cls)
            groups = parse_groups(cells)
            groups = [g for g in groups if g != cls]
            if append:
                groups = list(dict.fromkeys(data.get(cls, []) + groups))
            if len(groups) > 16:
                raise ValueError(f'{cls}: mehr als 16 Gruppen ({len(groups)})')
            data[cls] = groups

        redraw()
        editor = ttk.Frame(frame)

        cls_var = tk.StringVar()
        groups_var = tk.StringVar()
        editor.columnconfigure(1, weight=1)
        ttk.Label(editor, text='Hauptklasse:').grid(row=0, column=0, sticky='w')
        ttk.Entry(editor, textvariable=cls_var, width=10).grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(editor, text='Gruppen:').grid(row=1, column=0, sticky='w')
        ttk.Entry(editor, textvariable=groups_var, width=12).grid(row=1, column=1, sticky='ew', padx=5)

        def select_row(_=None):
            selected = tree.selection()
            if len(selected) == 1:
                cls = selected[0]
                cls_var.set(cls)
                groups_var.set('; '.join(data[cls]))
        tree.bind('<<TreeviewSelect>>', select_row)

        def apply():
            try:
                put(cls_var.get(), [groups_var.get()])
                redraw()
                status.set('Zeile übernommen. Zum dauerhaften Speichern unten klicken.')
            except ValueError as exc:
                messagebox.showerror('Eingabe prüfen', str(exc), parent=dialog)
        ttk.Button(editor, text='Zeile übernehmen', command=apply).grid(row=1, column=2, sticky='e')

        buttons = ttk.Frame(frame)


        def paste(_=None):
            try:
                raw = dialog.clipboard_get()
            except tk.TclError:
                return 'break'
            errors = []
            count = 0
            for n, line in enumerate(raw.splitlines(), 1):
                if not line.strip():
                    continue
                cells = line.split('\t')
                if len(cells) < 2:
                    errors.append(f'Zeile {n}: mindestens zwei Spalten benötigt')
                    continue
                if cells[0].strip().casefold() in ('hauptklasse', 'klasse'):
                    continue
                try:
                    put(cells[0], cells[1:], append=True)
                    count += 1
                except ValueError as exc:
                    errors.append(f'Zeile {n}: {exc}')
            redraw()
            status.set(f'{count} Klassenzeilen eingefügt.' + (' Fehler: ' + '; '.join(errors[:4]) if errors else ''))
            return 'break'

        def copy(_=None):
            ids = tree.selection() or tree.get_children()
            content = '\n'.join('\t'.join([cls] + data[cls] + [''] * (16-len(data[cls]))) for cls in ids)
            dialog.clipboard_clear()
            dialog.clipboard_append(content)
            return 'break'

        def remove():
            for cls in tree.selection():
                data.pop(cls, None)
            redraw()

        ttk.Button(buttons, text='Aus Excel einfügen (Strg+V)', command=paste)
        ttk.Button(buttons, text='Nach Excel kopieren (Strg+C)', command=copy)
        ttk.Button(buttons, text='Ausgewählte Klassen entfernen', command=remove)
        tree.bind('<Control-v>', paste)
        tree.bind('<Control-V>', paste)
        tree.bind('<Control-c>', copy)
        tree.bind('<Control-C>', copy)

        def fetch():
            token = self.get_token()
            if not token:
                messagebox.showwarning('API-Token fehlt', 'Bitte zuerst einen API-Token eingeben.', parent=dialog)
                return
            status.set('Lade Hauptklassen aus dem Stundenplan …')
            def work():
                try:
                    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
                    response = requests.get('https://beste.schule/api/time-tables/current', headers=headers, timeout=60)
                    response.raise_for_status()
                    payload = response.json()
                    table = payload.get('data', payload)
                    names = {str((lesson.get('group') or {}).get('local_id') or '').strip()
                             for lesson in table.get('lessons', [])}
                    classes = {x for x in names if re.fullmatch(r'(?:10|[5-9])/\d+', x)}
                    if not classes:
                        classes = {x for x in names if re.fullmatch(r'(?:10|[5-9])[a-zA-Z]', x)}
                    def show():
                        for cls in classes:
                            data.setdefault(cls, [])
                        redraw()
                        status.set(f'{len(classes)} Hauptklassen erkannt. Gruppen bitte zuordnen.')
                    dialog.after(0, show)
                except Exception as exc:
                    msg = str(exc)
                    dialog.after(0, lambda: status.set('API-Abruf fehlgeschlagen: ' + msg))
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(buttons, text='Hauptklassen aus API übernehmen', command=fetch)
        flow_buttons(buttons)
        status_label = wrapping_label(frame, textvariable=status)

        def save():
            # Keep the engine's established group -> classes representation.
            mapping = {}
            for cls, groups in data.items():
                mapping.setdefault(cls, []).append(cls)
                for group in groups:
                    mapping.setdefault(group, []).append(cls)
            try:
                self.config['group_mappings'] = mapping
                CONFIG.parent.mkdir(parents=True, exist_ok=True)
                CONFIG.write_text(json.dumps(self.config, indent=2, ensure_ascii=False), encoding='utf-8')
                board_engine.SETTINGS['group_mappings'] = mapping
                board_engine.cache['at'] = 0
                self.refresh_group_name_options()
                self.status.set('Klassen- und Gruppenzuordnungen gespeichert')
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror('Speichern fehlgeschlagen', str(exc), parent=dialog)
        save_button = ttk.Button(frame, text='Zuordnungen speichern', style='Accent.TButton', command=save)
        save_button.pack(side='bottom', anchor='e', pady=5)
        status_label.pack(side='bottom', anchor='w', pady=5)
        buttons.pack(side='bottom', fill='x', pady=5)
        editor.pack(side='bottom', fill='x', pady=(9, 4))
        table_area.pack(fill='both', expand=True)

    def choose_school_logo(self):
        path = filedialog.askopenfilename(title='Schullogo auswählen', filetypes=[('PNG-Bilder','*.png')])
        if path: self.school_logo.set(path)

    def choose_pdf_folder(self):
        folder=filedialog.askdirectory(title='Ordner für Info-PDFs auswählen',initialdir=self.pdf_folder.get() if Path(self.pdf_folder.get()).is_dir() else str(Path.home()))
        if folder:self.pdf_folder.set(folder)

    def get_token(self):
        return self.token.get().strip() or keyring.get_password(SERVICE,ACCOUNT) or ''

    def save(self):
        if self.running:
            messagebox.showwarning('Server läuft','Bitte den Server zuerst stoppen, bevor du Einstellungen änderst.')
            return False
        try:
            cfg={key:int(var.get()) for key,var in self.values.items()}
            cfg['lan']=self.lan.get()
            cfg['school_name']=self.school_name.get().strip() or 'Musterschule'
            cfg['school_logo']=self.school_logo.get().strip()
            if cfg['school_logo'] and (not Path(cfg['school_logo']).is_file() or Path(cfg['school_logo']).suffix.lower() != '.png'):
                raise ValueError('Bitte eine vorhandene PNG-Datei als Schullogo auswählen.')
            cfg['automatic_group_mapping']=self.automatic_group_mapping.get()
            for mapping_key in ('group_mappings','teacher_mappings','room_mappings'):
                cfg[mapping_key]=self.config.get(mapping_key,{})
            group_name_display = dict(self.config['group_name_display'])
            for group, checked in self.group_name_options.items():
                if checked.get() == board_engine.default_group_name_display(group):
                    group_name_display.pop(group, None)
                else:
                    group_name_display[group] = checked.get()
            cfg['group_name_display'] = group_name_display
            duration = self.lesson_duration.get().strip()
            if not re.fullmatch(r'[0-9]{1,4}', duration) or not 1 <= int(duration) < 1440:
                raise ValueError('Bitte eine gültige Stundenlänge in ganzen Minuten eingeben.')
            duration = int(duration)
            cfg['lesson_duration'] = duration
            lesson_times = {}
            previous_end = ''
            for period, value in self.lesson_times.items():
                start = value.get()
                if not start:
                    continue
                try:
                    end = lesson_end(start, duration)
                except ValueError as exc:
                    raise ValueError(f'{period}. Stunde: {exc}') from exc
                if start < previous_end:
                    raise ValueError(f'{period}. Stunde: Die Unterrichtszeiten überschneiden sich oder sind falsch angeordnet.')
                lesson_times[str(period)] = {'start': start, 'end': end}
                previous_end = end
            cfg['lesson_times'] = lesson_times
            pdf_folder = self.pdf_folder.get().strip()
            cfg['pdf_folder'] = str(Path(pdf_folder).expanduser().resolve()) if pdf_folder else ''
            if cfg['pdf_folder']:
                Path(cfg['pdf_folder']).mkdir(parents=True, exist_ok=True)
            if not 1024<=cfg['port']<=65535: raise ValueError('Port muss zwischen 1024 und 65535 liegen')
            if cfg['display_rows'] not in (1,2,3): raise ValueError('Bitte 1, 2 oder 3 Zeilen wählen')
            if cfg['refresh_seconds']<30 or cfg['course_seconds']<1 or cfg['pdf_seconds']<2: raise ValueError('Ungültige Zeitangabe')
            if self.token.get().strip():
                keyring.set_password(SERVICE,ACCOUNT,self.token.get().strip())
                self.token.delete(0,'end')
            CONFIG.write_text(json.dumps(cfg,indent=2,ensure_ascii=False),encoding='utf-8')
            self.config=cfg
            self.status.set('Einstellungen gespeichert')
            return True
        except Exception as e:
            messagebox.showerror('Speichern fehlgeschlagen',str(e))
            return False

    def test(self):
        token=self.get_token()
        if not token:
            messagebox.showwarning('Token fehlt','Bitte zuerst den API-Token eingeben.')
            return
        self.status.set('Teste API-Verbindung …')
        def run():
            try:
                r=requests.get('https://beste.schule/api/time-tables/current',headers={'Authorization':'Bearer '+token,'Accept':'application/json'},timeout=25)
                r.raise_for_status()
                self.root.after(0,lambda: messagebox.showinfo('API-Test','Verbindung erfolgreich (HTTP 200).'))
                self.root.after(0,lambda:self.status.set('API-Verbindung erfolgreich'))
            except Exception as e:
                msg=str(e)
                self.root.after(0,lambda:messagebox.showerror('API-Test fehlgeschlagen',msg))
                self.root.after(0,lambda:self.status.set('API-Verbindung fehlgeschlagen'))
        threading.Thread(target=run,daemon=True).start()

    def start(self):
        if self.running or not self.save():return
        token=self.get_token()
        if not token:
            messagebox.showwarning('Token fehlt','Bitte API-Token eingeben und speichern.')
            return
        os.environ['BESTE_TOKEN']=token
        board_engine.SETTINGS.update({k:v for k,v in self.config.items() if k in board_engine.SETTINGS})
        board_engine.cache.update({'at':0,'data':None})
        host='0.0.0.0' if self.config['lan'] else '127.0.0.1'
        try:
            self.server=create_server(board_engine.app,host=host,port=self.config['port'],threads=4)
        except Exception as e:
            messagebox.showerror('Server konnte nicht starten',str(e));return
        self.running=True
        self.start_btn.configure(state='disabled');self.stop_btn.configure(state='normal')
        self.status.set('Server läuft')
        url=f"http://127.0.0.1:{self.config['port']}"
        self.address.set('Auf diesem PC: '+url+ (' | Im Schulnetz: http://<IP-des-Servers>:'+str(self.config['port']) if self.config['lan'] else ''))
        threading.Thread(target=self.serve,daemon=True).start()

    def serve(self):
        try: self.server.run()
        except Exception as e:
            msg=str(e)
            self.root.after(0,lambda: self.status.set('Serverfehler: '+msg))

    def stop(self):
        if not self.running:return
        try: self.server.close()
        except Exception:pass
        self.server=None;self.running=False
        self.start_btn.configure(state='normal');self.stop_btn.configure(state='disabled')
        self.status.set('Server gestoppt');self.address.set('')

    def open(self):
        if not self.running:
            messagebox.showinfo('Server gestoppt','Bitte zuerst den Server starten.');return
        webbrowser.open(f"http://127.0.0.1:{self.config['port']}")

    def check_updates(self):
        """Prüft Releases im Hintergrund, ohne Dateien zu verändern."""
        self.status.set('Suche nach Schul-Board-Updates …')
        def run():
            result, message, url = updater.check_for_update()
            def show():
                self.status.set(message)
                if result == 'available':
                    if messagebox.askyesno('Schul-Board – Update verfügbar',
                                           message + '\n\nRelease-Seite im Browser öffnen?'):
                        webbrowser.open(url)
                elif result == 'unavailable':
                    if messagebox.askyesno('Schul-Board – Updateprüfung',
                                           message + '\n\nGitHub im Browser öffnen?'):
                        webbrowser.open(url)
                else:
                    messagebox.showinfo('Schul-Board – Updateprüfung', message)
            self.root.after(0, show)
        threading.Thread(target=run, daemon=True).start()

    def close(self):
        if self.running:
            if not messagebox.askyesno('Beenden','Beim Beenden wird auch der Stundenplanserver gestoppt. Fortfahren?'):return
            self.stop()
        self.root.destroy()

if __name__=='__main__':
    if os.name == 'nt':
        import ctypes

        # Set system DPI awareness before Tk creates its first window.
        ctypes.windll.user32.SetProcessDPIAware()
    root=tk.Tk()
    try: ttk.Style().theme_use('vista')
    except tk.TclError: pass
    Window(root)
    root.mainloop()
