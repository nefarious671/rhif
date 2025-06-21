import tkinter as tk
from tkinter import ttk
from tkhtmlview import HTMLLabel
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


class RHIFApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.withdraw()  # hide main window

        master.option_add("*Font", "Segoe UI 11")

        self.panel = None
        self.tray_icon = None
        self.toggle = tk.Toplevel(master)
        self.toggle.overrideredirect(True)
        self.toggle.geometry("40x40+20+20")
        self.toggle.attributes("-topmost", True)
        self.toggle.attributes("-alpha", 0.9)

        self.toggle_canvas = tk.Canvas(
            self.toggle,
            width=40,
            height=40,
            highlightthickness=0,
            bg=self.toggle.cget("bg"),
        )
        self.toggle_canvas.pack(fill="both", expand=True)
        self.toggle_canvas.create_oval(2, 2, 38, 38, fill="#2b6cb0", outline="")
        self.toggle_canvas.create_text(
            20,
            20,
            text="R",
            fill="white",
            font=("Segoe UI", 14, "bold"),
        )
        self.toggle_canvas.bind("<ButtonPress-1>", self.start_drag)
        self.toggle_canvas.bind("<B1-Motion>", self.do_drag)
        self.toggle_canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.toggle_canvas.bind("<Button-3>", self.minimize_to_tray)

    def toggle_panel(self):
        if self.panel and self.panel.winfo_viewable():
            self.panel.withdraw()
        else:
            if not self.panel:
                self.build_panel()
            if self.panel:
                self.panel.deiconify()
                self.panel.lift()

    def start_drag(self, event):
        self._drag_offset = (event.x, event.y)

    def do_drag(self, event):
        x = self.toggle.winfo_x() + event.x - self._drag_offset[0]
        y = self.toggle.winfo_y() + event.y - self._drag_offset[1]
        self.toggle.geometry(f"+{x}+{y}")

    def end_drag(self, event):
        if abs(event.x - self._drag_offset[0]) < 5 and abs(event.y - self._drag_offset[1]) < 5:
            self.toggle_panel()

    def create_tray_image(self):
        if Image is None:
            return None
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((0, 0, 64, 64), fill=(43, 108, 176, 255))
        w, h = draw.textsize("R")
        draw.text(((64 - w) / 2, (64 - h) / 2), "R", fill="white")
        return img

    def minimize_to_tray(self, _=None):
        if pystray is None:
            self.toggle.withdraw()
            if self.panel:
                self.panel.withdraw()
            return
        self.toggle.withdraw()
        if self.panel:
            self.panel.withdraw()

        image = self.create_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem(
                "Restore", self.restore_from_tray, default=True
            ),
            pystray.MenuItem("Exit", self.exit_app),
        )
        self.tray_icon = pystray.Icon("RHIF", image, "RHIF", menu)

        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def restore_from_tray(self, icon=None, item=None):
        if icon:
            icon.stop()
        self.tray_icon = None
        self.master.deiconify()
        self.toggle.deiconify()
        if self.panel:
            self.panel.deiconify()
        self.toggle.lift()

    def exit_app(self, icon=None, item=None):
        if icon:
            icon.stop()
        self.master.destroy()

    def build_panel(self):
        self.panel = tk.Toplevel(self.master)
        self.panel.title("RHIF")
        self.panel.geometry("800x500")
        self.panel.attributes("-topmost", True)
        self.panel.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        # search bar
        header = ttk.Frame(self.panel)
        header.pack(side="top", fill="x")

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(header, textvariable=self.search_var)
        self.search_entry.pack(side="top", fill="x", expand=True, padx=6, pady=6)
        self.search_entry.bind("<Return>", lambda e: self.run_search())

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

        self.preview = HTMLLabel(right, html="<i>Nothing selected</i>")
        self.preview.pack(fill="both", expand=True, padx=5, pady=5)

        # bottom filter+controls panel
        bottom = ttk.Frame(self.panel)
        bottom.pack(side="bottom", fill="x", padx=5, pady=5)

        for lbl, var in [
            ("Domain", self.domain_var),
            ("Topic", self.topic_var),
            ("Emotion", self.emotion_var),
            ("Conversation", self.conv_var),
            ("Start", self.start_var),
            ("End", self.end_var),
        ]:
            ttk.Label(bottom, text=lbl).pack(side="left")
            ttk.Entry(bottom, textvariable=var, width=10).pack(side="left", padx=2)
        ttk.Checkbutton(bottom, text="Slow", variable=self.slow_var).pack(side="left", padx=4)

        self.prev_btn = ttk.Button(bottom, text="Prev", command=lambda: self.move_idx(-1))
        self.prev_btn.pack(side="left", padx=5)
        self.next_btn = ttk.Button(bottom, text="Next", command=lambda: self.move_idx(1))
        self.next_btn.pack(side="left")
        self.copy_btn = ttk.Button(bottom, text="Copy", command=self.copy_current)
        self.copy_btn.pack(side="right")

        self.conv_cache = {}
        self.rows = []
        self.conv_rows = []
        self.conv_idx = -1

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
        params = {'q': q, 'limit': '20'}
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
        self.render_entry(i)

    def render_entry(self, idx):
        if idx < 0 or idx >= len(self.conv_rows):
            return
        self.conv_idx = idx
        text = self.conv_rows[idx].get('text', '')
        html = md_to_html(text)
        self.preview.set_html(html)
        self.update_nav()

    def update_nav(self):
        self.prev_btn['state'] = tk.NORMAL if self.conv_idx > 0 else tk.DISABLED
        self.next_btn['state'] = tk.NORMAL if 0 <= self.conv_idx < len(self.conv_rows) - 1 else tk.DISABLED

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

