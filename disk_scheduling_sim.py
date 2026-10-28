"""
Multithreaded Disk Scheduling Simulator
FCFS, SSTF, SCAN, C-SCAN and LOOK each run in their OWN THREAD.
Results are stored in a shared dictionary protected by a Lock (mutex).
The main thread join()s all workers, then draws the graphs and comparison.
"""
import threading
import random
import tkinter as tk
from tkinter import ttk, messagebox

# ------------------------------------------------------------------ theme
PURPLE = "#6b3fa0"
PURPLE_DARK = "#4b2a75"
PURPLE_LIGHT = "#e6dcf3"
OFFWHITE = "#faf7f2"
TEXT = "#2d2340"


# ------------------------------------------------------------- algorithms
# Each returns the PATH of head positions (starting with the initial head).

def fcfs(reqs, head, size, direction):
    return [head] + list(reqs)


def sstf(reqs, head, size, direction):
    path, pending, cur = [head], list(reqs), head
    while pending:
        nxt = min(pending, key=lambda r: abs(r - cur))
        pending.remove(nxt)
        path.append(nxt)
        cur = nxt
    return path


def _split(reqs, head):
    lower = sorted(r for r in reqs if r < head)
    upper = sorted(r for r in reqs if r >= head)
    return lower, upper


def scan(reqs, head, size, direction):
    lower, upper = _split(reqs, head)
    if direction == "right":
        path = [head] + upper + [size - 1]
        if lower:
            path += lower[::-1]
    else:
        path = [head] + lower[::-1] + [0]
        if upper:
            path += upper
    return path


def cscan(reqs, head, size, direction):
    lower, upper = _split(reqs, head)
    if direction == "right":
        path = [head] + upper + [size - 1, 0] + lower
    else:
        path = [head] + lower[::-1] + [0, size - 1] + upper[::-1]
    return path


def look(reqs, head, size, direction):
    lower, upper = _split(reqs, head)
    if direction == "right":
        path = [head] + upper + lower[::-1]
    else:
        path = [head] + lower[::-1] + upper
    return path


ALGORITHMS = {"FCFS": fcfs, "SSTF": sstf, "SCAN": scan, "C-SCAN": cscan, "LOOK": look}


def seek_time(path):
    return sum(abs(path[i + 1] - path[i]) for i in range(len(path) - 1))


# --------------------------------------------------------- threading part
results = {}                      # shared resource
results_lock = threading.Lock()   # mutex protecting it


def worker(name, func, reqs, head, size, direction):
    path = func(reqs, head, size, direction)
    total = seek_time(path)
    with results_lock:            # critical section
        results[name] = {
            "path": path,
            "seek": total,
            "avg": total / len(reqs),
            "thread": threading.current_thread().name,
        }


