"""Lokale Windows-Verwaltung des Stundenplan-Boards."""
import json
import os
import socket
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

import keyring
import requests
from waitress import create_server
import board_engine
import updater

ROOT = Path(os.environ.get('APPDATA', str(Path.home()))) / 'StundenplanBoard'
CONFIG = ROOT / 'einstellungen.json'
SERVICE = 'StundenplanBoard-beste.schule'
ACCOUNT = 'api-token'
DEFAULT = {'port':5000,'lan':False,'refresh_seconds':300,'switch_seconds':15,
           'course_seconds':4,'cutoff_hour':15,'start_grade':5,'display_rows':2,'pdf_folder':str(Path.home() / 'StundenplanBoard_Infoboard'),'pdf_seconds':12,'group_mappings':{},'teacher_mappings':{},'room_mappings':{},'school_name':'Meine Schule','school_logo':'','automatic_group_mapping':True}

class Window:
    def __init__(self, root):
        self.root = root
        self.root.title('Schul-Board – Verwaltung')
        self.root.geometry('940x610')
        self.root.minsize(780,510)
        ROOT.mkdir(parents=True, exist_ok=True)
        try: self.config = {**DEFAULT, **json.loads(CONFIG.read_text(encoding='utf-8'))}
        except (FileNotFoundError, ValueError): self.config = dict(DEFAULT)
        self.values = {}
        self.server = None
        self.running = False

        shell = ttk.Frame(root, padding=12)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='StundenplanBoard – Verwaltung',
                  font=('Segoe UI', 17, 'bold')).pack(anchor='w', pady=(0,10))
        body = ttk.Frame(shell)
        body.pack(fill='both', expand=True)
        navigation = ttk.LabelFrame(body, text='Bereiche', padding=8)
        navigation.pack(side='left', fill='y', padx=(0,10))
        content = ttk.Frame(body)
        content.pack(side='left', fill='both', expand=True)
        self.pages = {}
        self.nav_buttons = {}
        for name in ('Allgemein', 'API & Server', 'Anzeige & PDFs',
                     'Lehrer', 'Räume', 'Klassen & Gruppen'):
            page = ttk.Frame(content, padding=12)
            self.pages[name] = page
            btn = ttk.Button(navigation, text=name, width=23,
                             command=lambda n=name: self.show_page(n))
            btn.pack(fill='x', pady=3)
            self.nav_buttons[name] = btn

        general = self.pages['Allgemein']
        school = ttk.LabelFrame(general, text='Schule', padding=12)
        school.pack(fill='x', pady=5)
        ttk.Label(school, text='Schulname im Kopfbereich').pack(anchor='w')
        self.school_name = tk.StringVar(value=self.config.get('school_name', ''))
        ttk.Entry(school, textvariable=self.school_name).pack(fill='x', pady=5)
        ttk.Label(school, text='Schullogo (PNG, leer = mitgeliefertes Logo)').pack(anchor='w')
        logo_row = ttk.Frame(school)
        logo_row.pack(fill='x', pady=5)
        self.school_logo = tk.StringVar(value=self.config.get('school_logo', ''))
        ttk.Entry(logo_row, textvariable=self.school_logo).pack(side='left', fill='x', expand=True)
        ttk.Button(logo_row, text='Auswählen …', command=self.choose_school_logo).pack(side='left', padx=(5,0))
        self.automatic_group_mapping = tk.BooleanVar(value=self.config.get('automatic_group_mapping', True))
        ttk.Checkbutton(general,
                        text='Automatische Gruppenzuordnung (Gruppenregeln)',
                        variable=self.automatic_group_mapping).pack(anchor='w', pady=12)
        ttk.Label(general, text='Für andere Schulen die Gruppenautomatik ausschalten.',
                  foreground='#666').pack(anchor='w')

        api = self.pages['API & Server']
        access = ttk.LabelFrame(api, text='beste.schule API', padding=12)
        access.pack(fill='x', pady=5)
        ttk.Label(access, text='Token (sicher im Windows-Anmeldespeicher)').pack(anchor='w')
        self.token = ttk.Entry(access, show='•')
        self.token.pack(fill='x', pady=7)
        ttk.Button(access, text='Token-Verbindung testen', command=self.test).pack(anchor='w')
        self.lan = tk.BooleanVar(value=self.config['lan'])
        ttk.Checkbutton(api, text='Im Schulnetz erreichbar (nicht nur dieser PC)',
                        variable=self.lan).pack(anchor='w', pady=12)

        settings = self.pages['Anzeige & PDFs']
        options = ttk.LabelFrame(settings, text='Anzeigeeinstellungen', padding=10)
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
            row = ttk.Frame(options)
            row.grid(row=i//2, column=i%2, sticky='ew', padx=7, pady=5)
            ttk.Label(row, text=label).pack(anchor='w')
            v = tk.StringVar(value=str(self.config[key]))
            self.values[key] = v
            ttk.Combobox(row, textvariable=v, values=choices,
                         state='readonly', width=12).pack(anchor='w', pady=(2,0))
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        pdf = ttk.LabelFrame(settings, text='Infoboard-PDFs', padding=10)
        pdf.pack(fill='x', pady=9)
        ttk.Label(pdf, text='Ordner für Info-PDFs').pack(anchor='w')
        self.pdf_folder = tk.StringVar(value=str(self.config['pdf_folder']))
        pdfrow = ttk.Frame(pdf)
        pdfrow.pack(fill='x', pady=5)
        ttk.Entry(pdfrow, textvariable=self.pdf_folder).pack(side='left', fill='x', expand=True)
        ttk.Button(pdfrow, text='Auswählen …', command=self.choose_pdf_folder).pack(side='left', padx=5)

        for name, kind, desc in [
            ('Lehrer','teachers','Lehrerbezeichnungen und Anzeigenamen verwalten'),
            ('Räume','rooms','Raumbezeichnungen und Anzeigenamen verwalten'),
            ('Klassen & Gruppen','groups','Hauptklassen und bis zu 16 Gruppen zuordnen')]:
            page = self.pages[name]
            ttk.Label(page, text=name, font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(0,8))
            ttk.Label(page, text=desc).pack(anchor='w', pady=(0,15))
            ttk.Button(page, text='Tabelle bearbeiten / Excel einfügen …',
                       command=lambda k=kind: self.open_mapping_editor(k)).pack(anchor='w')
            ttk.Label(page, text='Der Tabelleneditor öffnet sich in einem eigenen Fenster.',
                      foreground='#666').pack(anchor='w', pady=12)

        footer = ttk.Frame(shell)
        footer.pack(side='bottom', fill='x', pady=(10,0))
        ttk.Separator(shell, orient='horizontal').pack(side='bottom', fill='x')
        ttk.Button(footer, text='Speichern', command=self.save).pack(side='left', padx=(0,7))
        ttk.Button(footer, text='Im Browser öffnen', command=self.open).pack(side='left', padx=(0,7))
        self.start_btn = ttk.Button(footer, text='Board starten', command=self.start)
        self.start_btn.pack(side='left', padx=(0,7))
        self.stop_btn = ttk.Button(footer, text='Server stoppen', command=self.stop, state='disabled')
        self.stop_btn.pack(side='left', padx=(0,7))
        ttk.Button(footer, text='Beenden', command=self.close).pack(side='right')
        ttk.Button(footer, text='Auf Updates prüfen', command=self.check_updates).pack(side='right', padx=(0,7))
        statusbar = ttk.Frame(shell)
        statusbar.pack(side='bottom', fill='x', pady=(7,0))
        self.status = tk.StringVar(value='Server ist gestoppt')
        ttk.Label(statusbar, textvariable=self.status, font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        self.address = tk.StringVar(value='')
        ttk.Label(statusbar, textvariable=self.address).pack(anchor='w')
        self.show_page('Allgemein')
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def show_page(self, name):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill='both', expand=True)


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
        dialog.title('StundenplanBoard – ' + title)
        dialog.geometry('900x710')
        dialog.transient(self.root)
        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text=title, font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Excel: zwei Spalten markieren, Strg+C und hier Strg+V. Mehrere Zeilen werden gemeinsam eingefügt. '
                  'Bei Gruppen: eine Zeile je Zuordnung oder mehrere Klassen durch Komma trennen.',
                  wraplength=850).pack(anchor='w', pady=(5, 9))
        data = dict(self.config.get(key) or {})
        if kind == 'groups':
            data = {k: (v if isinstance(v, list) else [v]) for k,v in data.items()}
        columns = ('source', 'target')
        tree = ttk.Treeview(outer, columns=columns, show='headings', selectmode='extended')
        tree.heading('source', text=left_label)
        tree.heading('target', text=right_label)
        tree.column('source', width=350)
        tree.column('target', width=440)
        sb = ttk.Scrollbar(outer, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        def as_text(value):
            return ', '.join(value) if isinstance(value,list) else str(value)
        def redraw():
            tree.delete(*tree.get_children())
            for name in sorted(data, key=str.casefold):
                tree.insert('', 'end', iid=name, values=(name, as_text(data[name])))
        redraw()
        row = ttk.Frame(outer)
        row.pack(fill='x', pady=7)
        source = tk.StringVar()
        target = tk.StringVar()
        ttk.Label(row,text=left_label+':').pack(side='left')
        ttk.Entry(row,textvariable=source,width=23).pack(side='left',padx=4)
        ttk.Label(row,text=right_label+':').pack(side='left')
        ttk.Entry(row,textvariable=target,width=28).pack(side='left',padx=4,fill='x',expand=True)
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
        ttk.Button(row,text='Übernehmen',command=apply).pack(side='left')
        tools=ttk.Frame(outer);tools.pack(fill='x',pady=3)
        def delete():
            for name in tree.selection():data.pop(name,None)
            redraw()
        ttk.Button(tools,text='Ausgewählte entfernen',command=delete).pack(side='left',padx=(0,8))
        def copy_rows(_=None):
            ids=tree.selection() or tree.get_children()
            content='\n'.join(name+'\t'+as_text(data[name]) for name in ids)
            dialog.clipboard_clear();dialog.clipboard_append(content)
            return 'break'
        ttk.Button(tools,text='Auswahl nach Excel kopieren',command=copy_rows).pack(side='left',padx=(0,8))
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
        ttk.Button(tools,text='Aus Excel einfügen (Strg+V)',command=paste_rows).pack(side='left')
        tree.bind('<Control-v>',paste_rows)
        tree.bind('<Control-V>',paste_rows)
        tree.bind('<Control-c>',copy_rows)
        status=tk.StringVar(value='Noch nicht gespeicherte Änderungen werden erst durch „Speichern“ übernommen.')
        ttk.Label(outer,textvariable=status,wraplength=850).pack(anchor='w',pady=6)
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
        ttk.Button(tools,text='Bezeichnungen aus API übernehmen',command=fetch).pack(side='right')
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
        ttk.Button(outer,text='Zuordnungen speichern',command=save_mapping).pack(anchor='e',pady=5)

    def open_class_group_editor(self):
        """One main class per row, 16 group columns; Excel TSV and semicolons supported."""
        import re
        dialog = tk.Toplevel(self.root)
        dialog.title('StundenplanBoard – Hauptklassen und Gruppen')
        dialog.geometry('1250x730')
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Hauptklassen und Gruppen', font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Spalte A: Hauptklasse; Spalten B–Q: bis zu 16 Gruppen. Excel-Bereich kopieren und mit Strg+V einfügen. '
                  'Alternativ mehrere Gruppen mit Semikolon in einer Zelle trennen. Die Hauptklasse gilt automatisch als Gruppe.',
                  wraplength=1200).pack(anchor='w', pady=(4, 8))

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
        table_area.pack(fill='both', expand=True)
        tree = ttk.Treeview(table_area, columns=cols, show='headings', selectmode='extended')
        tree.heading('class', text='Hauptklasse')
        tree.column('class', width=115, minwidth=95, stretch=False)
        for i in range(1, 17):
            col = f'g{i}'
            tree.heading(col, text=f'Gruppe {i}')
            tree.column(col, width=115, minwidth=85, stretch=False)
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
        editor.pack(fill='x', pady=(9, 4))
        cls_var = tk.StringVar()
        groups_var = tk.StringVar()
        ttk.Label(editor, text='Hauptklasse:').pack(side='left')
        ttk.Entry(editor, textvariable=cls_var, width=10).pack(side='left', padx=(4, 12))
        ttk.Label(editor, text='Gruppen (Semikolon getrennt):').pack(side='left')
        ttk.Entry(editor, textvariable=groups_var).pack(side='left', fill='x', expand=True, padx=5)

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
        ttk.Button(editor, text='Zeile übernehmen', command=apply).pack(side='left', padx=4)

        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=5)

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

        ttk.Button(buttons, text='Aus Excel einfügen (Strg+V)', command=paste).pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Nach Excel kopieren (Strg+C)', command=copy).pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Ausgewählte Klassen entfernen', command=remove).pack(side='left')
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
        ttk.Button(buttons, text='Hauptklassen aus API übernehmen', command=fetch).pack(side='right')
        ttk.Label(frame, textvariable=status, wraplength=1200).pack(anchor='w', pady=5)

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
                self.status.set('Klassen- und Gruppenzuordnungen gespeichert')
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror('Speichern fehlgeschlagen', str(exc), parent=dialog)
        ttk.Button(frame, text='Zuordnungen speichern', command=save).pack(anchor='e', pady=5)

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
            cfg['school_name']=self.school_name.get().strip() or 'StundenplanBoard'
            cfg['school_logo']=self.school_logo.get().strip()
            if cfg['school_logo'] and (not Path(cfg['school_logo']).is_file() or Path(cfg['school_logo']).suffix.lower() != '.png'):
                raise ValueError('Bitte eine vorhandene PNG-Datei als Schullogo auswählen.')
            cfg['automatic_group_mapping']=self.automatic_group_mapping.get()
            for mapping_key in ('group_mappings','teacher_mappings','room_mappings'):
                cfg[mapping_key]=self.config.get(mapping_key,{})
            cfg['pdf_folder']=str(Path(self.pdf_folder.get()).expanduser().resolve())
            if not cfg['pdf_folder']:raise ValueError('PDF-Ordner fehlt')
            Path(cfg['pdf_folder']).mkdir(parents=True,exist_ok=True)
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
        """Prüft Releases asynchron; kein Download, keine Installation."""
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
    root=tk.Tk()
    try: ttk.Style().theme_use('vista')
    except tk.TclError: pass
    Window(root)
    root.mainloop()
