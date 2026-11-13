"""Helles Fluent-Design für die lokale Tk-Verwaltung."""

import os
import tkinter as tk
from tkinter import font, ttk

BACKGROUND = '#eef2fa'
NAVIGATION = '#e8edf7'
CARD = '#fdfdff'
TEXT = '#182131'
MUTED = '#505d70'
BLUE = '#0067bd'


def apply_style(root):
    style = ttk.Style(root)
    style.theme_use('clam')
    family = 'Segoe UI' if os.name == 'nt' else 'DejaVu Sans'
    for name in ('TkDefaultFont', 'TkTextFont'):
        font.nametofont(name, root=root).configure(family=family, size=10)
    root.configure(background=BACKGROUND)
    style.configure('.', background=BACKGROUND, foreground=TEXT, font='TkDefaultFont')
    style.configure('Page.TLabel', font=(family, 24, 'bold'))
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('Card.TLabel', background=CARD)
    style.configure('CardTitle.TLabel', background=CARD, font=(family, 12, 'bold'))
    style.configure('CardMuted.TLabel', background=CARD, foreground=MUTED)
    style.configure('Card.TFrame', background=CARD)
    style.configure('GroupName.TCheckbutton', background=CARD, padding=(2, 3))
    style.configure('Navigation.TFrame', background=NAVIGATION)
    style.configure('Selection.TFrame', background=BLUE)
    style.configure('TSeparator', background='#d7deeb')
    style.configure('TButton', padding=(11, 7), background=CARD, bordercolor='#c9d2df',
                    lightcolor=CARD, darkcolor=CARD, focuscolor=BLUE, focusthickness=2)
    style.map('TButton', background=[('disabled', '#e7ebf1'), ('pressed', '#dce8f5'),
                                     ('active', '#e9f1fb')],
              foreground=[('disabled', '#647185')])
    style.configure('Accent.TButton', background=BLUE, foreground='#ffffff',
                    bordercolor=BLUE, lightcolor=BLUE, darkcolor=BLUE,
                    focuscolor='#ffffff')
    style.map('Accent.TButton', background=[('pressed', '#004777'), ('active', '#00599e')])
    for name, color in [('Nav', NAVIGATION), ('SelectedNav', '#d7e5f7')]:
        button_style = f'{name}.TButton'
        style.configure(button_style, anchor='w', padding=(12, 10), background=color,
                        bordercolor=color, lightcolor=color, darkcolor=color)
        style.map(button_style, background=[('active', '#dce7f5')])
    for control in ('TEntry', 'TCombobox'):
        style.configure(control, padding=(8, 5), fieldbackground=CARD,
                        bordercolor='#bbc7d7', lightcolor=CARD, darkcolor=CARD)
        style.map(control, fieldbackground=[('readonly', CARD)],
                  bordercolor=[('focus', BLUE)])
    style.configure('Compact.TCombobox', padding=(6, 2))
    style.configure('Treeview', background=CARD, fieldbackground=CARD, font='TkDefaultFont',
                    rowheight=max(26, font.nametofont('TkDefaultFont', root=root).metrics('linespace') + 8),
                    bordercolor='#ccd5e2')
    style.configure('Treeview.Heading', background='#e4ebf6', padding=(8, 6))
    style.map('Treeview', background=[('selected', '#d7e5f7')],
              foreground=[('selected', TEXT)])
    return style


def _rounded(canvas, x, y, width, height, radius, **options):
    right, bottom = x + width, y + height
    return canvas.create_polygon(
        x, y + radius, x, y, x + radius, y, right - radius, y,
        right, y, right, y + radius, right, bottom - radius,
        right, bottom, right - radius, bottom, x + radius, bottom,
        x, bottom, x, bottom - radius, smooth=True, splinesteps=24, **options)


def card(parent, title):
    shell = ttk.Frame(parent)
    shell.pack(fill='x', pady=(0, 12))
    shell.columnconfigure(0, weight=1)
    canvas = tk.Canvas(shell, background=BACKGROUND, highlightthickness=0, borderwidth=0)
    canvas.place(relwidth=1, relheight=1)

    def draw(event):
        canvas.delete('all')
        for offset, shade in [(5, '#e7ecf6'), (3, '#e1e7f2')]:
            _rounded(canvas, 1, offset, event.width - 2, event.height - 7, 13, fill=shade, outline='')
        _rounded(canvas, 1, 1, event.width - 2, event.height - 7, 13,
                 fill=CARD, outline='#dce3ee')

    canvas.bind('<Configure>', draw)
    content = ttk.Frame(shell, style='Card.TFrame')
    content.grid(row=0, column=0, sticky='ew', padx=18, pady=(13, 19))
    ttk.Label(content, text=title, style='CardTitle.TLabel').pack(anchor='w', pady=(0, 8))
    return content


