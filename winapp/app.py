import tkinter as tk
from tkinter import ttk
from tkhtmlview import HTMLLabel
import requests

HUB_BASE = 'http://127.0.0.1:8765'


def md_to_html(md: str) -> str:
    """Convert a subset of Markdown to HTML."""
    html = (
        md.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )
    html = html.replace('```\n', '<pre><code>')
    html = html.replace('```', '</code></pre>')
    html = html.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
    html = html.replace('*', '<em>', 1).replace('*', '</em>', 1)
    html = html.replace('`', '<code>', 1).replace('`', '</code>', 1)
    html = html.replace('\n', '<br>')
    return html


class RhifApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.withdraw()  # hide main window

        self.panel = None
        self.toggle = tk.Toplevel(master)
        self.toggle.overrideredirect(True)
        self.toggle.geometry('50x50+20+20')
        self.toggle.attributes('-topmost', True)

        self.toggle_canvas = tk.Canvas(
            self.toggle,
            width=50,
            height=50,
            highlightthickness=0,
            bg=self.toggle.cget("bg"),
        )
        self.toggle_canvas.pack(fill="both", expand=True)
        self.toggle_canvas.create_oval(2, 2, 48, 48, fill="#2b6cb0", outline="")
        self.toggle_canvas.create_text(
            25,
            25,
            text="R",
            fill="white",
            font=("TkDefaultFont", 16, "bold"),
        )
        self.toggle_canvas.bind("<ButtonPress-1>", self.start_drag)
        self.toggle_canvas.bind("<B1-Motion>", self.do_drag)
        self.toggle_canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.toggle_canvas.bind("<Button-3>", lambda e: self.master.destroy())

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

    def build_panel(self):
        self.panel = tk.Toplevel(self.master)
        self.panel.title('RHIF')
        self.panel.geometry('600x400')
        self.panel.attributes('-topmost', True)

        header = ttk.Frame(self.panel)
        header.pack(side='top', fill='x')

        self.search_var = tk.StringVar()
        search = ttk.Entry(header, textvariable=self.search_var)
        search.pack(side='left', fill='x', expand=True, padx=4, pady=4)
        search.bind('<Return>', lambda e: self.run_search())

        ttk.Button(header, text='Filters', command=self.toggle_filters).pack(side='right')

        self.filter_frame = ttk.Frame(self.panel)
        self.filter_frame.pack(side='top', fill='x')
        self.filter_frame.pack_forget()

        self.domain_var = tk.StringVar()
        self.topic_var = tk.StringVar()
        self.emotion_var = tk.StringVar()
        self.conv_var = tk.StringVar()
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.slow_var = tk.BooleanVar()

        for text, var in [
            ('Domain', self.domain_var),
            ('Topic', self.topic_var),
            ('Emotion', self.emotion_var),
            ('Conversation', self.conv_var),
        ]:
            ttk.Label(self.filter_frame, text=text).pack(side='left')
            ttk.Entry(self.filter_frame, textvariable=var, width=8).pack(side='left')
        ttk.Label(self.filter_frame, text='Start').pack(side='left')
        ttk.Entry(self.filter_frame, textvariable=self.start_var, width=10).pack(side='left')
        ttk.Label(self.filter_frame, text='End').pack(side='left')
        ttk.Entry(self.filter_frame, textvariable=self.end_var, width=10).pack(side='left')
        ttk.Checkbutton(self.filter_frame, text='Slow', variable=self.slow_var).pack(side='left')

        main = ttk.Frame(self.panel)
        main.pack(fill='both', expand=True)

        self.results = tk.Listbox(main)
        self.results.pack(side='left', fill='y')
        self.results.bind('<<ListboxSelect>>', self.on_select)

        self.preview = HTMLLabel(main, html='<i>Nothing selected</i>')
        self.preview.pack(side='left', fill='both', expand=True)

        controls = ttk.Frame(self.panel)
        controls.pack(side='bottom', fill='x')
        self.prev_btn = ttk.Button(controls, text='Prev', command=lambda: self.move_idx(-1))
        self.prev_btn.pack(side='left')
        self.next_btn = ttk.Button(controls, text='Next', command=lambda: self.move_idx(1))
        self.next_btn.pack(side='left')
        self.copy_btn = ttk.Button(controls, text='Copy', command=self.copy_current)
        self.copy_btn.pack(side='right')

        self.conv_cache = {}
        self.rows = []
        self.conv_rows = []
        self.conv_idx = -1

    def toggle_filters(self):
        if self.filter_frame.winfo_manager():
            self.filter_frame.pack_forget()
        else:
            self.filter_frame.pack(side='top', fill='x')

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
    app = RhifApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
