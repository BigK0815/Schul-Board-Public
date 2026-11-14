"""Lokale Windows-Verwaltung des Stundenplan-Boards."""
import json
import os
import re
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, messagebox, filedialog, font

import keyring
import requests
from waitress import create_server
import board_engine
import updater
from verwaltungsstil import SettingsViewport, apply_style, card, toggle, flow_buttons

ROOT = Path(os.environ.get('APPDATA', str(Path.home()))) / 'StundenplanBoard'
CONFIG = ROOT / 'einstellungen.json'
SERVICE = 'StundenplanBoard-beste.schule'
ACCOUNT = 'api-token'
DEFAULT = {'port':5000,'lan':False,'switch_seconds':15,
           'course_seconds':4,'cutoff_hour':15,'start_grade':5,'display_rows':2,'pdf_folder':'','pdf_seconds':12,'group_mappings':{},'group_name_display':None,'group_custom_names':{},'hidden_groups':[],'hidden_grades':[],'show_unassigned':True,'school_name':'Musterschule','school_logo':'','automatic_group_mapping':False}

def natural_name_key(name):
    normalized = name.casefold().translate(str.maketrans('äöü', 'aou'))
    return [int(part) if part.isascii() and part.isdigit() else part
            for part in re.split(r'([0-9]+)', normalized)]


