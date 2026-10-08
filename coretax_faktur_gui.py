"""Coretax Faktur Keluaran dari Zahir Online (zsql) - aplikasi desktop (Tkinter).
Logika inti ada di core.py (dipakai juga oleh versi web/Vercel). Build .exe: jalankan build.bat (Windows)."""
from core import *            # noqa: F401,F403  (query, normalisasi, export, login, lisensi, referensi)

# ----------------------------- GUI -----------------------------
import os, pathlib, threading, calendar
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def wide_popdown(cb, extra=340):
    """Lebarkan daftar dropdown Combobox ke KANAN agar uraian panjang terbaca utuh.
    Lebar tambahan dihitung saat dibuka: secukupnya untuk teks terpanjang, dan tidak melewati tepi kanan layar."""
    name = f"W{id(cb)}.TCombobox"
    st = ttk.Style(cb); cb.configure(style=name)
    def post():
        try:
            vals = [str(v) for v in cb.cget("values")]
            need = max([len(v) for v in vals] + [0]) * 7 + 40 - cb.winfo_width()       # perkiraan lebar teks
            room = cb.winfo_screenwidth() - (cb.winfo_rootx() + cb.winfo_width()) - 12
            st.configure(name, postoffset=(0, 0, max(0, min(extra, need, room)), 0))
        except tk.TclError:
            pass
    cb.configure(postcommand=post)


SETTINGS = pathlib.Path(os.environ.get("APPDATA") or pathlib.Path.home()) / "CoretaxFaktur" / "settings.json"


def load_settings():
    try: return json.loads(SETTINGS.read_text("utf-8"))
    except Exception: return {}


def save_settings(d):
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        cur = load_settings(); cur.update(d)
        SETTINGS.write_text(json.dumps(cur), "utf-8")
    except Exception: pass


# Aset gambar (PNG base64): logo lengkap untuk header, ikon Z untuk jendela/taskbar.
LOGO_B64 = (
    "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"
    "=="
)
ICON64_B64 = (
    "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"
    "=="
)
ICON32_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAD1klEQVR42r2Xz28bVRDHvzPveTdRnTgJoQlRovaCkDhwiipVHHoG0ebkklag3H"
    "psRP8AfrcEDo36N6RCjRcOlRB3DogLQohr4FAFbMdSqd2GOOvdN8PBsUmaXXtjp4y0p327n3nzewgAUCwZBFfd7PUfz7E3vgrCOxB3DkAOAGE4"
    "UQAR2DyC4jtpPb1X/frNRx0moagGAbm5935aRq5wj413Vl0Ilfjg29MQArEFGR/iWjVEjdXy/YsPUFRDADD7/s9FOzJV0rgJdS0HAgNEOFVRhU"
    "LIeIbsKOL9v69WNxYDmnv3hwX1C7+xyRVUWgKQwQsVdcQei4saFDbeYPHzt9jPT6j7P+AAQEZdS9jPT4ifv2UZtIQ41LbZE47T0IZPCglGHCqD"
    "lixACyoxpQV75HSoWLSGEq/VDnJasCCyvQhTeQvLNJAOIorGnkvPTiJr08weO8Vk3uL7j17FZN5CpLc7mI6anRh4tufw1idbqNUj5CwlusP28p"
    "01hPmXPOTsYIHgW4ZnUuKgnwIdK2yV9zF+xrRvRc/HEkBEaIaC8zMe+OCAaPudYSByvS1n025vmPB0z+HtT7dAKQoaJtQaMT64MoMPl1+Bduu2"
    "gplwO6jgz8ctnPEZoie0QEfCKPlLy8BfjQirl2fw8fW5rplFFYYJn29W8EVQxdSYSYVnUuBYFhFgOzdfmsHaynzX5Ifhd4IKpsctnPTOH87Syg"
    "4/hgk79Qg3L5/F2sp8F5AEF+mfvHzSolKrR1i9MtOFExH0CLzchWepHXy68Aqmx3OZ4ZkVyA63J4JnUiAJzofgt0tt+MsFC1HtpmLW0tUzC5iQ"
    "DD8Ixs82y7hTqmC6YI80LT1BN7XpcMI/ocPNBDgArH1TwZffVjE7mYOTdl04XtAU/RKB5lZ+1bQyPJG3+GX9dYx4DNX/Go4o8Ht5H75HiT2/U7"
    "b3QsHyV3+g1ogHa0Y5Q3BO22A6Wpxemx/JNA97KeBMMRC7dj9npmPNSHr8tXN2tyl9m1GiC44MJGOdgUQzR3Y7EwhOFI+fxX2CUDUGcepUVKtH"
    "PU3YZx1AzlD6S5XYArpNbM+rtBKTZtBhpOdQClXiHNSF2yzQh7A+QSFpPxjmSfGRwPok0IfM4e5dCXfrZDwG1L34vUAdGY8l3K1zuHuXy5uXtl"
    "XjG2RHidgzUHUY3Ot9VjN1xJ4hO0qq8Y3y5qVtRlFNdWMxkObONQXV2BszxB4NvxQ/v5x6xN6YUVBNmjvXqhuLAYpqGAE5FEumfP/iAwmfXJC4"
    "ua6QLUBbp7QeK6AthWxJ3FyX8MmF9mZcMgjI/QsD4TmDArs5fAAAAABJRU5ErkJggg=="
)
HDR = "#151515"    # warna latar header = warna latar logo


BG, CARD, PRI, PRI_D, TXT, MUT = "#F3F5F9", "#FFFFFF", "#0B5FA5", "#084A82", "#1F2937", "#6B7280"
LBL, LINE = "#374151", "#E1E6EE"
SIDE_W = 460                              # lebar panel kiri (px)          # warna label field (lebih gelap dari MUT) & garis pemisah
OK_C, BAD_C, WARN_C, FONT = "#15803D", "#B42318", "#B45309", "Segoe UI"
PILL = {"ok": ("#DCFCE7", OK_C), "bad": ("#FEE2E2", BAD_C), "warn": ("#FEF3C7", WARN_C),
        "idle": ("#E5E7EB", MUT), "busy": ("#DBEAFE", PRI)}


class ScrollFrame(tk.Frame):
    """Frame dengan scrollbar vertikal; isi diletakkan di .inner. Roda mouse aktif saat kursor di atasnya."""
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        bg = kw.get("bg", CARD)
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.inner = tk.Frame(self.cv, bg=bg)
        self._win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.cv.configure(yscrollcommand=self.sb.set)
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", self._sync); self.cv.bind("<Configure>", self._sync)
        self.bind_all("<MouseWheel>", self._wheel, add="+")
        self.bind_all("<Button-4>", lambda e: self._scroll(-1), add="+"); self.bind_all("<Button-5>", lambda e: self._scroll(1), add="+")
    def _sync(self, _=None):
        self.cv.itemconfigure(self._win, width=self.cv.winfo_width())
        self.cv.configure(scrollregion=self.cv.bbox("all"))
        need = self.inner.winfo_reqheight() > self.cv.winfo_height() + 2
        if need and not self.sb.winfo_ismapped(): self.sb.pack(side="right", fill="y")
        elif not need and self.sb.winfo_ismapped(): self.sb.pack_forget(); self.cv.yview_moveto(0)
    def _inside(self):
        x, y = self.winfo_pointerxy(); w = self.winfo_containing(x, y)
        while w is not None:
            if w is self: return True
            w = w.master
        return False
    def _scroll(self, n):
        if self.sb.winfo_ismapped() and self._inside(): self.cv.yview_scroll(n, "units")
    def _wheel(self, e):
        self._scroll(-1 if e.delta > 0 else 1)


