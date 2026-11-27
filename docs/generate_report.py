"""
Generates:
  1. docs/architecture_diagram.png — Clean 5-Stage PPL Pipeline visual diagram
  2. docs/SplitLang_Report_Template.docx — Submission-ready <=5-page Word report
     covering all 7 required sections from the PPL Final Project Guidelines.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

DOCS_DIR = Path(__file__).resolve().parent
DIAGRAM_PATH = DOCS_DIR / "architecture_diagram.png"
DOCX_PATH = DOCS_DIR / "SplitLang_Report_Template.docx"


def _load_font(size: int, bold: bool = False):
    candidates = (
        ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def generate_architecture_diagram() -> None:
    W, H = 1600, 620
    img = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    f_title = _load_font(30, bold=True)
    f_sub = _load_font(18, bold=False)
    f_box_title = _load_font(20, bold=True)
    f_box_body = _load_font(16, bold=False)
    f_small = _load_font(15, bold=False)

    # Header
    draw.text((40, 24), "SplitLang — Five-Stage PPL Interpreter & Execution Pipeline", fill="#1E3A5F", font=f_title)
    draw.text(
        (40, 66),
        'Example Input:  bob paid 120k + 30k * 2 for "Hotpot" split ratio alice: 2, bob: 1 with tax 10%',
        fill="#475569",
        font=f_sub,
    )

    stages = [
        (
            "1. Input",
            "#9D174D",
            "User DSL Command\nor .split Script",
            "frontend/ (Web FE)\ncli.py (REPL)",
            "Hand-written",
        ),
        (
            "2. Lexer",
            "#5B21B6",
            "Splits text into\nlabeled tokens\n(ID, PAID, MONEY_K...)",
            "SplitLangLexer.py\n(ANTLR 4.9.2)",
            "Generated",
        ),
        (
            "3. Parser",
            "#5B21B6",
            "Validates CFG rules,\nprecedence & recursion;\nbuilds Parse Tree",
            "SplitLangParser.py\n+ ErrorListener",
            "Generated",
        ),
        (
            "4. Visitor & AST",
            "#9D174D",
            "Walks Parse Tree,\ndrops sugar, builds\nExpenseOp / BillOp",
            "ASTGeneration.py\nASTutils.py",
            "Hand-written",
        ),
        (
            "5. Action & DB",
            "#0F766E",
            "Semantic checks,\nDecimal rounding,\nMin Cash Flow + SQLite",
            "utilFunction.py\nDatabase.py",
            "Hand-written",
        ),
    ]

    box_w, box_h = 264, 300
    gap = 46
    start_x = 42
    top_y = 128

    for idx, (title, color, body, file_lbl, origin) in enumerate(stages):
        x0 = start_x + idx * (box_w + gap)
        y0 = top_y
        x1 = x0 + box_w
        y1 = y0 + box_h

        # Outer card
        draw.rounded_rectangle([x0, y0, x1, y1], radius=16, fill="#F8FAFC", outline=color, width=3)
        # Header band
        draw.rounded_rectangle([x0, y0, x1, y0 + 56], radius=14, fill=color)
        draw.rectangle([x0, y0 + 36, x1, y0 + 56], fill=color)
        draw.text((x0 + 18, y0 + 15), title, fill="#FFFFFF", font=f_box_title)

        # Body text
        draw.multiline_text((x0 + 18, y0 + 74), body, fill="#1E293B", font=f_box_body, spacing=6)

        # Divider & File label
        draw.line([(x0 + 16, y1 - 86), (x1 - 16, y1 - 86)], fill="#CBD5E1", width=2)
        draw.multiline_text((x0 + 18, y1 - 74), file_lbl, fill="#334155", font=f_small, spacing=4)

        # Origin badge below card
        badge_bg = "#EDE9FE" if origin == "Generated" else "#FCE7F3"
        badge_fg = "#5B21B6" if origin == "Generated" else "#9D174D"
        if title.startswith("5."):
            badge_bg, badge_fg = "#CCFBF1", "#0F766E"
        draw.rounded_rectangle([x0 + 38, y1 + 16, x1 - 38, y1 + 48], radius=12, fill=badge_bg)
        draw.text((x0 + 76, y1 + 22), origin, fill=badge_fg, font=f_small)

        # Arrow to next stage
        if idx < len(stages) - 1:
            ax0 = x1 + 6
            ax1 = x1 + gap - 6
            ay = y0 + box_h // 2
            draw.line([(ax0, ay), (ax1 - 10, ay)], fill="#475569", width=4)
            draw.polygon([(ax1, ay), (ax1 - 14, ay - 9), (ax1 - 14, ay + 9)], fill="#475569")

    # Error Rejection Path banner at bottom
    err_y0 = 510
    draw.rounded_rectangle([42, err_y0, W - 42, 588], radius=12, fill="#FFF1F2", outline="#E11D48", width=2)
    draw.text(
        (64, err_y0 + 14),
        "Safety & Validation Paths:",
        fill="#BE123C",
        font=_load_font(17, bold=True),
    )
    draw.text(
        (290, err_y0 + 14),
        "• Syntax Errors (Stage 2/3): Caught by SplitLangErrorListener -> rejected immediately; nothing modifies DB.",
        fill="#881337",
        font=f_small,
    )
    draw.text(
        (290, err_y0 + 42),
        "• Semantic Errors (Stage 5): Unknown member, percent != 100%, exact sum mismatch, or div-by-zero -> cleanly reported.",
        fill="#881337",
        font=f_small,
    )

    img.save(DIAGRAM_PATH)
    print(f"Saved architecture diagram: {DIAGRAM_PATH}")


def _set_cell_shading(cell, fill_hex: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill_hex)
    tcPr.append(shd)


def _add_heading(doc: Document, text: str, level: int = 1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10 if level == 1 else 6)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(13 if level == 1 else 11)
    run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F) if level == 1 else RGBColor(0x9D, 0x17, 0x4D)
    return p


def _add_body(doc: Document, text: str, bold_prefix: str = ""):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.12
    if bold_prefix:
        rb = p.add_run(bold_prefix)
        rb.bold = True
        rb.font.name = "Calibri"
        rb.font.size = Pt(10)
    r = p.add_run(text)
    r.font.name = "Calibri"
    r.font.size = Pt(10)
    return p


def _style_table(table, headers: list[str], rows: list[list[str]], col_widths: list[float]):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for j, h in enumerate(headers):
        cell = table.rows[0].cells[j]
        cell.width = Inches(col_widths[j])
        _set_cell_shading(cell, "1E3A5F")
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for i, row_data in enumerate(rows, start=1):
        bg = "F8FAFC" if i % 2 == 1 else "FFFFFF"
        for j, val in enumerate(row_data):
            cell = table.rows[i].cells[j]
            cell.width = Inches(col_widths[j])
            _set_cell_shading(cell, bg)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(9.2)


def generate_docx_report() -> None:
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.65)
        section.bottom_margin = Inches(0.65)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Title Banner
    p_univ = doc.add_paragraph()
    p_univ.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_univ.paragraph_format.space_after = Pt(2)
    r_u = p_univ.add_run("VNU-HCM INTERNATIONAL UNIVERSITY · SCHOOL OF COMPUTER SCIENCE AND ENGINEERING")
    r_u.bold = True
    r_u.font.name = "Calibri"
    r_u.font.size = Pt(9.5)
    r_u.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_after = Pt(2)
    r_t = p_title.add_run("SplitLang: A Domain-Specific Language for Deterministic Bill Splitting")
    r_t.bold = True
    r_t.font.name = "Calibri"
    r_t.font.size = Pt(16)
    r_t.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(8)
    r_s = p_sub.add_run("Principles of Programming Languages (Fall 2026) — Final Project Report  |  Team ID: [Replace with TeamID]")
    r_s.italic = True
    r_s.font.name = "Calibri"
    r_s.font.size = Pt(10)
    r_s.font.color.rgb = RGBColor(0x9D, 0x17, 0x4D)

    # Section 1 & 2 & 3
    _add_heading(doc, "1. Project Information, Team Members & Contributions")
    _add_body(doc, "SplitLang — A Custom Domain-Specific Language (DSL) for Deterministic Bill Splitting", bold_prefix="Project Name: ")

    member_rows = [
        ["1", "[Member 1 Full Name]", "[ITITIU...]", "Grammar Design (SplitLang.g4), ANTLR 4.9.2 generation, Lexer/Parser tests"],
        ["2", "[Member 2 Full Name]", "[ITITIU...]", "Visitor & AST Generation (ASTGeneration.py, ASTutils.py), Semantic validation"],
        ["3", "[Member 3 Full Name]", "[ITITIU...]", "Decimal Split Engine, Largest-Remainder rounding, Min-Cash-Flow & SQLite DB"],
        ["4", "[Member 4 Full Name]", "[ITITIU...]", "FastAPI Backend & Web Frontend (api/, frontend/) with Live PPL Inspector, CLI & Report"],
    ]
    tbl1 = doc.add_table(rows=1 + len(member_rows), cols=4)
    _style_table(tbl1, ["#", "Full Name", "Student ID", "Member Contributions"], member_rows, [0.4, 1.8, 1.2, 3.6])

    # Section 4: Problem Statement
    _add_heading(doc, "2. Problem Statement & System Description")
    _add_body(
        doc,
        "Group expense splitting (shared meals, travel itineraries, apartment bills) involves nuanced calculations: "
        "equal splits with exclusions, exact allocations, percentage and weighted ratio splits, itemized bills where "
        "participants share different dishes, proportional distribution of tax/tip/discounts, and minimizing final "
        "repayment transfers. Manual spreadsheets are tedious, whereas general-purpose LLMs are non-deterministic—they "
        "frequently miscalculate arithmetic, lose currency units to rounding drift, and confidently accept invalid inputs "
        "(e.g., percentages summing to 95%)."
    )
    _add_body(
        doc,
        "SplitLang addresses these challenges with a concise, human-readable Domain-Specific Language built on ANTLR 4.9.2. "
        "Users enter single interactive commands or multi-line .split scripts (including block-structured itemized bills). "
        "Every input is deterministically lexed, parsed, validated, computed with base-10 Decimal math, persisted locally in "
        "SQLite, and displayed in a Desktop GUI featuring a live PPL Inspector showing Tokens, Parse Tree, and AST."
    )

    # Section 5: Architecture Figure
    _add_heading(doc, "3. System Framework & Workflow Architecture")
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(4)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.add_run().add_picture(str(DIAGRAM_PATH), width=Inches(6.9))

    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_after = Pt(6)
    rc = p_cap.add_run("Figure 1: Five-stage SplitLang PPL Interpreter Pipeline (ANTLR 4.9.2 + Visitor + Deterministic Financial Engine).")
    rc.italic = True
    rc.font.name = "Calibri"
    rc.font.size = Pt(9)
    rc.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    # Section 6: Techniques per Component
    _add_heading(doc, "4. Techniques Used for Each Component")
    tech_rows = [
        ["Grammar & Generator", "parserAnalyzer/SplitLang.g4, run.py", "ANTLR 4.9.2 LL(*) parser generator (-Dlanguage=Python3 -visitor -no-listener) producing SplitLangLexer, SplitLangParser, and SplitLangVisitor."],
        ["Controller & Error Handling", "controller/Response.py", "Custom SplitLangErrorListener intercepts lexer/parser errors with exact line/column locations and halts execution before any state changes."],
        ["AST & Visitor", "module/ASTGeneration.py, ASTutils.py", "Visitor Pattern subclassing SplitLangVisitor; strips syntactic sugar and builds typed Command Ops (ExpenseOp, BillOp, SettleOp, QueryOp, etc.)."],
        ["Financial Engine", "module/utilFunction.py", "Base-10 Decimal arithmetic (zero float error), Largest-Remainder (Hamilton) rounding so sum(shares) == total, and Greedy Minimum Cash Flow (<= N-1 transfers)."],
        ["Persistence", "module/Database.py", "Zero-setup embedded SQLite (groups, members, expenses, expense_shares, settlements, action_log) supporting offline usage and undo/reset."],
        ["Web FE & CLI", "api/server.py, frontend/, cli.py", "FastAPI REST API + responsive HTML/CSS/JS Web Frontend with live Balances/Expenses dashboard + 5-Stage PPL Inspector, plus CLI REPL & .split runner."],
    ]
    tbl2 = doc.add_table(rows=1 + len(tech_rows), cols=3)
    _style_table(tbl2, ["Component", "Files", "Core Technique"], tech_rows, [1.4, 1.8, 3.8])

    # Section 7: PPL Concepts Applied
    _add_heading(doc, "5. Applying Principles of Programming Languages (PPL) Concepts")
    ppl_points = [
        (
            "Lexical Analysis & Token Prioritization: ",
            "Keywords (PAID, SPLIT, BILL, TAX, CURRENCY_CODE) are declared before the fallback identifier ID so maximal-munch "
            "matching prioritizes reserved words. Case-insensitive letter fragments (fragment A: [aA];) allow natural casing "
            "(PAID/paid/Paid) while preserving original casing in STRING and ID tokens. Domain literals—MONEY_K (300k), "
            "MONEY_M (1.5m), MONEY_USD ($25.50), PERCENT_LIT (10%), and DATE—are tokenized directly, while comments (//, #) "
            "and spaces are skipped.",
        ),
        (
            "Context-Free Grammar & Multi-Line Statement Separation: ",
            "SplitLang.g4 defines 7 statement categories. Retaining NEWLINE in stmtSep : (SEMI | NEWLINE)+ prevents unquoted "
            "multi-word descriptions (e.g., 'for bun bo hue') from greedily consuming the next line's identifier, enabling "
            "clean semicolon-free scripts as well as semicolon-separated one-liners.",
        ),
        (
            "Recursion in Grammar & Visitor: ",
            "Arbitrary-length member lists and allocation lists use classic CFG right-recursion (personList : person COMMA "
            "personList | person;). In ASTGeneration.py, visitPersonList() recursively traverses the parse tree to gather "
            "all participants cleanly.",
        ),
        (
            "Arithmetic Expression Precedence & Associativity: ",
            "Amounts accept full expressions (e.g., 'alice paid 120k + 30k * 4' or '(100k + 50k) * 2') via ordered left-recursive "
            "alternatives (# MulDivExpr above # AddSubExpr, plus # ParenExpr), enforcing * and / tighter than + and -.",
        ),
        (
            "Block-Structured DSL Syntax: ",
            "Itemized bills use scoped brace blocks: bill \"BBQ Night\" paid by alice { item \"Beef\" 450k for all; item \"Tea\" "
            "60k for charlie; tax 10%; tip 5% }. The Visitor constructs a hierarchical BillOp node so tax, tip, and discount "
            "are distributed proportionally to each diner's item subtotal.",
        ),
        (
            "Separation of Syntax and Semantics: ",
            "ANTLR enforces grammar validity, while Stage 5 enforces semantic constraints impossible in pure CFGs: member "
            "existence in the active group, percentage totals equal to 100%, exact split totals matching expense amounts, "
            "non-negative modifiers, and division-by-zero prevention.",
        ),
    ]
    for prefix, body in ppl_points:
        _add_body(doc, body, bold_prefix="• " + prefix)

    # Sample Code Box + Verification Summary
    _add_heading(doc, "6. Example SplitLang Session & Verification")
    p_code = doc.add_paragraph()
    p_code.paragraph_format.left_indent = Inches(0.25)
    p_code.paragraph_format.space_after = Pt(4)
    rc_code = p_code.add_run(
        'group "Saigon Weekend"; currency VND; add members alice, bob, charlie, dave\n'
        'alice paid 120k + 30k * 4 for "Grab & Parking" split equally\n'
        'bob paid 180k for "Specialty Coffee" excluding dave\n'
        'bill "BBQ Night" paid by bob { item "Wagyu Beef" 480k for all; item "Beer" 240k for alice, bob, dave; tax 10%; tip 5% }\n'
        "show balances; settle up"
    )
    rc_code.font.name = "Consolas"
    rc_code.font.size = Pt(8.5)
    rc_code.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    _add_body(
        doc,
        "An automated pytest suite (tests/test_lexer_parser.py, tests/test_ast_visitor.py, tests/test_domain_logic.py) "
        "verifies all valid grammar constructs, syntax error rejections, arithmetic precedence, AST generation, "
        "Largest-Remainder rounding across VND and USD, semantic validation, and Greedy Minimum Cash Flow settlement."
    )

    doc.save(DOCX_PATH)
    print(f"Saved Word report template: {DOCX_PATH}")


if __name__ == "__main__":
    generate_architecture_diagram()
    generate_docx_report()
