import tkinter as tk
from tkinter import ttk
from tkhtmlview import HTMLScrolledText
from tkcalendar import DateEntry
import json
import markdown
import requests
import threading

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - pystray may fail without GUI
    pystray = None
    Image = ImageDraw = None

HUB_BASE = 'http://127.0.0.1:8765'


def md_to_html(md: str) -> str:
    """Convert Markdown to HTML using the ``markdown`` package."""
    return markdown.markdown(md or '', extensions=['fenced_code'])


SETTINGS_FILE = "app_settings.json"


class RHIFApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.withdraw()  # hide main window

        master.option_add("*Font", "Segoe UI 11")

        self.panel = None
        self.tray_icon = None
        self.settings = {}
        self._load_settings()
        self.search_history = self.settings.get("history", [])
        self.limit_var = tk.IntVar(value=self.settings.get("search_limit", 20))
        self.always_on_top_var = tk.BooleanVar(value=self.settings.get("always_on_top", True))
        self.domain_suggestions = set()
        self.topic_suggestions = set()
        self.domain_cb = None
        self.topic_cb = None

        self.master.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.filters_win = None
        self.create_tray_icon()

    def _load_settings(self):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                self.settings = json.load(f)
        except Exception:
            self.settings = {}

    def _save_settings(self):
        if self.panel and self.panel.winfo_exists():
            self.settings["geometry"] = self.panel.geometry()
        self.settings["search_limit"] = self.limit_var.get()
        self.settings["always_on_top"] = self.always_on_top_var.get()
        self.settings["history"] = self.search_history
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f)
        except Exception:
            pass

    def toggle_panel(self, icon=None, item=None):
        if self.panel and self.panel.winfo_viewable():
            self.panel.withdraw()
        else:
            if not self.panel:
                self.build_panel()
            if self.panel:
                self.panel.deiconify()
                self.panel.lift()

    def create_tray_image(self):
        if Image is None:
            return None
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((0, 0, 64, 64), fill=(43, 108, 176, 255))
        w, h = draw.textsize("R")
        draw.text(((64 - w) / 2, (64 - h) / 2), "R", fill="white")
        return img

    def create_tray_icon(self):
        if pystray is None or self.tray_icon is not None:
            return
        image = self.create_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Open", self.toggle_panel, default=True),
            pystray.MenuItem("Exit", self.exit_app),
        )
        self.tray_icon = pystray.Icon("RHIF", image, "RHIF", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def minimize_to_tray(self, _=None):
        if self.panel:
            self.panel.withdraw()
        self._save_settings()
        self.create_tray_icon()

    def restore_from_tray(self, icon=None, item=None):
        if icon:
            icon.stop()
        self.tray_icon = None
        if not self.panel:
            self.build_panel()
        if self.panel:
            self.panel.deiconify()
            self.panel.lift()

    def toggle_filters(self):
        if self.filters_win and self.filters_win.winfo_exists():
            self.filters_win.destroy()
            self.filters_win = None
            return
        self.build_filters_window()

    def build_filters_window(self):
        self.filters_win = tk.Toplevel(self.panel)
        self.filters_win.title("Filters & Settings")
        self.filters_win.resizable(False, False)

        row = 0
        ttk.Label(self.filters_win, text="Domain").grid(row=row, column=0, sticky="e")
        self.domain_cb = ttk.Combobox(self.filters_win, textvariable=self.domain_var, values=sorted(self.domain_suggestions), width=15)
        self.domain_cb.grid(row=row, column=1, pady=2)
        row += 1
        ttk.Label(self.filters_win, text="Topic").grid(row=row, column=0, sticky="e")
        self.topic_cb = ttk.Combobox(self.filters_win, textvariable=self.topic_var, values=sorted(self.topic_suggestions), width=15)
        self.topic_cb.grid(row=row, column=1, pady=2)
        row += 1
        for lbl, var in [
            ("Emotion", self.emotion_var),
            ("Conversation", self.conv_var),
        ]:
            ttk.Label(self.filters_win, text=lbl).grid(row=row, column=0, sticky="e")
            ttk.Entry(self.filters_win, textvariable=var, width=15).grid(row=row, column=1, pady=2)
            row += 1

        ttk.Label(self.filters_win, text="Start").grid(row=row, column=0, sticky="e")
        DateEntry(self.filters_win, textvariable=self.start_var, width=12).grid(row=row, column=1, pady=2)
        row += 1
        ttk.Label(self.filters_win, text="End").grid(row=row, column=0, sticky="e")
        DateEntry(self.filters_win, textvariable=self.end_var, width=12).grid(row=row, column=1, pady=2)
        row += 1

        ttk.Checkbutton(self.filters_win, text="Slow", variable=self.slow_var).grid(row=row, column=0, columnspan=2)
        row += 1

        ttk.Checkbutton(self.filters_win, text="Always on top", variable=self.always_on_top_var, command=self.update_always_on_top).grid(row=row, column=0, columnspan=2)
        row += 1

        ttk.Label(self.filters_win, text="Max results").grid(row=row, column=0, sticky="e")
        ttk.Spinbox(self.filters_win, from_=1, to=100, textvariable=self.limit_var, width=5).grid(row=row, column=1, pady=2)
        row += 1

        ttk.Button(self.filters_win, text="Close", command=self.filters_win.destroy).grid(row=row, column=0, columnspan=2, pady=4)

    def update_always_on_top(self):
        if self.panel:
            self.panel.attributes("-topmost", self.always_on_top_var.get())
        self._save_settings()

    def exit_app(self, icon=None, item=None):
        if icon:
            icon.stop()
        self._save_settings()
        self.master.destroy()

    def build_panel(self):
        self.panel = tk.Toplevel(self.master)
        self.panel.title("RHIF")
        self.panel.minsize(600, 400)
        self.panel.geometry(self.settings.get("geometry", "800x500"))
        self.panel.attributes("-topmost", self.always_on_top_var.get())
        self.panel.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        # search bar
        header = ttk.Frame(self.panel)
        header.pack(side="top", fill="x")

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Combobox(header, textvariable=self.search_var, values=self.search_history)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self.search_entry.bind("<Return>", lambda e: self.run_search())
        ttk.Button(header, text="Filters", command=self.toggle_filters).pack(side="right", padx=5, pady=5)

        # placeholder text
        self.search_entry.insert(0, "Search topics…")
        self.search_entry.configure(foreground="gray")
        self.search_entry.bind("<FocusIn>", self._clear_placeholder)
        self.search_entry.bind("<FocusOut>", self._add_placeholder)

        # variables for filters
        self.domain_var = tk.StringVar()
        self.topic_var = tk.StringVar()
        self.emotion_var = tk.StringVar()
        self.conv_var = tk.StringVar()
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.slow_var = tk.BooleanVar()

        # main paned layout
        self.paned = ttk.PanedWindow(self.panel, orient=tk.HORIZONTAL)
        self.paned.pack(fill="both", expand=True)

        left = ttk.Frame(self.paned)
        right = ttk.Frame(self.paned)
        self.paned.add(left, weight=1)
        self.paned.add(right, weight=3)

        # list of results with scrollbar
        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.results = tk.Listbox(list_frame)
        vs = ttk.Scrollbar(list_frame, orient="vertical", command=self.results.yview)
        self.results.configure(yscrollcommand=vs.set)
        self.results.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.results.bind("<<ListboxSelect>>", self.on_select)

        self.preview = HTMLScrolledText(right, html="<i>Nothing selected</i>")
        self.preview.pack(fill="both", expand=True, padx=5, pady=5)

        # bottom controls panel
        bottom = ttk.Frame(self.panel)
        bottom.pack(side="bottom", fill="x", padx=5, pady=5)

        self.status_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left")

        self.info_btn = ttk.Button(bottom, text="Info", command=self.show_info)
        self.info_btn.pack(side="right")
        self.copy_btn = ttk.Button(bottom, text="Copy", command=self.copy_current)
        self.copy_btn.pack(side="right", padx=5)
        self.next_btn = ttk.Button(bottom, text="Next", command=lambda: self.move_idx(1))
        self.next_btn.pack(side="right")
        self.prev_btn = ttk.Button(bottom, text="Prev", command=lambda: self.move_idx(-1))
        self.prev_btn.pack(side="right")

        self.conv_cache = {}
        self.rows = []
        self.conv_rows = []
        self.conv_idx = -1
        self.update_status("")

    def _clear_placeholder(self, _=None):
        if self.search_entry.get() == "Search topics…":
            self.search_entry.delete(0, tk.END)
            self.search_entry.configure(foreground="black")

    def _add_placeholder(self, _=None):
        if not self.search_entry.get():
            self.search_entry.insert(0, "Search topics…")
            self.search_entry.configure(foreground="gray")

    def run_search(self):
        q = self.search_var.get().strip()
        if not q:
            return
        if q and q not in self.search_history:
            self.search_history.append(q)
            self.search_entry['values'] = self.search_history
        params = {'q': q, 'limit': str(self.limit_var.get())}
        if self.domain_var.get():
            params['domain'] = self.domain_var.get()
        if self.topic_var.get():
            params['topic'] = self.topic_var.get()
        if self.emotion_var.get():
            params['emotion'] = self.emotion_var.get()
        if self.conv_var.get():
            params['conv_id'] = self.conv_var.get()
        if self.start_var.get():
            params['start'] = self.start_var.get()
        if self.end_var.get():
            params['end'] = self.end_var.get()
        if self.slow_var.get():
            params['slow'] = '1'
        try:
            r = requests.get(
                f'{HUB_BASE}/search',
                params=params,
                headers={'Accept': 'application/json'}
            )
            r.raise_for_status()
            self.rows = r.json()
        except Exception as exc:
            self.results.delete(0, tk.END)
            self.results.insert(tk.END, f'Error: {exc}')
            self.rows = []
            return

        self.results.delete(0, tk.END)
        self.conv_cache.clear()
        for row in self.rows:
            txt = (row.get('summary') or row.get('text', ''))[:60]
            self.results.insert(tk.END, txt)
            if row.get('domain'):
                self.domain_suggestions.add(row['domain'])
            if row.get('topic'):
                self.topic_suggestions.add(row['topic'])
        if self.domain_cb:
            self.domain_cb['values'] = sorted(self.domain_suggestions)
        if self.topic_cb:
            self.topic_cb['values'] = sorted(self.topic_suggestions)
        self.preview.set_html('<i>Select an entry</i>')
        self.conv_rows = []
        self.conv_idx = -1

    def ensure_conversation(self, conv_id):
        if conv_id not in self.conv_cache:
            r = requests.get(f'{HUB_BASE}/conversation', params={'conv_id': conv_id})
            r.raise_for_status()
            rows = r.json()
            rows.sort(key=lambda x: x['turn'])
            self.conv_cache[conv_id] = rows
        self.conv_rows = self.conv_cache[conv_id]

    def show_preview(self, idx):
        row = self.rows[idx]
        self.ensure_conversation(row['conv_id'])
        i = next((n for n, r in enumerate(self.conv_rows) if r['id'] == row['id']), 0)
        self.update_status(row['conv_id'])
        self.render_entry(i)

    def render_entry(self, idx):
        if idx < 0 or idx >= len(self.conv_rows):
            return
        self.conv_idx = idx
        text = self.conv_rows[idx].get('text', '')
        html = md_to_html(text)
        self.preview.set_html(html)
        self.update_status(self.conv_rows[idx].get('conv_id', ''))
        self.update_nav()

    def update_nav(self):
        self.prev_btn['state'] = tk.NORMAL if self.conv_idx > 0 else tk.DISABLED
        self.next_btn['state'] = tk.NORMAL if 0 <= self.conv_idx < len(self.conv_rows) - 1 else tk.DISABLED

    def update_status(self, conv_id):
        self.status_var.set(f"Conversation: {conv_id}" if conv_id else "")

    def move_idx(self, delta):
        new_idx = self.conv_idx + delta
        if 0 <= new_idx < len(self.conv_rows):
            self.render_entry(new_idx)

    def on_select(self, event):
        sel = self.results.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.rows):
            return
        self.show_preview(idx)

    def show_info(self):
        if not (0 <= self.conv_idx < len(self.conv_rows)):
            return
        info = self.conv_rows[self.conv_idx].copy()
        info.pop('text', None)
        info.pop('summary', None)
        win = tk.Toplevel(self.panel)
        win.title('Entry Info')
        txt = tk.Text(win, wrap='word')
        txt.insert('1.0', json.dumps(info, indent=2))
        txt.config(state=tk.DISABLED)
        txt.pack(fill='both', expand=True)
        ttk.Button(win, text='Close', command=win.destroy).pack(pady=2)

    def copy_current(self):
        if 0 <= self.conv_idx < len(self.conv_rows):
            text = self.conv_rows[self.conv_idx].get('text', '')
            self.master.clipboard_clear()
            self.master.clipboard_append(text)


def main():
    root = tk.Tk()
    app = RHIFApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()