def toggle(parent, text, variable):
    """Keep keyboard focus and native checkbutton state with a Fluent switch icon."""
    images = []
    for enabled in (False, True):
        image = tk.PhotoImage(master=parent, width=36, height=20)
        track = BLUE if enabled else '#778398'
        knob = '#ffffff'
        center = 26 if enabled else 10
        for y in range(20):
            for x in range(36):
                if (x - min(26, max(9, x))) ** 2 + (y - 9.5) ** 2 <= 81:
                    color = knob if (x - center) ** 2 + (y - 9.5) ** 2 <= 36 else track
                    image.put(color, (x, y))
        images.append(image)
    style = ttk.Style(parent)
    # Image layout replaces only the checkbox indicator, leaving the focus ring.
    if 'FluentSwitch.indicator' not in style.element_names():
        style.element_create('FluentSwitch.indicator', 'image', images[0],
                             ('selected', images[1]), sticky='w', padding=(0, 0, 8, 0))
        style.layout('FluentSwitch.TCheckbutton', [
            ('Checkbutton.padding', {'sticky': 'nswe', 'children': [
                ('FluentSwitch.indicator', {'side': 'left', 'sticky': 'w'}),
                ('Checkbutton.focus', {'side': 'left', 'children': [
                    ('Checkbutton.label', {'sticky': 'nswe'})]})]})])
        style.configure('FluentSwitch.TCheckbutton', background=CARD,
                        padding=(4, 3), focuscolor=BLUE)
        parent.winfo_toplevel()._switch_images = images
    return ttk.Checkbutton(parent, text=text, variable=variable,
                           style='FluentSwitch.TCheckbutton')


class SettingsViewport(ttk.Frame):
    """Keep settings at their natural height inside a resizable viewport."""

    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background=BACKGROUND, highlightthickness=0,
                                borderwidth=0, yscrollincrement=16)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window(0, 0, anchor='nw', window=self.content)
        self.canvas.bind('<Configure>', self.refresh)
        self.content.bind('<Configure>', self.refresh)
        self.canvas.bind('<MouseWheel>', self._wheel)

    def refresh(self, _event=None):
        width = self.canvas.winfo_width()
        height = self.content.winfo_reqheight()
        self.canvas.itemconfigure(self.window, width=width)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        if height > self.canvas.winfo_height():
            self.scrollbar.grid(row=0, column=1, sticky='ns')
        else:
            self.scrollbar.grid_remove()
            self.canvas.yview_moveto(0)

    def show(self, page):
        for child in self.content.pack_slaves():
            child.pack_forget()
        page.pack(fill='x')
        self.canvas.yview_moveto(0)
        self.after_idle(self.refresh)

    def bind_controls(self, parent):
        """Handle wheel and keyboard focus only inside the settings pane."""
        parent.bind('<MouseWheel>', self._wheel, add='+')
        parent.bind('<FocusIn>', self._reveal_focus, add='+')
        for child in parent.winfo_children():
            self.bind_controls(child)

    def _wheel(self, event):
        if self.scrollbar.winfo_ismapped() and event.delta:
            steps = max(1, abs(event.delta) // 120)
            self.canvas.yview_scroll(-steps * 3 if event.delta > 0 else steps * 3, 'units')
            return 'break'

    def _reveal_focus(self, event):
        if not self.scrollbar.winfo_ismapped():
            return
        top = event.widget.winfo_rooty() - self.content.winfo_rooty()
        bottom = top + event.widget.winfo_height()
        height = self.canvas.winfo_height()
        visible_top = self.canvas.canvasy(0)
        if top < visible_top:
            self.canvas.yview_moveto((top - 16) / self.content.winfo_reqheight())
        elif bottom > visible_top + height:
            self.canvas.yview_moveto((bottom - height + 16) / self.content.winfo_reqheight())

def flow_buttons(frame):
    """Wrap a toolbar according to the measured button widths."""
    def arrange(event=None):
        width = frame.winfo_width()
        x = y = row_height = 0
        for button in frame.winfo_children():
            button_width = button.winfo_reqwidth()
            button_height = button.winfo_reqheight()
            if x and x + button_width > width:
                y += row_height + 4
                x = row_height = 0
            button.place(x=x, y=y, width=min(width, button_width))
            x += button_width + 6
            row_height = max(row_height, button_height)
        frame.configure(height=y + row_height + 4)

    frame.bind('<Configure>', arrange)
    frame.after_idle(arrange)


def wrapping_label(parent, **options):
    label = ttk.Label(parent, **options)
    parent.bind('<Configure>', lambda event: label.configure(
        wraplength=max(100, event.width - 24)), add='+')
    return label