class Tip:
    """Tooltip sederhana: muncul saat kursor diam di atas widget."""
    def __init__(self, w, text):
        self.w, self.text, self.tw, self.job = w, text, None, None
        w.bind("<Enter>", self._sched, add="+"); w.bind("<Leave>", self._hide, add="+"); w.bind("<ButtonPress>", self._hide, add="+")
    def _sched(self, _=None):
        self._hide(); self.job = self.w.after(450, self._show)
    def _show(self):
        x = self.w.winfo_rootx() + 8; y = self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tw = tk.Toplevel(self.w); self.tw.wm_overrideredirect(True); self.tw.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tw, text=self.text, bg="#1F2937", fg="white", font=(FONT, 9), padx=8, pady=5,
                 justify="left", wraplength=320).pack()
    def _hide(self, _=None):
        if self.job: self.w.after_cancel(self.job); self.job = None
        if self.tw: self.tw.destroy(); self.tw = None


EMPTY_TXT = "Belum ada data\nKlik  \u25B6 Preview  untuk menarik faktur pada periode ini"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Zahir Coretax - Faktur Pajak Keluaran")
        self._icons = [tk.PhotoImage(data="".join(x.split())) for x in (ICON64_B64, ICON32_B64)]
        self.iconphoto(True, *self._icons)                          # ikon Z saja (jendela, taskbar, dialog)
        self.geometry("1366x900"); self.minsize(1240, 720); self.configure(bg=BG)
        self.token = self.slug = ""; self.logged_in = False; self.db_map = {}; self.lic_exp = None; self._gen = 0; self.db_ok = False; self._busy = 0
        self.v = {k: tk.StringVar() for k in ("server", "email", "password", "db", "npwp", "d1", "d2", "kode_a", "kode_b", "kode_trx", "cust",
                                                   "trx_txt", "ket_txt", "cap_txt")}
        self.cust_map = {}; self.cust_sel = set(); self.v["cust"].set(ALL_CUST)
        t = dt.date.today()
        self.v["d1"].set(t.replace(day=1).isoformat())
        self.v["d2"].set(t.replace(day=calendar.monthrange(t.year, t.month)[1]).isoformat())
        st = load_settings()
        self.v["server"].set(st.get("server", SERVER)); self.servers = st.get("servers") or [SERVER]
        self.v["npwp"].set(st.get("npwp", "")); self.v["email"].set(st.get("email", ""))
        self.v["kode_a"].set(st.get("kode_a", "000000")); self.v["kode_b"].set(st.get("kode_b", "000000"))
        self.v["kode_trx"].set(st.get("kode_trx", "04"))
        self.v["trx_txt"].set(ref_label(KODE_TRX, self.v["kode_trx"].get()))
        self.v["ket_txt"].set(st.get("ket_txt", "")); self.v["cap_txt"].set(st.get("cap_txt", ""))
        keep = ("npwp", "email", "kode_a", "kode_b", "kode_trx", "ket_txt", "cap_txt")
        for k in keep:
            self.v[k].trace_add("write", lambda *_: save_settings({x: self.v[x].get().strip() for x in keep}))
        self._style(); self._ui()

    # ------------------------------ tampilan ------------------------------
    def _style(self):
        st = ttk.Style(self); st.theme_use("clam")
        st.configure(".", font=(FONT, 10), background=BG, foreground=TXT)
        st.configure("Card.TFrame", background=CARD)
        st.configure("Card.TLabel", background=CARD, foreground=TXT)
        st.configure("Field.TLabel", background=CARD, foreground=LBL, font=(FONT, 10))
        st.configure("Hint.TLabel", background=CARD, foreground=MUT, font=(FONT, 9))
        st.configure("Sub.TLabel", background=CARD, foreground=PRI, font=(FONT, 9, "bold"))
        st.configure("Title.TLabel", background=CARD, foreground=TXT, font=(FONT, 12, "bold"))
        for name, bg, fg, bgh in (("Accent", PRI, "white", PRI_D), ("Soft", "#E6EEF8", PRI, "#D3E2F4")):
            st.configure(f"{name}.TButton", background=bg, foreground=fg, font=(FONT, 10, "bold"),
                         padding=(16, 8), borderwidth=0, focusthickness=0, focuscolor=bg)
            st.map(f"{name}.TButton", background=[("disabled", "#E5E7EB"), ("active", bgh)],
                   foreground=[("disabled", "#6B7280")])
        st.configure("Small.TButton", background="#E6EEF8", foreground=PRI, font=(FONT, 9, "bold"),
                     padding=(10, 5), borderwidth=0, focusthickness=0, focuscolor="#E6EEF8")
        st.map("Small.TButton", background=[("disabled", "#E5E7EB"), ("active", "#D3E2F4")],
               foreground=[("disabled", "#6B7280")])
        st.configure("Link.TButton", background=CARD, foreground=PRI, font=(FONT, 9, "underline"),
                     padding=(0, 2), borderwidth=0, focusthickness=0, focuscolor=CARD)
        st.map("Link.TButton", background=[("active", CARD)], foreground=[("active", PRI_D), ("disabled", MUT)])
        st.configure("TEntry", fieldbackground="white", padding=6, bordercolor="#D1D5DB", lightcolor="#D1D5DB", darkcolor="#D1D5DB")
        st.configure("TCombobox", fieldbackground="white", padding=6, bordercolor="#D1D5DB", lightcolor="#D1D5DB",
                     darkcolor="#D1D5DB", arrowsize=16)
        st.map("TEntry", fieldbackground=[("disabled", "#F3F4F6")], foreground=[("disabled", MUT)])
        st.map("TCombobox", fieldbackground=[("readonly", "white"), ("disabled", "#F3F4F6")], foreground=[("disabled", MUT)])
        st.configure("Treeview", rowheight=28, background="white", fieldbackground="white", borderwidth=0, font=(FONT, 10))
        st.configure("Treeview.Heading", background="#E9EEF5", foreground=TXT, font=(FONT, 10, "bold"), relief="flat", padding=(6, 7))
        st.map("Treeview", background=[("selected", "#CFE3F7")], foreground=[("selected", TXT)])
        st.map("Treeview.Heading", background=[("active", "#DCE5F0")])
        for sb in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            st.configure(sb, background="#C5D0DE", troughcolor="#EEF1F6", bordercolor="#EEF1F6", lightcolor="#C5D0DE",
                         darkcolor="#C5D0DE", arrowcolor=MUT, relief="flat", arrowsize=14)
            st.map(sb, background=[("active", "#A9B8CC")])
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", padding=(20, 8), font=(FONT, 10, "bold"), background="#E5EAF1", foreground=MUT, borderwidth=0)
        st.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", PRI)],
               padding=[("selected", (20, 8)), ("!selected", (20, 8))],
               expand=[("selected", (0, 0, 0, 0)), ("!selected", (0, 0, 0, 0))])
        st.configure("Horizontal.TProgressbar", background=PRI, troughcolor="#DDE3EC", borderwidth=0, thickness=6)

    def place(self, w, width, height):
        self.update_idletasks()
        x = self.winfo_x() + max(0, (self.winfo_width() - width) // 2); y = self.winfo_y() + 90
        w.geometry(f"{width}x{height}+{x}+{y}")

    def pill(self, lbl, text, kind):
        bg, fg = PILL[kind]; lbl.config(text=text, bg=bg, fg=fg)

    def status(self, text, kind=""):
        self.stat.config(text=text, fg={"bad": BAD_C, "ok": OK_C}.get(kind, LBL))

    def set_warn(self, text):
        self.warn.config(text=text)
        self.warn.grid() if text else self.warn.grid_remove()

    def field(self, parent, row, label, widget, hint=None, tip=None):
        lb = ttk.Label(parent, text=label, style="Field.TLabel")
        lb.grid(row=row, column=0, sticky="w", pady=3)
        widget.grid(row=row, column=1, sticky="ew", pady=3, padx=(10, 0))
        if hint: ttk.Label(parent, text=hint, style="Hint.TLabel").grid(row=row + 1, column=1, sticky="w", padx=(12, 0))
        if tip: Tip(lb, tip); Tip(widget, tip)
        return lb

    def step(self, parent, num, title):
        """Satu langkah di panel kiri: lencana nomor + garis penghubung + isi. Kembalikan frame isi."""
        wrap = tk.Frame(parent, bg=CARD); wrap.pack(fill="x", padx=(18, 20), pady=(16, 0))
        wrap.columnconfigure(1, weight=1); wrap.rowconfigure(2, weight=1)
        badge = tk.Label(wrap, text=str(num), width=2, font=(FONT, 10, "bold"), bd=0, pady=2)
        badge.grid(row=0, column=0, sticky="n", pady=(1, 0))
        tk.Label(wrap, text=title, bg=CARD, fg=TXT, font=(FONT, 12, "bold"), anchor="w").grid(row=0, column=1, sticky="w", padx=(12, 0))
        sub = tk.Label(wrap, text="", bg=CARD, fg=MUT, font=(FONT, 9), anchor="w", justify="left", wraplength=360)
        sub.grid(row=1, column=1, sticky="w", padx=(12, 0))
        rail = tk.Frame(wrap, bg=CARD, width=26); rail.grid(row=1, column=0, rowspan=2, sticky="ns")
        tk.Frame(rail, bg=LINE, width=2).place(relx=0.5, rely=0, relheight=1, y=6, anchor="n")
        body = ttk.Frame(wrap, style="Card.TFrame"); body.grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=(8, 2))
        body.columnconfigure(1, weight=1); body.columnconfigure(0, minsize=104)
        self.steps.append((badge, sub))
        return body

    def _ui(self):
        self.columnconfigure(1, weight=1); self.rowconfigure(1, weight=1)
        self.steps = []
        # --- header: logo + status koneksi ---
        h = tk.Frame(self, bg=HDR); h.grid(row=0, column=0, columnspan=2, sticky="ew"); h.columnconfigure(1, weight=1)
        self.logo_img = tk.PhotoImage(data="".join(LOGO_B64.split()))
        tk.Label(h, image=self.logo_img, bg=HDR, bd=0).grid(row=0, column=0, padx=(10, 10), pady=6)
        self.pill_conn = tk.Label(h, font=(FONT, 9, "bold"), padx=12, pady=5)
        self.pill_conn.grid(row=0, column=2, padx=18)
        self.pill(self.pill_conn, "● Belum login", "idle")

        # --- panel kiri (bisa digulir) ---
        side_out = tk.Frame(self, bg=CARD, width=SIDE_W); side_out.grid(row=1, column=0, sticky="ns")
        side_out.grid_propagate(False); side_out.rowconfigure(0, weight=1); side_out.columnconfigure(0, weight=1)
        side = ScrollFrame(side_out, bg=CARD); side.grid(row=0, column=0, sticky="nsew")
        tk.Frame(self, bg=LINE, width=1).grid(row=1, column=0, sticky="nse")
        s = side.inner

        a = self.step(s, 1, "Akun & database")
        srv = ttk.Frame(a, style="Card.TFrame"); srv.columnconfigure(0, weight=1)
        self.cb_srv = ttk.Combobox(srv, textvariable=self.v["server"], values=self.servers,
                                   postcommand=lambda: self.cb_srv.config(values=self.servers))
        self.cb_srv.grid(row=0, column=0, sticky="ew")
        self.btn_srv = ttk.Button(srv, text="Kelola", style="Small.TButton", command=self.server_dialog)
        self.btn_srv.grid(row=0, column=1, padx=(6, 0))
        self.e_email = ttk.Entry(a, textvariable=self.v["email"])
        self.e_pass = ttk.Entry(a, textvariable=self.v["password"], show="•")
        self.e_pass.bind("<Return>", lambda e: self.toggle())
        self.login_rows = []                                   # disembunyikan setelah login agar panel ringkas
        for i, (lbl, w, tip) in enumerate((
                ("Server", srv, "Alamat server Zahir. Klik Kelola untuk menambah server lain."),
                ("Email", self.e_email, "Email akun Zahir Online."),
                ("Password", self.e_pass, "Password tidak disimpan. Tekan Enter untuk login.")), start=0):
            self.login_rows += [self.field(a, i, lbl, w, tip=tip), w]
        self.btn_conn = ttk.Button(a, text="Login", style="Accent.TButton", command=self.toggle)
        self.btn_conn.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 10))
        self.cb_db = ttk.Combobox(a, textvariable=self.v["db"], state="disabled")
        self.cb_db.bind("<<ComboboxSelected>>", self.pick_db); self.cb_db.bind("<Return>", self.pick_db)
        wide_popdown(self.cb_db, 120)
        self.field(a, 4, "Database", self.cb_db, tip="Aktif setelah login. Pilih database (perusahaan) yang akan diproses.")
        reg = ttk.Frame(a, style="Card.TFrame"); reg.columnconfigure(0, weight=1)
        self.pill_lic = tk.Label(reg, font=(FONT, 9, "bold"), padx=10, pady=5, anchor="w", justify="left", wraplength=230)
        self.pill_lic.grid(row=0, column=0, sticky="ew")
        ttk.Button(reg, text="Registrasi...", style="Small.TButton", command=self.reg_dialog).grid(row=0, column=1, padx=(8, 0))
        self.field(a, 5, "Registrasi", reg)
        self.pill(self.pill_lic, "Belum ada database", "idle")

        b = self.step(s, 2, "Periode & filter")
        self.field(b, 0, "NPWP Penjual", ttk.Entry(b, textvariable=self.v["npwp"]), None,
                   "NPWP perusahaan Anda (penjual), 16 digit. ID TKU Penjual = NPWP + 000000.")
        per = ttk.Frame(b, style="Card.TFrame"); per.columnconfigure((0, 2), weight=1)
        ttk.Entry(per, textvariable=self.v["d1"], width=11).grid(row=0, column=0, sticky="ew")
        ttk.Label(per, text=" s/d ", style="Field.TLabel").grid(row=0, column=1)
        ttk.Entry(per, textvariable=self.v["d2"], width=11).grid(row=0, column=2, sticky="ew")
        self.field(b, 1, "Periode", per, None, "Rentang tanggal faktur, format YYYY-MM-DD (tahun-bulan-tanggal).")
        quick = ttk.Frame(b, style="Card.TFrame"); quick.grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(0, 4))
        for txt, off in (("Bulan ini", 0), ("Bulan lalu", -1)):
            ttk.Button(quick, text=txt, style="Link.TButton", command=lambda o=off: self.set_month(o)).pack(side="left", padx=(0, 10))
        cu = ttk.Frame(b, style="Card.TFrame"); cu.columnconfigure(0, weight=1)
        self.e_cust = ttk.Entry(cu, textvariable=self.v["cust"], state="readonly", cursor="hand2")
        self.e_cust.grid(row=0, column=0, sticky="ew"); self.e_cust.bind("<Button-1>", lambda e: self.cust_dialog())
        ttk.Button(cu, text="Pilih...", style="Small.TButton", command=self.cust_dialog).grid(row=0, column=1, padx=(6, 0))
        self.field(b, 3, "Customer", cu, None, "Pilih satu atau beberapa customer. Kosong = semua customer.")

        d = self.step(s, 3, "Isian faktur Coretax")
        self.cb_trx = ttk.Combobox(d, textvariable=self.v["trx_txt"], state="readonly", values=ref_labels(KODE_TRX))
        self.cb_trx.bind("<<ComboboxSelected>>", lambda e: self._trx_changed()); wide_popdown(self.cb_trx, 300)
        self.field(d, 0, "Kode Transaksi", self.cb_trx, None, "Dipakai bila kode transaksi di Zahir kosong / tidak tersedia.")
        self.cb_ket = ttk.Combobox(d, textvariable=self.v["ket_txt"], state="readonly"); wide_popdown(self.cb_ket, 480)
        self.field(d, 1, "Ket. Tambahan", self.cb_ket, None, "Hanya untuk kode transaksi 07 dan 08; daftar menyesuaikan kode yang dipilih.")
        self.cb_cap = ttk.Combobox(d, textvariable=self.v["cap_txt"], state="readonly"); wide_popdown(self.cb_cap, 480)
        self.field(d, 2, "Cap Fasilitas", self.cb_cap, None, "Hanya untuk kode transaksi 07 dan 08; daftar menyesuaikan kode yang dipilih.")
        kd = ttk.Frame(d, style="Card.TFrame"); kd.columnconfigure((0, 2), weight=1)
        for i, (var, lbl, tip) in enumerate((
                ("kode_a", "barang", "Kode Barang Coretax (6 digit) untuk item barang yang belum punya kode."),
                ("kode_b", "jasa", "Kode Jasa Coretax (6 digit) untuk item jasa yang belum punya kode."))):
            e = ttk.Entry(kd, textvariable=self.v[var], width=8); e.grid(row=0, column=i * 2, sticky="ew"); Tip(e, tip)
            ttk.Label(kd, text=f" {lbl}  ", style="Hint.TLabel").grid(row=0, column=i * 2 + 1, sticky="w")
        self.field(d, 3, "Kode default", kd, tip="Kode Barang/Jasa Coretax untuk item yang belum punya kode.")
        self.btn_ref = ttk.Button(d, text="Perbarui daftar dari template DJP...", style="Link.TButton", command=self.load_ref)
        self.btn_ref.grid(row=4, column=1, sticky="w", padx=(12, 0), pady=(2, 0))
        Tip(self.btn_ref, "Opsional: perbarui daftar Kode Transaksi, Keterangan Tambahan & Cap Fasilitas dari "
                          "template Faktur Coretax DJP (.xlsx) versi terbaru. Daftar bawaan sudah tersedia.")
        tk.Frame(s, bg=CARD, height=24).pack(fill="x")
        self._load_refs(); self._trx_changed()

        # --- area kanan: aksi, ringkasan, peringatan, tabel ---
        main = tk.Frame(self, bg=BG); main.grid(row=1, column=1, sticky="nsew", padx=(20, 20), pady=(16, 0))
        main.columnconfigure(0, weight=1); main.rowconfigure(3, weight=1)
        bar = tk.Frame(main, bg=BG); bar.grid(row=0, column=0, sticky="ew")
        self.acts = []
        for txt, mode, sty in (("▶  Preview", "preview", "Accent"), ("Export Excel", "xlsx", "Soft"), ("Export XML", "xml", "Soft")):
            btn = ttk.Button(bar, text=txt, style=f"{sty}.TButton", state="disabled", command=lambda m=mode: self.act(m))
            btn.pack(side="left", padx=(0, 8)); self.acts.append(btn)
        self.btn_diag = ttk.Button(bar, text="Tes akses database", style="Small.TButton", state="disabled", command=self.diag)
        self.btn_diag.pack(side="right")
        for btn, tip in zip(self.acts + [self.btn_diag], (
                "Tarik data faktur periode ini dan tampilkan di tabel.",
                "Simpan hasil ke Excel (2 sheet) untuk impor Coretax.",
                "Simpan hasil ke XML TaxInvoiceBulk untuk impor Coretax.",
                "Cek akses ke tabel-tabel Zahir yang dipakai.")):
            Tip(btn, tip)

        strip = tk.Frame(main, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        strip.grid(row=1, column=0, sticky="ew", pady=(14, 12))
        self.tile = {}
        for i, (key, title) in enumerate((("fak", "Faktur"), ("det", "Baris detail"), ("dpp", "Total DPP"), ("ppn", "Total PPN"))):
            strip.columnconfigure(i * 2, weight=1, uniform="t")
            if i: tk.Frame(strip, bg=LINE, width=1).grid(row=0, column=i * 2 - 1, sticky="ns", pady=12)
            cell = tk.Frame(strip, bg=CARD); cell.grid(row=0, column=i * 2, sticky="ew", padx=18, pady=(10, 12))
            tk.Label(cell, text=title, bg=CARD, fg=LBL, font=(FONT, 9)).pack(anchor="w")
            v = tk.Label(cell, text="–", bg=CARD, fg=TXT, font=(FONT, 16, "bold")); v.pack(anchor="w")
            self.tile[key] = v

        self.warn = tk.Label(main, bg="#FFF4D6", fg="#7A4B00", anchor="w", justify="left", padx=14, pady=8,
                             font=(FONT, 9), wraplength=860)
        self.warn.grid(row=2, column=0, sticky="ew", pady=(0, 12)); self.warn.grid_remove()

        self.nb = ttk.Notebook(main); self.nb.grid(row=3, column=0, sticky="nsew")
        self.trees = {}; self.empty = {}
        for name, cols in (("Faktur", FAKTUR_COLS), ("DetailFaktur", DETAIL_COLS)):
            g = ttk.Frame(self.nb); g.columnconfigure(0, weight=1); g.rowconfigure(0, weight=1)
            tv = ttk.Treeview(g, columns=cols, show="headings")
            for col in cols:
                w = 260 if col in ("Nama Barang Jasa", "Alamat Pembeli", "Nama Pembeli") else max(90, len(col) * 9 + 24)
                an = "e" if col in NUM_COLS else "w"
                tv.heading(col, text=col, anchor=an); tv.column(col, width=w, minwidth=70, stretch=False, anchor=an)
            tv.tag_configure("odd", background="#F6F8FB")
            ys = ttk.Scrollbar(g, command=tv.yview); xs = ttk.Scrollbar(g, orient="horizontal", command=tv.xview)
            tv.config(yscrollcommand=ys.set, xscrollcommand=xs.set)
            tv.grid(row=0, column=0, sticky="nsew"); ys.grid(row=0, column=1, sticky="ns"); xs.grid(row=1, column=0, sticky="ew")
            self.nb.add(g, text=name); self.trees[name] = (tv, cols)
            em = tk.Label(g, text=EMPTY_TXT, bg="white", fg=MUT, font=(FONT, 11), justify="center")
            em.place(relx=0.5, rely=0.5, anchor="center"); self.empty[name] = em

        # --- bilah status ---
        sb = tk.Frame(self, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        sb.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        self.stat = tk.Label(sb, text="Login dan pilih database untuk mulai", bg=CARD, fg=LBL, font=(FONT, 9), anchor="w")
        self.stat.pack(side="left", padx=14, pady=6)
        self.prog = ttk.Progressbar(sb, mode="indeterminate", length=120)
        for k in ("npwp", "d1", "d2", "trx_txt", "ket_txt", "cap_txt", "cust"):
            self.v[k].trace_add("write", lambda *_: self.update_steps())
        self.update_steps()

    def set_month(self, offset):
        t = dt.date.today().replace(day=1)
        if offset: t = (t - dt.timedelta(days=1)).replace(day=1)
        self.v["d1"].set(t.isoformat())
        self.v["d2"].set(t.replace(day=calendar.monthrange(t.year, t.month)[1]).isoformat())

    # ------------------------------ logika ------------------------------
    def cfg(self):
        v = {k: x.get().strip() for k, x in self.v.items()}
        proto, host = parse_server(self.v["server"].get())
        v.update(ket_tambahan=ref_code(v.get("ket_txt")), cap_fasilitas=ref_code(v.get("cap_txt")))
        v.update(cust_ids=[self.cust_map[n] for n in sorted(self.cust_sel) if n in self.cust_map], token=self.token, slug=self.slug, protocol=proto.upper(), server=host, url=f"{proto}://{host}/api/v2/zsql")
        return v

    def bg(self, fn, done):
        self._busy += 1; self.prog.pack(side="right", padx=14); self.prog.start(12)
        def fin(res, err):
            self._busy -= 1
            if not self._busy: self.prog.stop(); self.prog.pack_forget()
            done(res, err)
        def work():
            try: res, err = fn(), None
            except Exception as ex: res, err = None, f"{type(ex).__name__}: {ex}"
            self.after(0, lambda: fin(res, err))
        threading.Thread(target=work, daemon=True).start()

    def update_steps(self):
        """Lencana langkah di panel kiri: hijau = selesai, biru = langkah berikutnya, abu = belum."""
        if not getattr(self, "steps", None) or not hasattr(self, "cb_cap"): return
        v = {k: self.v[k].get().strip() for k in ("npwp", "d1", "d2", "cust")}
        code = ref_code(self.v["trx_txt"].get())
        ok_date = all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v[k]) for k in ("d1", "d2"))
        fas_ok = code not in KODE_FASILITAS or (ref_code(self.v["ket_txt"].get()) and ref_code(self.v["cap_txt"].get()))
        done = [bool(self.logged_in and self.db_ok and self.lic_exp),
                bool(re.fullmatch(r"\d{16}", re.sub(r"\D", "", v["npwp"])) and ok_date),
                bool(code and fas_ok)]
        who = getattr(self, "login_who", "")
        if not self.logged_in: s1 = "Masuk dengan akun Zahir"
        elif not self.db_ok: s1 = f"{who}\nPilih database yang akan diproses"
        elif not self.lic_exp: s1 = f"{who}\n{self.slug}: belum teregistrasi"
        else: s1 = f"{who}\n{self.slug}"
        s2 = (f"{v['d1']} s/d {v['d2']}, {v['cust'].lower() if v['cust'] == ALL_CUST else v['cust']}" if done[1]
              else "Isi NPWP penjual 16 digit dan periode")
        s3 = (f"Kode transaksi {code}" if done[2] else
              "Pilih Keterangan Tambahan dan Cap Fasilitas untuk kode 07/08" if code else "Pilih kode transaksi")
        cur = done.index(False) if False in done else -1
        for i, (badge, sub) in enumerate(self.steps):
            if done[i]: badge.config(text="\u2713", bg=OK_C, fg="white")
            elif i == cur: badge.config(text=str(i + 1), bg=PRI, fg="white")
            else: badge.config(text=str(i + 1), bg="#E5E7EB", fg=LBL)
            sub.config(text=(s1, s2, s3)[i], fg=OK_C if done[i] else MUT)

    def show(self, v, col):
        """Format tampilan saja (data ekspor tidak berubah): angka gaya Indonesia, rata kanan."""
        if v is None: return ""
        if col in NUM_COLS and isinstance(v, (int, float)):
            txt = f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
            return txt.replace(",", "X").replace(".", ",").replace("X", ".")
        return v

    def tiles(self, fak, det):
        def num(x):
            try: return float(x)
            except (TypeError, ValueError): return 0.0
        money = lambda x: "Rp " + f"{x:,.0f}".replace(",", ".")
        self.tile["fak"].config(text=str(len(fak))); self.tile["det"].config(text=str(len(det)))
        self.tile["dpp"].config(text=money(sum(num(r.get("DPP")) for r in det)))
        self.tile["ppn"].config(text=money(sum(num(r.get("PPN")) for r in det)))

    def set_actions(self, on):
        for b in self.acts: b.config(state="normal" if on else "disabled")

    def clear_view(self):
        for tv, _ in self.trees.values(): tv.delete(*tv.get_children())
        for i, name in enumerate(self.trees):
            self.nb.tab(i, text=name); self.empty[name].config(text=EMPTY_TXT); self.empty[name].place(relx=0.5, rely=0.5, anchor="center")
        for t in self.tile.values(): t.config(text="-")
        self.set_warn("")

    def reset(self):
        self._gen += 1
        self.token = self.slug = ""; self.logged_in = False; self.db_map = {}; self.lic_exp = None
        self.v["db"].set(""); self.cb_db.config(values=[], state="disabled")
        for w in (self.cb_srv, self.btn_srv, self.e_email, self.e_pass): w.config(state="normal")
        for w in self.login_rows: w.grid()
        self.btn_conn.config(text="Login"); self.set_actions(False); self.btn_diag.config(state="disabled")
        self.pill(self.pill_conn, "\u25CF Belum login", "idle"); self.pill(self.pill_lic, "Belum ada database", "idle")
        self.db_ok = False; self.clear_view(); self.status("Login dan pilih database untuk mulai"); self.update_steps()

    def toggle(self):
        if self.logged_in:
            self.reset(); return
        email, pw = self.v["email"].get().strip(), self.v["password"].get()
        if not email or not pw:
            messagebox.showwarning("Login", "Email dan Password wajib diisi"); return
        proto, host = parse_server(self.v["server"].get())
        client = load_settings().get("clients", {}).get(host, CLIENT_B64)   # client per-domain bila berbeda
        self.status(f"Login ke {host}..."); self.pill(self.pill_conn, "\u25CF Login...", "busy")
        def work():
            tok, me = login(email, pw, f"{proto}://{host}", client)
            dbs, note = list_companies({"token": tok, "protocol": proto, "server": host}, me)
            return tok, dbs, note
        def done(res, err):
            if err:
                self.status("Login gagal", "bad"); self.pill(self.pill_conn, "\u25CF Login gagal", "bad")
                messagebox.showerror("Login gagal", err); return
            self.token, dbs, note = res
            self.db_map = {f"{n}  |  {sl}": sl for n, sl in dbs}
            self.logged_in = True; self.v["password"].set("")
            entry = host if proto == "https" else f"http://{host}"
            if entry not in self.servers: self.servers.append(entry)
            self.v["server"].set(entry)
            self.cb_srv.config(values=self.servers); save_settings({"server": entry, "servers": self.servers})
            for w in (self.cb_srv, self.btn_srv, self.e_email, self.e_pass): w.config(state="disabled")
            for w in self.login_rows: w.grid_remove()
            self.login_who = f"{email} di {host}"
            self.cb_db.config(state="normal", values=list(self.db_map)); self.cb_db.focus_set()
            self.btn_conn.config(text="Logout")
            self.pill(self.pill_conn, "\u25CF Pilih database", "busy")
            if dbs:
                self.status(f"Login berhasil - {len(dbs)} database, pilih salah satu"); self.update_steps()
            else:
                self.status("Login berhasil - ketik slug database lalu Enter"); self.update_steps()
                messagebox.showinfo("Daftar database", "Login berhasil, tetapi daftar database tidak bisa diambil dari server ini.\n\n"
                    "Ketik slug database di kolom Database (mis. namapt.domainserver.com) lalu tekan Enter.\n\n"
                    "Detail: " + note)
        self.bg(work, done)

    def pick_db(self, _=None):
        """Boleh dipilih ulang kapan saja (tanpa logout): ganti database = koneksi & preview dimulai dari awal."""
        txt = self.v["db"].get().strip()
        slug = self.db_map.get(txt)
        if not slug:                                                  # slug diketik manual (server tanpa endpoint daftar database)
            m = re.fullmatch(r"(?:https?://)?([\w.-]+?)/?", txt, flags=re.I)
            slug = m.group(1).lower() if m else ""
            if not slug: return
            if slug not in self.db_map.values():
                self.db_map[slug] = slug; self.cb_db.config(values=list(self.db_map))
            self.v["db"].set(slug)
        self._gen += 1; gen = self._gen                               # abaikan hasil tes koneksi yang sudah usang
        self.slug = slug; self.lic_exp = None; self.db_ok = False; self.update_steps(); self.set_actions(False); self.btn_diag.config(state="disabled"); self.clear_view()
        self.pill(self.pill_lic, "Menunggu koneksi...", "idle"); self.pill(self.pill_conn, "\u25CF Menghubungkan...", "busy")
        f = self.cfg(); self.status(f"Menghubungkan ke {slug}...")
        def done(_, err):
            self.cb_db.config(state="normal")                          # dropdown tetap bisa diganti / diketik
            if gen != self._gen: return
            if err:
                self.status("Gagal terhubung", "bad"); self.pill(self.pill_conn, "\u25CF Gagal terhubung", "bad")
                self.pill(self.pill_lic, "-", "idle"); messagebox.showerror("Koneksi gagal", friendly(err)); return
            self.pill(self.pill_conn, "\u25CF Terhubung", "ok"); self.btn_diag.config(state="normal"); self.db_ok = True; self.update_steps()
            self.status(f"Terhubung: {slug}", "ok"); self.check_license(slug, gen); self.load_customers(f, gen)
        self.cb_db.selection_clear(); self.focus_set()
        self.bg(lambda: run("SELECT 1 AS ok", f), done)

    # ------------------------------ referensi ------------------------------
    def _load_refs(self):
        refs = load_settings().get("refs", {})
        tup = lambda k: [tuple(x) for x in refs.get(k) or []]
        self.ref = {"trx": tup("trx") or KODE_TRX,
                    "ket": {k: tup(f"ket{k}") or KET_TAMBAHAN[k] for k in KODE_FASILITAS},
                    "cap": {k: tup(f"cap{k}") or CAP_FASILITAS[k] for k in KODE_FASILITAS}}
        self.cb_trx.config(values=ref_labels(self.ref["trx"]))
        self.v["trx_txt"].set(ref_label(self.ref["trx"], self.v["kode_trx"].get()))

    def _trx_changed(self):
        code = ref_code(self.v["trx_txt"].get())
        if code: self.v["kode_trx"].set(code)
        on = code in KODE_FASILITAS
        for key, cb, var in (("ket", self.cb_ket, "ket_txt"), ("cap", self.cb_cap, "cap_txt")):
            items = self.ref[key].get(code, []) if on else []
            cb.config(values=[NONE_LABEL, *ref_labels(items)], state="readonly" if on else "disabled")
            cur = ref_code(self.v[var].get())                     # pilihan lama tetap bila kodenya ada di daftar baru
            self.v[var].set(ref_label(items, cur) if on and any(c == cur for c, _ in items) else (NONE_LABEL if on else ""))

    def load_ref(self):
        path = filedialog.askopenfilename(title="Pilih template Faktur Coretax DJP (.xlsx)",
                                          filetypes=[("Excel", "*.xlsx *.xlsm"), ("Semua file", "*.*")])
        if not path: return
        try:
            got = parse_ref_xlsx(path)
        except Exception as ex:
            messagebox.showerror("Muat referensi", f"File tidak bisa dibaca:\n{ex}"); return
        if not got:
            messagebox.showwarning("Muat referensi", "Tidak menemukan tabel 'Kode Transaksi', 'Keterangan Tambahan Kode "
                                   "Faktur 07/08' atau 'Cap Fasilitas Kode Faktur 07/08' di file ini."); return
        refs = load_settings().get("refs", {}); refs.update({k: [list(x) for x in v] for k, v in got.items()})
        save_settings({"refs": refs}); self._load_refs(); self._trx_changed()
        names = {"trx": "Kode Transaksi", "ket07": "Keterangan Tambahan 07", "ket08": "Keterangan Tambahan 08",
                 "cap07": "Cap Fasilitas 07", "cap08": "Cap Fasilitas 08"}
        messagebox.showinfo("Muat referensi", "Referensi diperbarui:\n" +
                            "\n".join(f"• {names[k]}: {len(v)} item" for k, v in got.items()))

    # ------------------------------ customer (multi pilih) ------------------------------
    def load_customers(self, f, gen):
        """Ambil daftar customer database terpilih; pilihan direset ke semua customer."""
        self.cust_map = {}; self.cust_sel = set(); self._cust_summary()
        def done(rows, err):
            if gen != self._gen or err: return
            m = {}
            for r in rows or []:
                n = str(r.get("nama") or "").strip()
                if n and n not in m: m[n] = r.get("id")
            self.cust_map = m
        self.bg(lambda: run(Q_CUSTOMERS, f), done)

    def _cust_summary(self):
        n = len(self.cust_sel)
        self.v["cust"].set(ALL_CUST if not n else next(iter(self.cust_sel)) if n == 1 else f"{n} customer dipilih")

    def cust_dialog(self):
        if not self.cust_map:
            messagebox.showinfo("Customer", "Daftar customer belum tersedia. Login dan pilih database dulu "
                                "(daftar dimuat otomatis setelah terhubung)."); return
        sel = set(self.cust_sel); names = sorted(self.cust_map, key=str.lower); shown = []
        w = tk.Toplevel(self); w.title("Pilih Customer"); w.configure(bg=BG); self.place(w, 560, 560)
        w.transient(self); w.grab_set()
        hd = tk.Frame(w, bg=HDR); hd.pack(fill="x")
        tk.Label(hd, text="Pilih Customer", bg=HDR, fg="white", font=(FONT, 15, "bold"), padx=20, pady=12).pack(anchor="w")
        body = ttk.Frame(w, style="Card.TFrame", padding=16); body.pack(fill="both", expand=True, padx=14, pady=14)
        q = tk.StringVar()
        top = ttk.Frame(body, style="Card.TFrame"); top.pack(fill="x")
        ttk.Label(top, text="Cari", style="Field.TLabel").pack(side="left")
        es = ttk.Entry(top, textvariable=q); es.pack(side="left", fill="x", expand=True, padx=(10, 0)); es.focus_set()
        fr = ttk.Frame(body, style="Card.TFrame"); fr.pack(fill="both", expand=True, pady=(10, 6))
        lb = tk.Listbox(fr, selectmode="multiple", activestyle="none", font=(FONT, 10), relief="flat",
                        exportselection=False, highlightthickness=1, highlightbackground="#D1D5DB",
                        selectbackground="#CFE3F7", selectforeground=TXT)
        ys = ttk.Scrollbar(fr, command=lb.yview); lb.config(yscrollcommand=ys.set)
        lb.pack(side="left", fill="both", expand=True); ys.pack(side="right", fill="y")
        info = tk.Label(body, bg=CARD, fg=MUT, font=(FONT, 9), anchor="w"); info.pack(fill="x")
        mark = lambda n: ("☑  " if n in sel else "☐  ") + n

        def count():
            info.config(text=(f"{len(sel)} dipilih" if sel else "Belum ada yang dipilih = semua customer")
                        + f"   •   {len(shown)} dari {len(names)} ditampilkan")

        def refresh(*_):
            t = q.get().strip().lower(); shown[:] = [n for n in names if t in n.lower()]
            lb.delete(0, "end")
            for i, n in enumerate(shown):
                lb.insert("end", mark(n))
                if n in sel: lb.selection_set(i)
            count()

        def toggled(_=None):
            cur = set(lb.curselection())
            for i, n in enumerate(shown):
                before = n in sel
                (sel.add if i in cur else sel.discard)(n)
                if before != (n in sel):                          # perbarui tanda centang baris yang berubah
                    top_i = lb.nearest(0); lb.delete(i); lb.insert(i, mark(n))
                    if n in sel: lb.selection_set(i)
                    lb.yview(top_i)
            count()

        def all_shown(): sel.update(shown); refresh()
        def clear(): sel.clear(); refresh()
        def apply():
            self.cust_sel = set(sel); self._cust_summary(); w.destroy()

        q.trace_add("write", refresh); lb.bind("<<ListboxSelect>>", toggled)
        btn = ttk.Frame(body, style="Card.TFrame"); btn.pack(fill="x", pady=(8, 0))
        ttk.Button(btn, text="Pilih semua yang tampil", style="Small.TButton", command=all_shown).pack(side="left")
        ttk.Button(btn, text="Kosongkan", style="Small.TButton", command=clear).pack(side="left", padx=(6, 0))
        ttk.Button(btn, text="Terapkan", style="Accent.TButton", command=apply).pack(side="right")
        ttk.Button(btn, text="Batal", style="Soft.TButton", command=w.destroy).pack(side="right", padx=(0, 6))
        w.bind("<Return>", lambda e: apply()); w.bind("<Escape>", lambda e: w.destroy())
        refresh()

    # ------------------------------ kelola server ------------------------------
    def server_dialog(self):
        """Tambah / ubah / hapus server Zahir Online, plus client (client_id:client_secret) khusus per server."""
        w = tk.Toplevel(self); w.title("Kelola Server"); w.configure(bg=BG); self.place(w, 660, 500); w.transient(self); w.grab_set()
        hd = tk.Frame(w, bg=HDR); hd.pack(fill="x")
        tk.Label(hd, text="Kelola Server", bg=HDR, fg="white", font=(FONT, 15, "bold"), padx=20, pady=14).pack(anchor="w")
        body = ttk.Frame(w, style="Card.TFrame", padding=18); body.pack(fill="both", expand=True, padx=14, pady=14)
        body.columnconfigure(1, weight=1)
        lb = tk.Listbox(body, height=6, font=(FONT, 10), relief="flat", highlightthickness=1, highlightbackground="#D1D5DB",
                        activestyle="none", selectbackground="#CFE3F7", selectforeground=TXT, exportselection=False)
        lb.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        host_v, cli_v = tk.StringVar(), tk.StringVar()
        self.field(body, 1, "Server", ttk.Entry(body, textvariable=host_v))
        self.field(body, 2, "Client", ttk.Entry(body, textvariable=cli_v, show="\u2022"))
        tk.Label(body, bg=CARD, fg=MUT, font=(FONT, 9), justify="left", anchor="w", wraplength=600,
                 text="Server: mis. erp.perusahaan.com, https://zahir.domain.id, atau http://192.168.1.10:8080\n"
                      "Client (opsional): client_id:client_secret (atau versi base64-nya) bila server memakai aplikasi "
                      "OAuth berbeda. Kosongkan untuk memakai client bawaan.").grid(row=3, column=1, sticky="w")
        msg = tk.Label(body, text="", bg=CARD, fg=MUT, anchor="w", justify="left", wraplength=600, font=(FONT, 9))
        msg.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 8))
        clients = lambda: load_settings().get("clients", {})

        def refresh(sel=None):
            cl = clients(); lb.delete(0, "end")
            for s in self.servers:
                tags = ("   \u2605 default" if s == self.servers[0] else "") + ("   [client khusus]" if parse_server(s)[1] in cl else "")
                lb.insert("end", s + tags)
            if sel in self.servers:
                i = self.servers.index(sel); lb.selection_set(i); lb.see(i)
            self.cb_srv.config(values=self.servers)

        def selected():
            i = lb.curselection()
            return self.servers[i[0]] if i else None

        def on_sel(_=None):
            s = selected()
            if s: host_v.set(s); cli_v.set(clients().get(parse_server(s)[1], ""))

        def persist():
            save_settings({"servers": self.servers, "server": self.v["server"].get().strip()})

        def save():
            raw = host_v.get().strip()
            proto, host = parse_server(raw)
            if not raw or not re.fullmatch(r"[\w.-]+(:\d{1,5})?", host):
                msg.config(text="Alamat server tidak valid.", fg=BAD_C); return
            c = cli_v.get().strip()
            if c and ":" in c:
                c = base64.b64encode(c.encode()).decode()
            elif c:
                try: ok = ":" in base64.b64decode(c, validate=True).decode()
                except Exception: ok = False
                if not ok: msg.config(text="Client harus berbentuk client_id:client_secret atau base64-nya.", fg=BAD_C); return
            entry = host if proto == "https" else f"http://{host}"
            old = selected()
            if old and old != entry and parse_server(old)[1] == host:      # ubah protokol server yang sama
                self.servers[self.servers.index(old)] = entry
            elif entry not in self.servers:
                self.servers.append(entry)
            cl = clients()
            if c: cl[host] = c
            else: cl.pop(host, None)
            save_settings({"clients": cl}); persist(); refresh(entry)
            msg.config(text=f"Tersimpan: {entry}", fg=OK_C)

        def delete():
            s = selected()
            if not s: msg.config(text="Pilih server di daftar dulu.", fg=BAD_C); return
            if len(self.servers) == 1: msg.config(text="Minimal harus ada satu server.", fg=BAD_C); return
            if not messagebox.askyesno("Hapus server", f"Hapus {s} dari daftar?", parent=w): return
            self.servers.remove(s)
            cl = clients(); cl.pop(parse_server(s)[1], None); save_settings({"clients": cl})
            if self.v["server"].get().strip() == s: self.v["server"].set(self.servers[0])
            persist(); refresh(); host_v.set(""); cli_v.set(""); msg.config(text=f"Dihapus: {s}", fg=MUT)

        def make_default():
            s = selected()
            if not s: msg.config(text="Pilih server di daftar dulu.", fg=BAD_C); return
            self.servers.remove(s); self.servers.insert(0, s); persist(); refresh(s)
            msg.config(text=f"{s} jadi server default (paling atas).", fg=OK_C)

        def use():
            s = selected() or host_v.get().strip()
            if s: self.v["server"].set(s); persist()
            w.destroy()

        lb.bind("<<ListboxSelect>>", on_sel); lb.bind("<Double-Button-1>", lambda e: use())
        btns = ttk.Frame(body, style="Card.TFrame"); btns.grid(row=5, column=0, columnspan=2, sticky="ew")
        ttk.Button(btns, text="Simpan", style="Soft.TButton", command=save).pack(side="left")
        ttk.Button(btns, text="Hapus", style="Soft.TButton", command=delete).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Jadikan Default", style="Soft.TButton", command=make_default).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Pakai Server Ini", style="Accent.TButton", command=use).pack(side="right")
        refresh(self.v["server"].get().strip()); on_sel()

    # ------------------------------ registrasi ------------------------------
    def check_license(self, slug, gen):
        code = load_settings().get("licenses", {}).get(slug, "")
        self.pill(self.pill_lic, "Memeriksa registrasi...", "busy")
        def done(res, err):
            if gen != self._gen: return
            ok, msg, exp = res if not err else (False, err, None)
            self.lic_exp = exp if ok else None
            kind = "bad" if not ok else ("warn" if (exp - dt.date.today()).days <= 14 else "ok")
            self.pill(self.pill_lic, ("\u2713 " if ok else "\u2717 ") + msg, kind)
            self.set_actions(ok); self.update_steps()
            self.status(f"Terhubung: {slug}" + ("" if ok else "  \u2022  belum teregistrasi"), "ok" if ok else "bad")
            if not ok and not code and msg == "belum teregistrasi": self.after(250, self.reg_dialog)
        self.bg(lambda: license_state(slug, code), done)

    def reg_dialog(self):
        if not self.slug:
            messagebox.showinfo("Registrasi", "Login dan pilih database dulu."); return
        slug = self.slug
        w = tk.Toplevel(self); w.title("Registrasi database"); w.configure(bg=BG); self.place(w, 680, 450); w.transient(self)
        hd = tk.Frame(w, bg=HDR); hd.pack(fill="x")
        tk.Label(hd, text="Registrasi Database", bg=HDR, fg="white", font=(FONT, 15, "bold"), padx=20, pady=14).pack(anchor="w")
        body = ttk.Frame(w, style="Card.TFrame", padding=20); body.pack(fill="both", expand=True, padx=14, pady=14)
        msg = tk.Label(body, text="", bg=CARD, fg=MUT, anchor="w", justify="left", wraplength=600, font=(FONT, 9))
        ttk.Label(body, text="1.  Kirim slug database ini ke admin", style="Title.TLabel").pack(anchor="w")
        row = ttk.Frame(body, style="Card.TFrame"); row.pack(fill="x", pady=(8, 18))
        e = ttk.Entry(row); e.insert(0, slug); e.config(state="readonly"); e.pack(side="left", fill="x", expand=True)
        def copy():
            self.clipboard_clear(); self.clipboard_append(slug); msg.config(text="Slug disalin ke clipboard.", fg=OK_C)
        ttk.Button(row, text="Salin", style="Soft.TButton", command=copy).pack(side="left", padx=(8, 0))
        ttk.Label(body, text="2.  Tempel kode registrasi dari admin", style="Title.TLabel").pack(anchor="w")
        t = tk.Text(body, height=6, wrap="word", font=("Consolas", 10), relief="flat", bd=0, padx=8, pady=6,
                    highlightthickness=1, highlightbackground="#D1D5DB", highlightcolor=PRI)
        t.pack(fill="x", pady=(8, 4)); t.insert("1.0", load_settings().get("licenses", {}).get(slug, ""))
        msg.pack(fill="x", pady=(2, 10))
        btns = ttk.Frame(body, style="Card.TFrame"); btns.pack(fill="x")
        def paste():
            try: t.delete("1.0", "end"); t.insert("1.0", self.clipboard_get().strip())
            except tk.TclError: msg.config(text="Clipboard kosong.", fg=BAD_C)
        ok_btn = ttk.Button(btns, text="Simpan & Aktifkan", style="Accent.TButton")
        def save():
            code = t.get("1.0", "end").strip()
            ok_btn.config(state="disabled"); msg.config(text="Memeriksa...", fg=MUT)
            def done(res, err):
                if not w.winfo_exists(): return
                ok_btn.config(state="normal")
                ok, text, _ = res if not err else (False, err, None)
                if ok:
                    lic = load_settings().get("licenses", {}); lic[slug] = code; save_settings({"licenses": lic})
                    w.destroy(); self.check_license(slug, self._gen)
                else:
                    msg.config(text="Registrasi belum berhasil: " + text, fg=BAD_C)
            self.bg(lambda: license_state(slug, code), done)
        ok_btn.config(command=save); ok_btn.pack(side="right")
        ttk.Button(btns, text="Tempel dari clipboard", style="Soft.TButton", command=paste).pack(side="left")

    # ------------------------------ tes akses ------------------------------
    def diag(self):
        f = self.cfg(); self.status("Menguji akses ke tabel...")
        def done(res, err):
            self.status("Tes akses selesai")
            if err:
                messagebox.showerror("Tes Akses", err); return
            w = tk.Toplevel(self); w.title("Tes Akses"); w.configure(bg=BG); self.place(w, 700, 470); w.transient(self)
            hd = tk.Frame(w, bg=HDR); hd.pack(fill="x")
            tk.Label(hd, text="Tes Akses Database", bg=HDR, fg="white", font=(FONT, 15, "bold"), padx=20, pady=14).pack(anchor="w")
            body = ttk.Frame(w, style="Card.TFrame", padding=18); body.pack(fill="both", expand=True, padx=14, pady=14)
            tx = tk.Text(body, height=11, font=("Consolas", 10), relief="flat", bg=CARD, wrap="word")
            tx.tag_config("ok", foreground=OK_C); tx.tag_config("bad", foreground=BAD_C)
            for name, ok, detail in res:
                tx.insert("end", ("\u2713  " if ok else "\u2717  ") + name + ("" if ok else f"   {detail}") + "\n", "ok" if ok else "bad")
            tx.config(state="disabled"); tx.pack(fill="both", expand=True)
            bad = [n for n, ok, _ in res if not ok]
            if not bad: text, col = "Semua tabel bisa dibaca. Jika Preview masih gagal, kirim pesan errornya ke admin.", OK_C
            elif len(bad) == len(res):
                text, col = ("Semua query ditolak: akun ini tidak punya izin zsql di database ini (pembatasan di sisi server Zahir). "
                             "Coba login dengan akun yang punya izin."), BAD_C
            else: text, col = "Tabel yang ditolak: " + ", ".join(bad) + ". Minta izin akses tabel itu untuk akun ini.", BAD_C
            tk.Label(body, text=text, bg=CARD, fg=col, wraplength=620, justify="left", font=(FONT, 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.bg(lambda: diagnose(f), done)

    # ------------------------------ preview / export ------------------------------
    def act(self, mode):
        if not self.lic_exp or dt.date.today() > self.lic_exp:
            messagebox.showwarning("Registrasi", "Database ini belum teregistrasi atau sudah kedaluwarsa."); return
        f = self.cfg(); path = None
        if mode != "preview":
            if not re.fullmatch(r"\d{16}", re.sub(r"\D", "", f["npwp"])):
                messagebox.showwarning("NPWP", "Isi NPWP Penjual 16 digit"); return
            ext = ".xlsx" if mode == "xlsx" else ".xml"
            path = filedialog.asksaveasfilename(defaultextension=ext, initialfile="Faktur_Keluaran_Coretax" + ext,
                                                filetypes=[(ext.upper(), "*" + ext)])
            if not path: return
        self.status("Menarik data...")
        def done(res, err):
            if err:
                self.status("Gagal", "bad"); messagebox.showerror("Error", friendly(err)); return
            fak, det = res
            for i, (name, data) in enumerate((("Faktur", fak), ("DetailFaktur", det))):
                tv, cols = self.trees[name]
                tv.delete(*tv.get_children())
                for n, r in enumerate(data):
                    tv.insert("", "end", tags=("odd",) if n % 2 else (), values=[self.show(r.get(c), c) for c in cols])
                self.nb.tab(i, text=f"{name} ({len(data)})")
                if data: self.empty[name].place_forget()
                else: self.empty[name].config(text="Tidak ada data pada periode ini"); self.empty[name].place(relx=0.5, rely=0.5, anchor="center")
            self.tiles(fak, det)
            self.set_warn("\n".join("\u26A0  " + x for x in validate(fak, det)))
            self.status(f"{len(fak)} faktur, {len(det)} baris detail", "ok")
            if path:
                buf = build_xlsx(fak, det, f["npwp"]) if mode == "xlsx" else build_xml(fak, det, f["npwp"])
                with open(path, "wb") as fh: fh.write(buf.getvalue())
                messagebox.showinfo("Selesai", f"Tersimpan:\n{path}")
        self.bg(lambda: fetch(f), done)


if __name__ == "__main__":
    App().mainloop()
