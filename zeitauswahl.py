"""Maus- und tastaturbedienbare Uhrzeitauswahl."""
import math
import tkinter as tk
from tkinter import ttk

from verwaltungsstil import BACKGROUND, BLUE, TEXT


def choose_time(parent, title, value):
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.resizable(False, False)
    panel = ttk.Frame(dialog, padding=12)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text=title, style='CardTitle.TLabel').pack(anchor='w')
    hour, minute = map(int, (value.get() or '07:30').split(':'))
    parts = [tk.StringVar(value=f'{part:02d}') for part in (hour, minute)]
    mode = 0
    controls = ttk.Frame(panel)
    controls.pack(pady=6)
    canvas = tk.Canvas(panel, width=284, height=284, bg=BACKGROUND, highlightthickness=0)
    canvas.pack()
    center = 142

    def number(part, maximum):
        text = part.get()
        return int(text) if text.isascii() and text.isdigit() and len(text) <= 2 and int(text) <= maximum else 0

    def point(index, count, radius):
        angle = index * math.tau / count
        return center + radius * math.sin(angle), center - radius * math.cos(angle)

    def draw(*_):
        canvas.delete('all')
        canvas.create_oval(4, 4, 280, 280, fill='#e0e8f5', outline='')
        selected = number(parts[mode], (23, 59)[mode])
        count = (12, 60)[mode]
        radius = 116 if mode or 1 <= selected <= 12 else 77
        x, y = point(selected, count, radius)
        canvas.create_line(center, center, x, y, fill=BLUE, width=3)
        canvas.create_oval(x-15, y-15, x+15, y+15, fill=BLUE, outline='')
        numbers = range(0, 60, 5) if mode else range(24)
        for n in numbers:
            r = 116 if mode or 1 <= n <= 12 else 77
            x, y = point(n, count, r)
            canvas.create_text(x, y, text=f'{n:02d}' if mode or n == 0 else str(n),
                               font='TkDefaultFont', fill='white' if n == selected else TEXT)

    def set_mode(index):
        nonlocal mode
        mode = index
        draw()

    def pick(event):
        dx, dy = event.x-center, event.y-center
        distance = math.hypot(dx, dy)
        if not 53 <= distance <= 140:
            return
        fraction = math.atan2(dx, -dy) / math.tau
        if mode == 0:
            mark = round(fraction * 12) % 12
            selected = (mark or 12) if distance >= 96 else (mark + 12) % 24
            parts[0].set(f'{selected:02d}')
            set_mode(1)
        else:
            parts[1].set(f'{round(fraction * 60) % 60:02d}')

    for index, label, limit in [(0, 'Stunde', 23), (1, 'Minute', 59)]:
        ttk.Button(controls, text=label, command=lambda i=index: set_mode(i)).grid(row=0, column=index, padx=4)
        spin = ttk.Spinbox(controls, from_=0, to=limit, format='%02.0f',
                           textvariable=parts[index], width=4, wrap=True)
        spin.grid(row=1, column=index, pady=4)
        spin.bind('<FocusIn>', lambda event, i=index: set_mode(i))
        parts[index].trace_add('write', draw)
    canvas.bind('<Button-1>', pick)

    def accept():
        if any(not part.get().isascii() or not part.get().isdigit() or len(part.get()) > 2
               or int(part.get()) > limit for part, limit in zip(parts, (23, 59))):
            dialog.bell()
            return
        value.set(':'.join(f'{int(part.get()):02d}' for part in parts))
        dialog.destroy()

    def clear():
        value.set('')
        dialog.destroy()

    actions = ttk.Frame(panel)
    actions.pack(fill='x', pady=(10, 0))
    ttk.Button(actions, text='Leeren', command=clear).pack(side='left')
    ttk.Button(actions, text='Übernehmen', style='Accent.TButton', command=accept).pack(side='right')
    ttk.Button(actions, text='Abbrechen', command=dialog.destroy).pack(side='right', padx=5)
    dialog.bind('<Escape>', lambda event: dialog.destroy())
    dialog.bind('<Return>', lambda event: accept())
    draw()
    dialog.wait_visibility()
    dialog.grab_set()
    dialog.focus_set()