def run_all(reqs, head, size, direction):
    """One thread per algorithm; main thread waits with join()."""
    results.clear()
    threads = [
        threading.Thread(target=worker, name=f"{n}-thread",
                         args=(n, f, reqs, head, size, direction))
        for n, f in ALGORITHMS.items()
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return {n: results[n] for n in ALGORITHMS}   # keep a fixed order


# -------------------------------------------------------------------- GUI
class GraphCanvas(tk.Canvas):
    """Head-movement graph: x = cylinder number, y = step (top to bottom)."""

    def __init__(self, master):
        super().__init__(master, bg=OFFWHITE, highlightthickness=0)
        self.data = None
        self.bind("<Configure>", lambda e: self.redraw())

    def set_data(self, path, size, title):
        self.data = (path, size, title)
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.data:
            return
        path, size, title = self.data
        w, h = max(self.winfo_width(), 500), max(self.winfo_height(), 300)
        left, right, top, bottom = 40, w - 40, 70, h - 20
        self.create_text(w / 2, 20, text=title, font=("Helvetica", 13, "bold"), fill=PURPLE_DARK)

        def X(v):
            return left + (right - left) * v / max(size - 1, 1)

        # axis with ticks
        self.create_line(left, top - 10, right, top - 10, fill=PURPLE_DARK)
        for i in range(0, 6):
            v = round((size - 1) * i / 5)
            self.create_line(X(v), top - 14, X(v), top - 6, fill=PURPLE_DARK)
            self.create_text(X(v), top - 24, text=str(v), font=("Helvetica", 9), fill=TEXT)

        steps = len(path) - 1
        step_h = (bottom - top) / max(steps, 1)
        pts = [(X(p), top + i * step_h) for i, p in enumerate(path)]
        for i in range(steps):
            self.create_line(*pts[i], *pts[i + 1], fill=PURPLE, width=2)
        for i, (x, y) in enumerate(pts):
            self.create_oval(x - 4, y - 4, x + 4, y + 4,
                             fill=PURPLE_DARK if i == 0 else PURPLE, outline="")
            self.create_text(x + 10, y, text=str(path[i]), anchor="w",
                             font=("Helvetica", 9), fill=TEXT)


class BarCanvas(tk.Canvas):
    """Comparison of total seek time."""

    def __init__(self, master):
        super().__init__(master, bg=OFFWHITE, highlightthickness=0)
        self.res = None
        self.bind("<Configure>", lambda e: self.redraw())

    def set_data(self, res):
        self.res = res
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.res:
            return
        w, h = max(self.winfo_width(), 500), max(self.winfo_height(), 300)
        self.create_text(w / 2, 20, text="Total seek time comparison",
                         font=("Helvetica", 13, "bold"), fill=PURPLE_DARK)
        base, top = h - 40, 60
        mx = max(max(v["seek"] for v in self.res.values()), 1)
        n = len(self.res)
        bw = min(90, (w - 80) / (n * 1.6))
        gap = bw * 0.6
        x = (w - (n * bw + (n - 1) * gap)) / 2
        best = min(self.res, key=lambda k: self.res[k]["seek"])
        for name, v in self.res.items():
            bh = (base - top) * v["seek"] / mx
            self.create_rectangle(x, base - bh, x + bw, base,
                                  fill=PURPLE_DARK if name == best else PURPLE, outline="")
            self.create_text(x + bw / 2, base - bh - 12, text=str(v["seek"]),
                             font=("Helvetica", 11, "bold"), fill=TEXT)
            self.create_text(x + bw / 2, base + 16, text=name,
                             font=("Helvetica", 10), fill=TEXT)
            x += bw + gap
        self.create_line(30, base, w - 30, base, fill=PURPLE_DARK)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Multithreaded Disk Scheduling Simulator")
        self.geometry("980x700")
        self.configure(bg=OFFWHITE)
        self.res = None

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=OFFWHITE)
        style.configure("TLabel", background=OFFWHITE, foreground=TEXT)
        style.configure("TNotebook", background=OFFWHITE)
        style.configure("TNotebook.Tab", background=PURPLE_LIGHT, foreground=PURPLE_DARK,
                        padding=(14, 6))
        style.map("TNotebook.Tab", background=[("selected", PURPLE)],
                  foreground=[("selected", "white")])
        style.configure("Treeview", background="white", fieldbackground="white",
                        foreground=TEXT, rowheight=26)
        style.configure("Treeview.Heading", background=PURPLE, foreground="white",
                        font=("Helvetica", 10, "bold"))
        style.map("Treeview", background=[("selected", PURPLE_LIGHT)],
                  foreground=[("selected", PURPLE_DARK)])

        # header
        header = tk.Frame(self, bg=PURPLE)
        header.pack(fill="x")
        tk.Label(header, text="Disk Scheduling Simulator", bg=PURPLE, fg="white",
                 font=("Helvetica", 18, "bold")).pack(anchor="w", padx=16, pady=(10, 0))
        tk.Label(header, text="FCFS  |  SSTF  |  SCAN  |  C-SCAN  |  LOOK   (one thread each)",
                 bg=PURPLE, fg=PURPLE_LIGHT, font=("Helvetica", 10)).pack(anchor="w", padx=16, pady=(0, 10))

        # inputs
        form = ttk.Frame(self, padding=12)
        form.pack(fill="x")
        ttk.Label(form, text="Request queue:").grid(row=0, column=0, sticky="w")
        self.reqs_var = tk.StringVar(value="98 183 37 122 14 124 65 67")
        ttk.Entry(form, textvariable=self.reqs_var, width=48).grid(row=0, column=1, columnspan=5, padx=6, sticky="we")

        ttk.Label(form, text="Initial head:").grid(row=1, column=0, sticky="w", pady=8)
        self.head_var = tk.StringVar(value="53")
        ttk.Entry(form, textvariable=self.head_var, width=8).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Disk size (cylinders):").grid(row=1, column=2, sticky="e")
        self.size_var = tk.StringVar(value="200")
        ttk.Entry(form, textvariable=self.size_var, width=8).grid(row=1, column=3, sticky="w", padx=6)
        ttk.Label(form, text="Direction:").grid(row=1, column=4, sticky="e")
        self.dir_var = tk.StringVar(value="right")
        ttk.Combobox(form, textvariable=self.dir_var, values=["right", "left"],
                     width=8, state="readonly").grid(row=1, column=5, sticky="w", padx=6)

        btns = ttk.Frame(self, padding=(12, 0))
        btns.pack(fill="x")
        self.button(btns, "Run simulation", self.run, primary=True).pack(side="left")
        self.button(btns, "Random queue", self.random_queue).pack(side="left", padx=8)
        self.button(btns, "Reset example", self.reset).pack(side="left")

        # results table
        self.table = ttk.Treeview(self, columns=("alg", "seek", "avg", "thread"),
                                  show="headings", height=5)
        for col, txt, wd in (("alg", "Algorithm", 120), ("seek", "Total seek time", 140),
                             ("avg", "Avg seek / request", 150), ("thread", "Ran on", 160)):
            self.table.heading(col, text=txt)
            self.table.column(col, width=wd, anchor="center")
        self.table.pack(fill="x", padx=12, pady=12)
        self.best_label = ttk.Label(self, text="", font=("Helvetica", 11, "bold"),
                                    foreground=PURPLE_DARK)
        self.best_label.pack(anchor="w", padx=14)

        # graph tabs
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=12)
        self.graphs = {}
        for name in ALGORITHMS:
            g = GraphCanvas(self.nb)
            self.nb.add(g, text=name)
            self.graphs[name] = g
        self.bars = BarCanvas(self.nb)
        self.nb.add(self.bars, text="Comparison")

    @staticmethod
    def button(parent, text, cmd, primary=False):
        return tk.Button(parent, text=text, command=cmd, relief="flat", cursor="hand2",
                         bg=PURPLE if primary else PURPLE_LIGHT,
                         fg="white" if primary else PURPLE_DARK,
                         activebackground=PURPLE_DARK, activeforeground="white",
                         font=("Helvetica", 10, "bold"), padx=14, pady=6)

    def parse(self):
        try:
            reqs = [int(x) for x in self.reqs_var.get().replace(",", " ").split()]
            head, size = int(self.head_var.get()), int(self.size_var.get())
            if not reqs or size < 2:
                raise ValueError("Enter at least one request and a disk size of 2 or more.")
            if not 0 <= head < size:
                raise ValueError(f"Head must be between 0 and {size - 1}.")
            if any(r < 0 or r >= size for r in reqs):
                raise ValueError(f"All requests must be between 0 and {size - 1}.")
            return reqs, head, size, self.dir_var.get()
        except ValueError as e:
            msg = str(e) if "invalid literal" not in str(e) else "Please enter whole numbers only."
            messagebox.showerror("Invalid input", msg)
            return None

    def random_queue(self):
        size = int(self.size_var.get() or 200)
        self.reqs_var.set(" ".join(str(random.randint(0, size - 1)) for _ in range(8)))
        self.head_var.set(str(random.randint(0, size - 1)))

    def reset(self):
        self.reqs_var.set("98 183 37 122 14 124 65 67")
        self.head_var.set("53")
        self.size_var.set("200")
        self.dir_var.set("right")

    def run(self):
        parsed = self.parse()
        if not parsed:
            return
        reqs, head, size, direction = parsed
        res = run_all(reqs, head, size, direction)
        self.table.delete(*self.table.get_children())
        for name, v in res.items():
            self.table.insert("", "end", values=(name, v["seek"], f"{v['avg']:.2f}", v["thread"]))
        best = min(res, key=lambda k: res[k]["seek"])
        self.best_label.config(text=f"Best: {best} with total seek time {res[best]['seek']}")
        for name, v in res.items():
            order = " -> ".join(map(str, v["path"]))
            self.graphs[name].set_data(v["path"], size,
                                       f"{name}: head movement (seek = {v['seek']})")
        self.bars.set_data(res)


if __name__ == "__main__":
    App().mainloop()
