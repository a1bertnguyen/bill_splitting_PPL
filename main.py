"""
SplitLang Desktop GUI — Bill-Splitting Domain-Specific Language
Built with Python Tkinter + ANTLR 4.9.2 + SQLite.

Features:
  - Interactive DSL Console & Multi-line Script Editor
  - Quick Demo Chips (for live 15-minute PPL presentation)
  - Live Balances & Optimal Minimum-Transfer Settlement Dashboard
  - Expense & Itemized Bill History Table
  - Live PPL Inspector Tab (Stage 2 Lexer Tokens, Stage 3 Parse Tree, Stage 4 AST)
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from controller.Response import SplitLangInterpreter


# Color Palette (Modern Slate Dark Theme)
BG_MAIN = "#0F172A"
BG_PANEL = "#1E293B"
BG_CARD = "#263349"
BG_INPUT = "#0B1220"
FG_TEXT = "#F1F5F9"
FG_MUTED = "#94A3B8"
ACCENT = "#6366F1"
ACCENT_HOVER = "#4F46E5"
GREEN = "#10B981"
RED = "#F43F5E"
CYAN = "#38BDF8"
AMBER = "#F59E0B"
BORDER = "#334155"

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"


class SplitLangApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SplitLang — Bill-Splitting Custom DSL (ANTLR 4.9.2)")
        self.geometry("1320x820")
        self.minsize(1080, 680)
        self.configure(bg=BG_MAIN)

        self.interpreter = SplitLangInterpreter()
        self._configure_styles()
        self._build_layout()
        self._print_welcome()
        self._refresh_dashboard()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=BG_MAIN)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("Card.TFrame", background=BG_CARD)

        style.configure("TNotebook", background=BG_MAIN, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=BG_PANEL,
            foreground=FG_MUTED,
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#FFFFFF")],
        )

        style.configure(
            "Treeview",
            background=BG_INPUT,
            foreground=FG_TEXT,
            fieldbackground=BG_INPUT,
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=BG_CARD,
            foreground=CYAN,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", ACCENT)])

    # ------------------------------------------------------------------
    # Layout Construction
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        # Header Bar
        header = tk.Frame(self, bg=BG_PANEL, height=62, padx=18, pady=10)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        title_box = tk.Frame(header, bg=BG_PANEL)
        title_box.pack(side=tk.LEFT)
        tk.Label(
            title_box,
            text="SplitLang",
            bg=BG_PANEL,
            fg="#FFFFFF",
            font=("Segoe UI", 16, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            title_box,
            text="  Bill-Splitting DSL  |  ANTLR 4.9.2 Five-Stage Interpreter",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, pady=(4, 0))

        # Right side of header: Active Group Badge + Action Buttons
        controls = tk.Frame(header, bg=BG_PANEL)
        controls.pack(side=tk.RIGHT)

        self.group_badge = tk.Label(
            controls,
            text="Group: Default (VND)",
            bg=BG_CARD,
            fg=CYAN,
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=5,
        )
        self.group_badge.pack(side=tk.LEFT, padx=(0, 10))

        self._make_button(controls, "Run Demo Script", self._run_demo_script, bg=GREEN).pack(
            side=tk.LEFT, padx=4
        )
        self._make_button(controls, "Open .split File", self._load_script_file, bg=BG_CARD).pack(
            side=tk.LEFT, padx=4
        )
        self._make_button(controls, "Help", lambda: self._execute_text("help"), bg=BG_CARD).pack(
            side=tk.LEFT, padx=4
        )
        self._make_button(controls, "Reset", self._confirm_reset, bg="#991B1B").pack(
            side=tk.LEFT, padx=(4, 0)
        )

        # Main Paned Window (Left: Console & Input, Right: Live Dashboard & PPL Inspector)
        body = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=BG_MAIN,
            sashwidth=6,
            sashrelief=tk.FLAT,
            bd=0,
        )
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        left_pane = tk.Frame(body, bg=BG_PANEL, bd=1, relief=tk.FLAT)
        right_pane = tk.Frame(body, bg=BG_MAIN, bd=0)
        body.add(left_pane, minsize=460, width=590)
        body.add(right_pane, minsize=520)

        self._build_left_console(left_pane)
        self._build_right_tabs(right_pane)

    def _make_button(
        self, parent: tk.Widget, text: str, command, bg: str = ACCENT, fg: str = "#FFFFFF"
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=ACCENT_HOVER,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            padx=11,
            pady=5,
            cursor="hand2",
            bd=0,
        )

    def _build_left_console(self, parent: tk.Frame) -> None:
        # Output Header
        top_bar = tk.Frame(parent, bg=BG_CARD, padx=12, pady=8)
        top_bar.pack(fill=tk.X)
        tk.Label(
            top_bar,
            text="DSL Console & Transcript",
            bg=BG_CARD,
            fg=FG_TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT)
        tk.Button(
            top_bar,
            text="Clear Log",
            command=self._clear_log,
            bg=BG_PANEL,
            fg=FG_MUTED,
            relief=tk.FLAT,
            font=("Segoe UI", 8),
            padx=8,
            pady=2,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        # Output Log Text Widget
        log_frame = tk.Frame(parent, bg=BG_INPUT)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 6))

        self.log_text = tk.Text(
            log_frame,
            bg=BG_INPUT,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            font=("Consolas", 10),
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=10,
            pady=10,
            state=tk.DISABLED,
        )
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.log_text.tag_configure("user", foreground=CYAN, font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("ok", foreground="#A7F3D0")
        self.log_text.tag_configure("err", foreground="#FDA4AF")
        self.log_text.tag_configure("info", foreground=FG_MUTED)
        self.log_text.tag_configure("banner", foreground="#C7D2FE", font=("Consolas", 10, "bold"))

        # Quick Sample Command Chips
        chips_bar = tk.Frame(parent, bg=BG_PANEL, padx=10, pady=4)
        chips_bar.pack(fill=tk.X)
        tk.Label(
            chips_bar,
            text="Quick insert:",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 6))

        quick_samples = [
            ("+ Members", "add members alice, bob, charlie, dave"),
            ("Equal", "alice paid 300k for dinner split equally"),
            ("Ratio+Tax", "bob paid 120k + 30k * 2 for hotpot split ratio alice: 2, bob: 1, charlie: 1 with tax 10%"),
            (
                "Itemized Bill",
                'bill "BBQ Night" paid by alice {\n'
                '    item "Wagyu Beef" 450k for all\n'
                '    item "Beer Tower" 200k for alice, bob\n'
                '    item "Matcha Tea" 60k for charlie\n'
                "    tax 10%\n"
                "    tip 5%\n"
                "}",
            ),
            ("Settle Up", "settle up"),
            ("Invalid Input", "hello splitlang"),
        ]
        for label, snippet in quick_samples:
            btn = tk.Button(
                chips_bar,
                text=label,
                command=lambda s=snippet: self._set_input_text(s),
                bg=BG_CARD,
                fg=FG_TEXT,
                activebackground=ACCENT,
                activeforeground="#FFFFFF",
                relief=tk.FLAT,
                font=("Segoe UI", 8),
                padx=7,
                pady=3,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=2)

        # Input Editor Box (supports single command & multi-line bill blocks)
        input_wrap = tk.Frame(parent, bg=BG_PANEL, padx=10, pady=(4, 10))
        input_wrap.pack(fill=tk.X)

        tk.Label(
            input_wrap,
            text="Enter SplitLang command or script  (Ctrl+Enter to run, Enter for newline):",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor=tk.W, pady=(0, 4))

        editor_row = tk.Frame(input_wrap, bg=BG_PANEL)
        editor_row.pack(fill=tk.X)

        self.input_text = tk.Text(
            editor_row,
            height=5,
            bg=BG_INPUT,
            fg="#FFFFFF",
            insertbackground=CYAN,
            font=("Consolas", 10),
            relief=tk.FLAT,
            padx=10,
            pady=8,
            wrap=tk.WORD,
        )
        self.input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.input_text.bind("<Control-Return>", lambda e: self._on_run_clicked())

        run_col = tk.Frame(editor_row, bg=BG_PANEL)
        run_col.pack(side=tk.RIGHT, fill=tk.Y)
        self._make_button(run_col, "Run DSL\n(Ctrl+Enter)", self._on_run_clicked, bg=ACCENT).pack(
            fill=tk.BOTH, expand=True
        )

    def _build_right_tabs(self, parent: tk.Frame) -> None:
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Balances & Settlements
        tab_bal = tk.Frame(self.notebook, bg=BG_MAIN, padx=8, pady=8)
        self.notebook.add(tab_bal, text="  Balances & Settle Up  ")
        self._build_balances_tab(tab_bal)

        # Tab 2: Expenses & Bills
        tab_exp = tk.Frame(self.notebook, bg=BG_MAIN, padx=8, pady=8)
        self.notebook.add(tab_exp, text="  Expenses & Bills  ")
        self._build_expenses_tab(tab_exp)

        # Tab 3: PPL Inspector (Tokens / Parse Tree / AST)
        tab_ppl = tk.Frame(self.notebook, bg=BG_MAIN, padx=8, pady=8)
        self.notebook.add(tab_ppl, text="  PPL Inspector (Tokens / Tree / AST)  ")
        self._build_ppl_inspector_tab(tab_ppl)

    def _build_balances_tab(self, parent: tk.Frame) -> None:
        # Summary KPI Cards
        cards_row = tk.Frame(parent, bg=BG_MAIN)
        cards_row.pack(fill=tk.X, pady=(0, 10))
        self.kpi_labels: dict[str, tk.Label] = {}
        for key, title, color in [
            ("total_spent", "TOTAL SPENT", CYAN),
            ("members", "MEMBERS", "#A78BFA"),
            ("expenses", "EXPENSES / BILLS", AMBER),
            ("transfers", "MIN TRANSFERS", GREEN),
        ]:
            card = tk.Frame(cards_row, bg=BG_PANEL, padx=12, pady=10)
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            tk.Label(card, text=title, bg=BG_PANEL, fg=FG_MUTED, font=("Segoe UI", 8, "bold")).pack(
                anchor=tk.W
            )
            lbl = tk.Label(card, text="0", bg=BG_PANEL, fg=color, font=("Segoe UI", 13, "bold"))
            lbl.pack(anchor=tk.W, pady=(4, 0))
            self.kpi_labels[key] = lbl

        # Member Balances Table
        tk.Label(
            parent,
            text="Member Balances",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(4, 4))

        bal_frame = tk.Frame(parent, bg=BG_PANEL)
        bal_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.bal_tree = ttk.Treeview(
            bal_frame,
            columns=("member", "paid", "owed", "net"),
            show="headings",
            height=7,
        )
        for col, heading, w, anchor in [
            ("member", "Member", 130, tk.W),
            ("paid", "Total Paid", 130, tk.E),
            ("owed", "Total Share", 130, tk.E),
            ("net", "Net Balance", 150, tk.E),
        ]:
            self.bal_tree.heading(col, text=heading)
            self.bal_tree.column(col, width=w, anchor=anchor)
        self.bal_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Optimal Settlement Plan
        tk.Label(
            parent,
            text="Optimal Settlement Plan (Greedy Minimum Cash Flow Algorithm)",
            bg=BG_MAIN,
            fg=GREEN,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(4, 4))

        settle_frame = tk.Frame(parent, bg=BG_PANEL)
        settle_frame.pack(fill=tk.BOTH, expand=True)

        self.settle_tree = ttk.Treeview(
            settle_frame,
            columns=("from", "arrow", "to", "amount"),
            show="headings",
            height=6,
        )
        self.settle_tree.heading("from", text="Debtor (Pays)")
        self.settle_tree.heading("arrow", text="")
        self.settle_tree.heading("to", text="Creditor (Receives)")
        self.settle_tree.heading("amount", text="Transfer Amount")
        self.settle_tree.column("from", width=150, anchor=tk.W)
        self.settle_tree.column("arrow", width=40, anchor=tk.CENTER)
        self.settle_tree.column("to", width=150, anchor=tk.W)
        self.settle_tree.column("amount", width=160, anchor=tk.E)
        self.settle_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _build_expenses_tab(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="Recorded Expenses & Itemized Bills (Newest First)",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 6))

        wrap = tk.Frame(parent, bg=BG_PANEL)
        wrap.pack(fill=tk.BOTH, expand=True)

        self.exp_tree = ttk.Treeview(
            wrap,
            columns=("id", "date", "payer", "desc", "mode", "total", "shares"),
            show="headings",
        )
        for col, heading, w, anchor in [
            ("id", "#", 36, tk.CENTER),
            ("date", "Date", 88, tk.CENTER),
            ("payer", "Payer", 80, tk.W),
            ("desc", "Description", 120, tk.W),
            ("mode", "Mode", 78, tk.CENTER),
            ("total", "Total", 105, tk.E),
            ("shares", "Per-Member Shares", 240, tk.W),
        ]:
            self.exp_tree.heading(col, text=heading)
            self.exp_tree.column(col, width=w, anchor=anchor)

        exp_scroll = ttk.Scrollbar(wrap, command=self.exp_tree.yview)
        self.exp_tree.configure(yscrollcommand=exp_scroll.set)
        exp_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.exp_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _build_ppl_inspector_tab(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="Live ANTLR 4.9.2 Pipeline Inspector — Last Executed Command",
            bg=BG_MAIN,
            fg=CYAN,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 6))

        paned = tk.PanedWindow(parent, orient=tk.VERTICAL, bg=BG_MAIN, sashwidth=6, bd=0)
        paned.pack(fill=tk.BOTH, expand=True)

        self.tokens_box = self._make_inspector_section(
            paned, "Stage 2 · Lexical Analysis (SplitLangLexer Tokens)", height=6
        )
        self.tree_box = self._make_inspector_section(
            paned, "Stage 3 · Syntax Analysis (SplitLangParser Concrete Parse Tree)", height=10
        )
        self.ast_box = self._make_inspector_section(
            paned, "Stage 4 · Visitor & AST Generation (Distilled Op Nodes)", height=8
        )

    def _make_inspector_section(self, paned: tk.PanedWindow, title: str, height: int) -> tk.Text:
        frame = tk.Frame(paned, bg=BG_PANEL)
        tk.Label(
            frame,
            text=title,
            bg=BG_CARD,
            fg=FG_TEXT,
            font=("Segoe UI", 9, "bold"),
            anchor=tk.W,
            padx=10,
            pady=5,
        ).pack(fill=tk.X)

        txt = tk.Text(
            frame,
            height=height,
            bg=BG_INPUT,
            fg="#E2E8F0",
            font=("Consolas", 9),
            relief=tk.FLAT,
            padx=8,
            pady=6,
            wrap=tk.NONE,
            state=tk.DISABLED,
        )
        y_scroll = ttk.Scrollbar(frame, command=txt.yview)
        x_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=txt.xview)
        txt.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        paned.add(frame, minsize=100)
        return txt

    # ------------------------------------------------------------------
    # Actions & Event Handlers
    # ------------------------------------------------------------------

    def _print_welcome(self) -> None:
        self._append_log(
            "Welcome to SplitLang — A Custom DSL for Deterministic Bill Splitting!\n", "banner"
        )
        self._append_log(
            "Type commands below (Ctrl+Enter to run), click 'Run Demo Script', or type 'help'.\n"
            "Switch to the 'PPL Inspector' tab anytime to view Lexer Tokens, Parse Tree, and AST!\n\n",
            "info",
        )

    def _append_log(self, text: str, tag: str = "ok") -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text, tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_readonly_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        widget.configure(state=tk.DISABLED)

    def _set_input_text(self, text: str) -> None:
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", text)
        self.input_text.focus_set()

    def _clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _on_run_clicked(self) -> str:
        raw = self.input_text.get("1.0", tk.END).strip()
        if raw:
            self._execute_text(raw)
            self.input_text.delete("1.0", tk.END)
        return "break"

    def _execute_text(self, source: str) -> None:
        self._append_log(f">>> {source}\n", "user")
        res = self.interpreter.execute(source)

        # Check clear UI control op
        if any(op.get("result", {}).get("clear_ui") for op in res["ops"]):
            self._clear_log()
            return

        tag = "ok" if res["ok"] else "err"
        for msg in res["messages"]:
            self._append_log(f"{msg}\n", tag)
        self._append_log("\n", "info")

        self._update_ppl_inspector(res)
        self._refresh_dashboard()

    def _update_ppl_inspector(self, res: dict) -> None:
        tok_lines = [
            f"{i:02d}. {t['type']:<14} <- {t['text']!r}   (line {t['line']}, col {t['column']})"
            for i, t in enumerate(res["tokens"], 1)
        ]
        self._set_readonly_text(
            self.tokens_box, "\n".join(tok_lines) if tok_lines else "(no tokens)"
        )
        self._set_readonly_text(self.tree_box, res["parse_tree"] or "(no parse tree)")
        self._set_readonly_text(self.ast_box, res["ast_tree"] or "(no AST)")

    def _refresh_dashboard(self) -> None:
        state = self.interpreter.get_dashboard_state()
        grp = state["group"]
        self.group_badge.configure(text=f"Group: {grp['name']} ({state['currency']})")

        self.kpi_labels["total_spent"].configure(text=state["total_spent"])
        self.kpi_labels["members"].configure(text=str(len(state["members"])))
        self.kpi_labels["expenses"].configure(text=str(state["expense_count"]))
        self.kpi_labels["transfers"].configure(text=str(len(state["transfers"])))

        # Balances table
        for item in self.bal_tree.get_children():
            self.bal_tree.delete(item)
        for b in state["balances"]:
            self.bal_tree.insert("", tk.END, values=(b["member"], b["paid"], b["owed"], b["net"]))

        # Settlements table
        for item in self.settle_tree.get_children():
            self.settle_tree.delete(item)
        if not state["transfers"]:
            self.settle_tree.insert("", tk.END, values=("All settled up!", "", "", ""))
        else:
            for tr in state["transfers"]:
                self.settle_tree.insert(
                    "", tk.END, values=(tr["from"], "->", tr["to"], tr["formatted"])
                )

        # Expenses table
        for item in self.exp_tree.get_children():
            self.exp_tree.delete(item)
        for e in state["expenses"]:
            self.exp_tree.insert(
                "",
                tk.END,
                values=(
                    e["id"],
                    e["date"],
                    e["payer"],
                    e["description"],
                    e["mode"],
                    e["total"],
                    e["shares_text"],
                ),
            )

    def _run_demo_script(self) -> None:
        demo_file = EXAMPLES_DIR / "dinner_demo.split"
        if not demo_file.exists():
            messagebox.showwarning("Demo Not Found", f"Could not find {demo_file}")
            return
        script = demo_file.read_text(encoding="utf-8")
        self._execute_text(script)

    def _load_script_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open SplitLang Script",
            initialdir=str(EXAMPLES_DIR) if EXAMPLES_DIR.exists() else ".",
            filetypes=[("SplitLang Scripts", "*.split"), ("All Files", "*.*")],
        )
        if path:
            content = Path(path).read_text(encoding="utf-8")
            self._set_input_text(content)

    def _confirm_reset(self) -> None:
        if messagebox.askyesno(
            "Reset Active Group",
            "Clear all members, expenses, and settlements in the current group?",
        ):
            self._execute_text("reset")

    def _on_close(self) -> None:
        self.interpreter.close()
        self.destroy()


def main() -> None:
    app = SplitLangApp()
    app.mainloop()


if __name__ == "__main__":
    main()