def visible_row_indices(top, height, row_height, count):
    first = max(0, top // row_height - 2)
    end = min(count, (top + height + row_height - 1) // row_height + 2)
    return range(first, end)


def visibility_icons(parent, size):
    """Transparent checkbox images shared by every visible table row."""
    images = []
    for selected in (False, True):
        icon = tk.PhotoImage(master=parent, width=size, height=size)
        outline = '#0866cb' if selected else '#657d98'
        icon.put(outline, to=(2, 0, size - 2, size))
        icon.put(outline, to=(0, 2, size, size - 2))
        if selected:
            # Draw the two strokes in the same proportions at each DPI.
            for x in range(size * 23 // 100, size * 78 // 100):
                y = size * 49 // 100 + min(x - size * 23 // 100,
                                           size * 57 // 100 - x)
                icon.put('#ffffff', to=(x, y, x + 1, y + max(2, size // 9)))
        else:
            icon.put('#ffffff', to=(2, 2, size - 2, size - 2))
        images.append(icon)
    return images


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
        for name in ('Allgemein', 'API & Server', 'Anzeige & PDFs', 'Klassen & Gruppen'):
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
        school = card(general, 'Schule')
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

        groups_page = self.pages['Klassen & Gruppen']
        group_refresh = card(groups_page, 'Gruppenzuordnung')
        self.group_refresh_button = ttk.Button(
            group_refresh, text='Jetzt aktualisieren', command=self.update_groups)
        self.group_refresh_button.pack(side='right', padx=(8, 0))
        ttk.Label(group_refresh, text='Automatische Aktualisierung einmal pro Woche',
                  style='Card.TLabel').pack(anchor='w')
        self.group_status = tk.StringVar(value='Noch nicht aktualisiert')
        ttk.Label(group_refresh, textvariable=self.group_status,
                  style='CardMuted.TLabel').pack(anchor='w', pady=(4, 0))

        self.group_visibility = {}
        self.group_custom_names = {}
        filters = card(groups_page, 'Jahrgänge anzeigen')
        self.grade_filters = {}
        self.grade_buttons = ttk.Frame(filters, style='Card.TFrame')
        self.grade_buttons.pack(fill='x')
        self.show_unassigned = tk.BooleanVar(value=self.config['show_unassigned'])
        ttk.Checkbutton(filters, text='Gruppen ohne Zuordnung anzeigen',
                        variable=self.show_unassigned, command=self.refresh_group_name_options,
                        style='GroupName.TCheckbutton').pack(anchor='w', pady=(6, 0))
        self.class_grades = {}

        table = card(groups_page, 'Anzeige im Plan')
        table.columnconfigure(0, weight=1)
        grid = ttk.Frame(table)
        grid.pack(fill='x')
        grid.columnconfigure(0, weight=1)
        line = '#b8cce3'
        self.group_header_canvas = tk.Canvas(grid, height=1, highlightthickness=0, background=line)
        self.group_canvas = tk.Canvas(grid, height=250, highlightthickness=0, background=line)
        self.group_header_canvas.grid(row=0, column=0, sticky='ew')
        self.group_canvas.grid(row=1, column=0, sticky='ew')
        self.group_header = tk.Frame(self.group_header_canvas, background=line)
        self.group_rows = []
        self.group_row_widgets = {}
        self.group_render_pending = False
        self.group_table_width = 0
        line_height = font.nametofont('TkDefaultFont').metrics('linespace')
        checkbox_size = max(22, line_height + 4)
        self.group_row_height = max(line_height + 18, checkbox_size + 10)
        self.group_visibility_icons = visibility_icons(self.group_canvas, checkbox_size)
        self.group_header_window = self.group_header_canvas.create_window(
            0, 0, anchor='nw', window=self.group_header)
        scroll = ttk.Scrollbar(grid, orient='vertical', command=self.group_canvas.yview)
        scroll.grid(row=1, column=1, sticky='ns')

        def scroll_rows(first, last):
            scroll.set(first, last)
            self.schedule_group_rows()

        self.group_canvas.configure(yscrollcommand=scroll_rows,
                                    yscrollincrement=self.group_row_height)

        def scroll_columns(*args):
            self.group_canvas.xview(*args)
            self.group_header_canvas.xview(*args)

        horizontal = ttk.Scrollbar(grid, orient='horizontal', command=scroll_columns)
        self.group_canvas.configure(xscrollcommand=horizontal.set)
        horizontal.grid(row=2, column=0, sticky='ew')
        titles = ('Anzeigen', 'Klasse / Gruppe', 'Hauptklassen', 'Eigener Anzeigename')
        heading_font = font.nametofont('TkDefaultFont').copy()
        heading_font.configure(weight='bold')
        self.group_column_widths = [heading_font.measure(title) + 20 for title in titles]
        for column, title in enumerate(titles):
            tk.Label(self.group_header, text=title, font=heading_font, background='#dceafa',
                     anchor='w', padx=9, pady=7).grid(row=0, column=column, sticky='nsew',
                                                      padx=(0, 1), pady=(0, 1))
        for column in (1, 2):
            self.group_column_widths[column] = max(self.group_column_widths[column], 146)
        self.group_canvas.bind('<Configure>', self.resize_group_table)
        self.group_canvas.bind('<Map>', lambda event: self.resize_group_table())
        self.group_header.bind('<Configure>', self.resize_group_table)
        self.group_canvas.bind('<MouseWheel>', self.scroll_group_rows)
        self.root.bind('<Configure>', self.resize_group_table, add='+')
        self.group_timestamp = None
        self.group_mapping = None
        self.group_token = ''
        self.group_refresh_pending = False
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
        self.poll_group_status()

    def show_page(self, name):
        self.viewport.show(self.pages[name])
        for label, button in self.nav_buttons.items():
            button.configure(style='SelectedNav.TButton' if label == name else 'Nav.TButton')
            self.nav_markers[label].configure(
                style='Selection.TFrame' if label == name else 'Navigation.TFrame')


    def poll_group_status(self):
        if not self.group_refresh_pending:
            try:
                token = self.get_token()
                if token == self.group_token and board_engine.school_data is not None:
                    source = board_engine.school_data
                    if source.token == token:
                        updated, mapping = source.read('gruppen-cache')
                        self.show_group_snapshot(updated, mapping, source.read('jahrgaenge-cache')[1])
                        if source.group_error:
                            self.group_status.set('Letzter Abruf fehlgeschlagen: ' + source.group_error)
                elif token != self.group_token:
                    self.group_token = token
                    source = board_engine.SchoolData(token) if token else None
                    try:
                        self.show_group_snapshot(
                            *(source.read('gruppen-cache') if source else (None, None)),
                            source.read('jahrgaenge-cache')[1] if source else None)
                    finally:
                        if source:
                            source.session.close()
            except keyring.errors.KeyringError:
                pass
        self.root.after(5000, self.poll_group_status)

    def show_group_snapshot(self, updated, mapping, grades=None):
        if updated is None:
            self.group_status.set('Noch nicht aktualisiert')
        else:
            self.group_status.set(updated.strftime('Zuletzt aktualisiert: %d.%m.%Y, %H:%M'))
        grades = grades or {}
        if (updated, mapping, grades) != (self.group_timestamp, self.group_mapping, self.class_grades):
            self.class_grades = grades
            self.group_timestamp, self.group_mapping = updated, mapping
            self.refresh_group_name_options()

    def update_groups(self):
        token = self.get_token()
        if not token:
            messagebox.showwarning('Token fehlt', 'Bitte zuerst den API-Token eingeben.')
            return
        if self.running and token != os.environ.get('BESTE_TOKEN'):
            messagebox.showwarning('API-Token geändert', 'Bitte den Server mit dem neuen Token neu starten.')
            return
        self.group_token = token
        self.group_refresh_pending = True
        self.group_status.set('Gruppenzuordnung wird aktualisiert …')
        self.group_refresh_button.configure(state='disabled')

        def finished(updated=None, mapping=None, error=None):
            self.group_refresh_pending = False
            self.group_refresh_button.configure(state='normal')
            if error:
                self.group_status.set('Aktualisierung fehlgeschlagen')
                messagebox.showerror('Gruppenzuordnung', error)
            else:
                self.show_group_snapshot(updated, mapping, board_engine.school_data.read(
                    'jahrgaenge-cache')[1])

        def run():
            try:
                updated, mapping = board_engine.update_groups(token)
            except Exception as error:
                self.root.after(0, finished, None, None, str(error))
            else:
                self.root.after(0, finished, updated, mapping)

        threading.Thread(target=run, daemon=True).start()

    def resize_group_table(self, event=None):
        if event and event.widget not in (self.root, self.group_canvas, self.group_header):
            return
        minimum = sum(self.group_column_widths)
        width = max(minimum, self.group_canvas.winfo_width())
        widths = self.group_column_widths.copy()
        extra = width - minimum
        widths[2] += extra // 2
        widths[3] += extra - extra // 2
        for column, size in enumerate(widths):
            self.group_header.columnconfigure(column, minsize=size)
        self.group_widths = widths
        self.group_table_width = width
        header_height = self.group_header.winfo_reqheight()
        self.group_header_canvas.configure(height=header_height,
                                           scrollregion=(0, 0, width, header_height))
        self.group_header_canvas.itemconfigure(self.group_header_window, width=width)
        self.group_canvas.configure(
            height=max(110, self.root.winfo_height() - self.group_canvas.winfo_rooty()
                       + self.root.winfo_rooty() - 125),
            scrollregion=(0, 0, width, max(1, len(self.group_rows)) * self.group_row_height))
        self.group_header_canvas.xview_moveto(self.group_canvas.xview()[0])
        self.schedule_group_rows()

    def schedule_group_rows(self):
        if not self.group_render_pending:
            self.group_render_pending = True
            self.group_canvas.after_idle(self.render_group_rows)

    def scroll_group_rows(self, event):
        self.group_canvas.yview_scroll(-int(event.delta / 120), 'units')
        return 'break'

    def refresh_group_name_options(self):
        mapping = self.group_mapping
        if mapping is None:
            mapping = self.config.get('group_mappings') or {}
        classes = set()
        groups = {}
        for group, targets in mapping.items():
            if isinstance(targets, str):
                targets = [target.strip() for target in re.split('[,;]', targets) if target.strip()]
            classes.update(targets)
            if targets != [group]:
                groups[group] = targets
        grades = {name: board_engine.class_grade(name, self.class_grades) for name in classes}
        available_grades = sorted(set(range(5, 13)) | {grade for grade in grades.values()
                                                      if grade is not None})
        if available_grades != list(self.grade_filters):
            for button in self.grade_buttons.winfo_children():
                button.destroy()
            self.grade_filters = {
                grade: self.grade_filters.get(grade) or tk.BooleanVar(
                    value=grade not in self.config['hidden_grades']) for grade in available_grades
            }
            for index, (grade, checked) in enumerate(self.grade_filters.items()):
                button = ttk.Checkbutton(
                    self.grade_buttons, text=str(grade), variable=checked,
                    command=self.refresh_group_name_options, style='GroupName.TCheckbutton')
                button.grid(row=index // 8, column=index % 8, sticky='w', padx=(0, 9))
                self.viewport.bind_controls(button)
        visible_classes = {name for name, grade in grades.items()
                           if grade is None or self.grade_filters[grade].get()}
        rows = [(name, None) for name in sorted(visible_classes, key=natural_name_key)]
        for name in sorted(groups.keys() - classes, key=natural_name_key):
            targets = sorted(set(groups[name]) & visible_classes, key=natural_name_key)
            if targets or (not groups[name] and self.show_unassigned.get()):
                rows.append((name, targets))

        for row in tuple(self.group_row_widgets):
            self.remove_group_row(row)
        self.group_rows = rows
        self.group_canvas.delete('empty')
        self.group_canvas.yview_moveto(0)
        self.resize_group_table()

    def remove_group_row(self, row):
        item, frame = self.group_row_widgets.pop(row)
        self.group_canvas.delete(item)
        frame.destroy()

    def render_group_rows(self):
        self.group_render_pending = False
        canvas = self.group_canvas
        if not canvas.winfo_ismapped() or not self.group_table_width:
            return
        if not self.group_rows:
            canvas.delete('empty')
            canvas.create_text(9, 6, anchor='nw', tags='empty',
                               text='Keine Klassen oder Gruppen für diese Auswahl.')
            return
        wanted = set(visible_row_indices(int(canvas.canvasy(0)), canvas.winfo_height(),
                                         self.group_row_height, len(self.group_rows)))
        focus = self.root.focus_get()
        for row, (_, frame) in tuple(self.group_row_widgets.items()):
            if row not in wanted and (focus is None or not str(focus).startswith(str(frame) + '.')):
                self.remove_group_row(row)
        for row in sorted(wanted | self.group_row_widgets.keys()):
            if row not in self.group_row_widgets:
                self.create_group_row(row)
            item, frame = self.group_row_widgets[row]
            canvas.itemconfigure(item, width=self.group_table_width)
            for column, width in enumerate(self.group_widths):
                frame.columnconfigure(column, minsize=width)

    def create_group_row(self, row):
        name, targets = self.group_rows[row]
        canvas = self.group_canvas
        frame = tk.Frame(canvas, background='#b8cce3')
        frame.grid_propagate(False)
        frame.rowconfigure(0, weight=1)
        item = canvas.create_window(0, row * self.group_row_height, anchor='nw', window=frame,
                                    height=self.group_row_height)
        self.group_row_widgets[row] = (item, frame)
        if name not in self.group_visibility:
            self.group_visibility[name] = tk.BooleanVar(value=name not in self.config['hidden_groups'])
        color = '#ffffff' if row % 2 == 0 else '#edf4fc'
        cells = [tk.Frame(frame, background=color) for _ in self.group_column_widths]
        for column, cell in enumerate(cells):
            cell.pack_propagate(False)
            cell.grid(row=0, column=column, sticky='nsew', padx=(0, 1), pady=(0, 1))

        unchecked, checked = self.group_visibility_icons
        tk.Checkbutton(
            cells[0], variable=self.group_visibility[name], image=unchecked, selectimage=checked,
            indicatoron=False, background=color, activebackground=color, selectcolor=color,
            relief='flat', overrelief='flat', offrelief='flat', borderwidth=0, padx=0, pady=0,
            highlightthickness=1, highlightbackground=color, highlightcolor='#0866cb',
            takefocus=True, cursor='hand2',
        ).pack(fill='both', expand=True)
        tk.Label(cells[1], text=name, background=color, anchor='w').pack(fill='x', expand=True, padx=8)
        text = '–' if targets is None else ', '.join(targets) or 'Ohne Zuordnung'
        tk.Label(cells[2], text=text, background=color, anchor='w').pack(fill='x', expand=True, padx=8)
        if targets is None:
            tk.Label(cells[3], text='–', background=color).pack(expand=True)
        else:
            if name not in self.group_custom_names:
                self.group_custom_names[name] = tk.StringVar(
                    value=board_engine.group_display_name(name, self.config))
            ttk.Entry(cells[3], textvariable=self.group_custom_names[name], width=10).pack(
                fill='x', expand=True, padx=6)
        for cell in cells:
            cell.bind('<MouseWheel>', self.scroll_group_rows)
            for widget in cell.winfo_children():
                widget.bind('<MouseWheel>', self.scroll_group_rows)
                widget.bind('<FocusOut>', lambda event: self.schedule_group_rows())

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
            cfg['automatic_group_mapping']=self.config['automatic_group_mapping']
            for mapping_key in ('group_mappings', 'teacher_mappings', 'room_mappings'):
                if mapping_key in self.config:
                    cfg[mapping_key] = self.config[mapping_key]
            cfg['group_name_display'] = self.config['group_name_display']
            hidden = set(self.config['hidden_groups'])
            hidden.difference_update(self.group_visibility)
            hidden.update(name for name, checked in self.group_visibility.items() if not checked.get())
            cfg['hidden_groups'] = sorted(hidden)
            excluded = set(self.config['hidden_grades']) - self.grade_filters.keys()
            excluded.update(grade for grade, checked in self.grade_filters.items() if not checked.get())
            cfg['hidden_grades'] = sorted(excluded)
            cfg['show_unassigned'] = self.show_unassigned.get()
            custom_names = dict(self.config['group_custom_names'])
            for name, variable in self.group_custom_names.items():
                custom_name = variable.get().strip()
                if custom_name or cfg['group_name_display'] is not None:
                    custom_names[name] = custom_name
                else:
                    custom_names.pop(name, None)
            cfg['group_custom_names'] = custom_names
            pdf_folder = self.pdf_folder.get().strip()
            cfg['pdf_folder'] = str(Path(pdf_folder).expanduser().resolve()) if pdf_folder else ''
            if cfg['pdf_folder']:
                Path(cfg['pdf_folder']).mkdir(parents=True, exist_ok=True)
            if not 1024<=cfg['port']<=65535: raise ValueError('Port muss zwischen 1024 und 65535 liegen')
            if cfg['display_rows'] not in (1,2,3): raise ValueError('Bitte 1, 2 oder 3 Zeilen wählen')
            if cfg['course_seconds']<1 or cfg['pdf_seconds']<2: raise ValueError('Ungültige Zeitangabe')
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
        with board_engine.lock:
            board_engine.SETTINGS.update({k:v for k,v in self.config.items() if k in board_engine.SETTINGS})
            board_engine.cache.update(key=None, data=None)
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
        self.refresh_stop = threading.Event()
        threading.Thread(target=self.refresh_board, args=(self.refresh_stop,), daemon=True).start()

    @staticmethod
    def refresh_board(stop):
        while not stop.is_set():
            try:
                board_engine.refresh_board()
            except Exception:
                # The board's API reports failures to connected displays.
                pass
            stop.wait(5)

    def serve(self):
        try: self.server.run()
        except Exception as e:
            msg=str(e)
            self.root.after(0,lambda: self.status.set('Serverfehler: '+msg))

    def stop(self):
        if not self.running:return
        self.refresh_stop.set()
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
