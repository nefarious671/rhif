import tkinter as tk
from tkinter import ttk
from tkhtmlview import HTMLLabel
import markdown
from PIL import Image, ImageDraw
import pystray


class RHIFApp:
    """Main application class for the RHIF viewer."""

    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("RHIF Viewer")
        self.master.geometry("900x600")
        self.master.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        self._build_tray_icon()
        self._build_floating_button()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_floating_button(self) -> None:
        """Create the floating always-on-top 'R' button."""
        self.float_win = tk.Toplevel(self.master)
        self.float_win.overrideredirect(True)
        self.float_win.geometry("40x40+20+20")
        self.float_win.attributes("-topmost", True)

        canvas = tk.Canvas(self.float_win, width=40, height=40, highlightthickness=0,
                          bg=self.float_win.cget("bg"))
        canvas.pack(fill="both", expand=True)
        canvas.create_oval(2, 2, 38, 38, fill="#2b6cb0", outline="")
        canvas.create_text(20, 20, text="R", fill="white", font=("TkDefaultFont", 14, "bold"))

        canvas.bind("<ButtonPress-1>", self._start_drag)
        canvas.bind("<B1-Motion>", self._do_drag)
        canvas.bind("<ButtonRelease-1>", self._end_drag)
        canvas.bind("<Button-3>", lambda e: self.minimize_to_tray())

        self.float_canvas = canvas
        self._drag_offset = (0, 0)

    def _build_ui(self) -> None:
        """Create the main application widgets."""
        # Menu
        menubar = tk.Menu(self.master)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Quit", command=self.quit_app)
        menubar.add_cascade(label="File", menu=filem)
        self.master.config(menu=menubar)

        # Paned window setup
        paned = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=3)

        # Left pane widgets
        self.search_var = tk.StringVar()
        search = ttk.Entry(left, textvariable=self.search_var)
        search.insert(0, "Search topics…")
        search.bind("<FocusIn>", lambda e: self._clear_placeholder())
        search.bind("<FocusOut>", lambda e: self._add_placeholder())
        search.bind("<KeyRelease>", self._filter_topics)
        search.pack(fill="x", padx=4, pady=4)
        self.search_entry = search

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        self.topic_list = tk.Listbox(list_frame)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.topic_list.yview)
        self.topic_list.configure(yscrollcommand=scroll.set)
        self.topic_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.topic_list.bind("<<ListboxSelect>>", self._on_topic_select)

        # Right pane widget - HTML preview
        self.preview = HTMLLabel(right, html="<i>Select a topic</i>")
        self.preview.pack(fill="both", expand=True, padx=5, pady=5)
        self.preview_menu = tk.Menu(self.preview, tearoff=0)
        self.preview_menu.add_command(label="Copy HTML", command=self._copy_html)
        self.preview.bind("<Button-3>", self._popup_menu)

        # Bottom panel
        bottom = ttk.Frame(self.master)
        bottom.pack(fill="x")
        self.fields = {}
        for label in ["domain", "topic", "emotion", "conversation", "start", "end"]:
            ttk.Label(bottom, text=label.capitalize()).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(bottom, textvariable=var, width=8).pack(side="left", padx=2)
            self.fields[label] = var

        self.prev_btn = ttk.Button(bottom, text="Prev", command=self._prev_topic)
        self.prev_btn.pack(side="right", padx=2)
        self.next_btn = ttk.Button(bottom, text="Next", command=self._next_topic)
        self.next_btn.pack(side="right")
        self.copy_btn = ttk.Button(bottom, text="Copy", command=self._copy_markdown)
        self.copy_btn.pack(side="right", padx=2)

        self._load_dummy_data()

    # ------------------------------------------------------------------
    # Dummy data handling
    # ------------------------------------------------------------------
    def _load_dummy_data(self) -> None:
        """Populate listbox with dummy topics and markdown."""
        self.topics = {
            f"Topic {i}": f"# Topic {i}\n\nThis is **markdown** content for topic {i}." for i in range(1, 11)
        }
        self.topic_titles = list(self.topics.keys())
        self._refresh_list()
        self.current_index = -1
        self._update_nav()

    def _refresh_list(self, filter_text: str = "") -> None:
        self.topic_list.delete(0, tk.END)
        for title in self.topic_titles:
            if filter_text.lower() in title.lower():
                self.topic_list.insert(tk.END, title)

    # ------------------------------------------------------------------
    # Placeholder logic
    # ------------------------------------------------------------------
    def _clear_placeholder(self) -> None:
        if self.search_entry.get() == "Search topics…":
            self.search_entry.delete(0, tk.END)
            self.search_entry.configure(foreground="black")

    def _add_placeholder(self) -> None:
        if not self.search_entry.get():
            self.search_entry.insert(0, "Search topics…")
            self.search_entry.configure(foreground="grey")

    def _filter_topics(self, event=None) -> None:
        text = self.search_var.get()
        if text == "Search topics…":
            text = ""
        self._refresh_list(text)

    # ------------------------------------------------------------------
    # Listbox selection
    # ------------------------------------------------------------------
    def _on_topic_select(self, event=None) -> None:
        sel = self.topic_list.curselection()
        if not sel:
            return
        index = sel[0]
        title = self.topic_list.get(index)
        self.current_index = self.topic_titles.index(title)
        self._display_markdown(title)
        self._update_nav()

    def _display_markdown(self, title: str) -> None:
        pos = self.preview.yview()[0]
        md_text = self.topics.get(title, "")
        html = markdown.markdown(md_text)
        self.preview.set_html(html)
        self.preview.yview_moveto(pos)

    # ------------------------------------------------------------------
    # Bottom navigation
    # ------------------------------------------------------------------
    def _prev_topic(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            title = self.topic_titles[self.current_index]
            self._select_title(title)

    def _next_topic(self) -> None:
        if self.current_index < len(self.topic_titles) - 1:
            self.current_index += 1
            title = self.topic_titles[self.current_index]
            self._select_title(title)

    def _select_title(self, title: str) -> None:
        idx = self.topic_titles.index(title)
        self.topic_list.selection_clear(0, tk.END)
        self.topic_list.selection_set(idx)
        self.topic_list.activate(idx)
        self._display_markdown(title)
        self._update_nav()

    def _update_nav(self) -> None:
        self.prev_btn["state"] = tk.NORMAL if self.current_index > 0 else tk.DISABLED
        self.next_btn["state"] = tk.NORMAL if self.current_index < len(self.topic_titles) - 1 else tk.DISABLED

    # ------------------------------------------------------------------
    # Clipboard helpers and context menu
    # ------------------------------------------------------------------
    def _copy_markdown(self) -> None:
        if 0 <= self.current_index < len(self.topic_titles):
            md = self.topics[self.topic_titles[self.current_index]]
            self.master.clipboard_clear()
            self.master.clipboard_append(md)

    def _copy_html(self) -> None:
        if 0 <= self.current_index < len(self.topic_titles):
            html = markdown.markdown(self.topics[self.topic_titles[self.current_index]])
            self.master.clipboard_clear()
            self.master.clipboard_append(html)

    def _popup_menu(self, event) -> None:
        self.preview_menu.tk_popup(event.x_root, event.y_root)

    # ------------------------------------------------------------------
    # Drag handling for floating button
    # ------------------------------------------------------------------
    def _start_drag(self, event) -> None:
        self._drag_offset = (event.x, event.y)

    def _do_drag(self, event) -> None:
        x = self.float_win.winfo_x() + event.x - self._drag_offset[0]
        y = self.float_win.winfo_y() + event.y - self._drag_offset[1]
        self.float_win.geometry(f"+{x}+{y}")

    def _end_drag(self, event) -> None:
        if abs(event.x - self._drag_offset[0]) < 5 and abs(event.y - self._drag_offset[1]) < 5:
            if self.master.state() == "normal" and self.master.winfo_viewable():
                self.master.withdraw()
            else:
                self.master.deiconify()
                self.master.lift()

    # ------------------------------------------------------------------
    # System tray integration
    # ------------------------------------------------------------------
    def _build_tray_icon(self) -> None:
        size = 64
        image = Image.new("RGBA", (size, size), (43, 108, 176, 255))
        draw = ImageDraw.Draw(image)
        w, h = draw.textsize("R")
        draw.text(((size - w) / 2, (size - h) / 2), "R", fill="white")
        menu = pystray.Menu(
            pystray.MenuItem("Restore", self.show_app, default=True),
            pystray.MenuItem("Quit", self.quit_app)
        )
        self.tray_icon = pystray.Icon("rhif", image, "RHIF Viewer", menu)
        # Start icon thread hidden
        self.tray_icon.run_detached()
        self.tray_icon.visible = False

    def minimize_to_tray(self, *args) -> None:
        self.master.withdraw()
        self.float_win.withdraw()
        self.tray_icon.visible = True

    def show_app(self, *args) -> None:
        self.master.deiconify()
        self.float_win.deiconify()
        self.master.lift()
        self.tray_icon.visible = False

    def quit_app(self, *args) -> None:
        try:
            self.tray_icon.stop()
        except Exception:
            pass
        self.master.destroy()


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = RHIFApp(root)
    root.mainloop()
