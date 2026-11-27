/**
 * Rendering helpers for SplitLang Web Frontend:
 *   - Console Transcript
 *   - Balances & Optimal Settlements (with one-click Mark Paid)
 *   - Expenses & Itemized Bills
 *   - Live 5-Stage PPL Pipeline Inspector (Tokens, Parse Tree, AST)
 */

const NUM_TYPES = new Set(["NUMBER", "MONEY_K", "MONEY_M", "MONEY_USD", "PERCENT_LIT", "DATE"]);
const OP_TYPES = new Set(["PLUS", "MINUS", "STAR", "SLASH"]);
const PUNCT_TYPES = new Set(["LPAREN", "RPAREN", "LBRACE", "RBRACE", "COMMA", "COLON", "SEMI", "QUESTIONMARK", "NEWLINE"]);

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function tokenCategoryClass(type) {
  if (type === "ID") return "tok-id";
  if (type === "STRING") return "tok-str";
  if (NUM_TYPES.has(type)) return "tok-num";
  if (OP_TYPES.has(type)) return "tok-op";
  if (PUNCT_TYPES.has(type)) return "tok-punct";
  return "tok-kw";
}

export function appendConsoleBanner(logEl) {
  const div = document.createElement("div");
  div.className = "log-entry log-banner";
  div.innerHTML =
    "<strong>Welcome to SplitLang!</strong> — A Custom DSL for Deterministic Bill Splitting.<br/>" +
    "Type commands below (<kbd>Ctrl+Enter</kbd>), click <strong>Run Demo</strong>, or inspect the <strong>PPL Inspector</strong> tab to view Lexer Tokens, Parse Tree, and AST live.";
  logEl.appendChild(div);
}

export function appendConsoleCommand(logEl, code) {
  const div = document.createElement("div");
  div.className = "log-entry log-cmd";
  div.textContent = `>>> ${code}`;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

export function appendConsoleExecution(logEl, execution) {
  if (!execution.messages || execution.messages.length === 0) return;

  const div = document.createElement("div");
  div.className = `log-entry ${execution.ok ? "log-ok" : "log-err"}`;

  if (!execution.ok) {
    const label =
      execution.stage_failed === "lexer_parser"
        ? "Stage 2/3 · Lexer / Parser Rejected"
        : "Stage 5 · Semantic Validation Error";
    const badge = document.createElement("div");
    badge.className = "err-badge";
    badge.textContent = label;
    div.appendChild(badge);
  }

  const body = document.createElement("div");
  body.textContent = execution.messages.join("\n");
  div.appendChild(body);
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

export function renderDashboard(state, { onMarkPaid }) {
  // Header group selector & currency
  const groupSelect = document.getElementById("groupSelect");
  groupSelect.innerHTML = "";
  for (const g of state.groups || []) {
    const opt = document.createElement("option");
    opt.value = g.name;
    opt.textContent = `${g.name} (${g.member_count})`;
    if (g.id === state.group.id) opt.selected = true;
    groupSelect.appendChild(opt);
  }
  document.getElementById("currencyBadge").textContent = state.currency;

  // KPI cards & badge
  document.getElementById("kpiTotalSpent").textContent = state.total_spent;
  document.getElementById("kpiMembers").textContent = String(state.members.length);
  document.getElementById("kpiExpenses").textContent = String(state.expense_count);
  document.getElementById("kpiTransfers").textContent = String(state.transfers.length);
  document.getElementById("expenseCountBadge").textContent = String(state.expense_count);

  // Member Balances table
  const balBody = document.getElementById("balancesBody");
  if (!state.balances.length) {
    balBody.innerHTML = `<tr><td colspan="4" class="empty-muted">No members yet. Try: <code>add members alice, bob, charlie</code></td></tr>`;
  } else {
    balBody.innerHTML = state.balances
      .map((b) => {
        const cls = b.net_raw > 0 ? "net-pos" : b.net_raw < 0 ? "net-neg" : "net-zero";
        const initial = escapeHtml(b.member.slice(0, 2));
        return `
          <tr>
            <td>
              <div class="member-cell">
                <span class="avatar">${initial}</span>
                <span>${escapeHtml(b.member)}</span>
              </div>
            </td>
            <td class="num">${escapeHtml(b.paid)}</td>
            <td class="num">${escapeHtml(b.owed)}</td>
            <td class="num"><span class="net-pill ${cls}">${escapeHtml(b.net)}</span></td>
          </tr>`;
      })
      .join("");
  }

  // Optimal Settlements
  const transfersEl = document.getElementById("transfersList");
  if (!state.transfers.length) {
    transfersEl.innerHTML = `<div class="empty-muted">All settled up! No transfers needed.</div>`;
  } else {
    transfersEl.innerHTML = "";
    for (const tr of state.transfers) {
      const card = document.createElement("div");
      card.className = "transfer-card";
      card.innerHTML = `
        <div class="transfer-flow">
          <span>${escapeHtml(tr.from)}</span>
          <span class="transfer-arrow">&rarr;</span>
          <span>${escapeHtml(tr.to)}</span>
        </div>
        <div class="transfer-right">
          <span class="transfer-amount">${escapeHtml(tr.formatted)}</span>
          <button class="mark-paid-btn" title="Execute '${escapeHtml(tr.from)} pays ${escapeHtml(tr.to)} ${escapeHtml(tr.amount)}'">
            Mark Paid
          </button>
        </div>`;
      card.querySelector(".mark-paid-btn").addEventListener("click", () => {
        onMarkPaid(tr.from, tr.to, tr.amount);
      });
      transfersEl.appendChild(card);
    }
  }

  // Expenses & Itemized Bills
  const expEl = document.getElementById("expensesList");
  if (!state.expenses.length) {
    expEl.innerHTML = `<div class="empty-muted">No expenses recorded in this group yet.</div>`;
  } else {
    expEl.innerHTML = state.expenses
      .map((e) => {
        const isItemized = e.kind === "bill";
        const modTags = [
          e.discount ? `<span class="mod-tag">Discount -${escapeHtml(e.discount)}</span>` : "",
          e.tax ? `<span class="mod-tag">Tax +${escapeHtml(e.tax)}</span>` : "",
          e.tip ? `<span class="mod-tag">Tip +${escapeHtml(e.tip)}</span>` : "",
        ]
          .filter(Boolean)
          .join("");

        const itemsHtml =
          isItemized && e.items
            ? `<div class="bill-items">${e.items
                .map(
                  (it) =>
                    `<div class="bill-item-row"><span>&bull; ${escapeHtml(it.name)} (${escapeHtml(
                      it.consumers.join(", ")
                    )})</span><span>${escapeHtml(it.amount)}</span></div>`
                )
                .join("")}</div>`
            : "";

        const sharesHtml = (e.shares || [])
          .map(
            (s) =>
              `<span class="share-chip">${escapeHtml(s.member)}: ${escapeHtml(s.formatted)}</span>`
          )
          .join("");

        return `
          <div class="expense-card">
            <div class="expense-top">
              <div>
                <div class="expense-title">
                  <span>#${e.id} ${escapeHtml(e.description)}</span>
                  <span class="mode-badge ${isItemized ? "mode-itemized" : ""}">${escapeHtml(e.mode)}</span>
                </div>
                <div class="expense-meta">Paid by <strong>${escapeHtml(e.payer)}</strong> on ${escapeHtml(e.date)}</div>
              </div>
              <div class="expense-total">${escapeHtml(e.total)}</div>
            </div>
            ${modTags ? `<div class="mod-tags">${modTags}</div>` : ""}
            ${itemsHtml}
            <div class="shares-row">${sharesHtml}</div>
          </div>`;
      })
      .join("");
  }
}

export function renderPPLInspector(execution) {
  // Update 5-stage visual stepper
  const steps = document.querySelectorAll("#pipelineStepper .stage-step");
  steps.forEach((el) => {
    el.classList.remove("pass", "fail");
    const num = Number(el.dataset.stage);
    if (execution.ok) {
      el.classList.add("pass");
    } else if (execution.stage_failed === "lexer_parser") {
      if (num === 1) el.classList.add("pass");
      else if (num === 2 || num === 3) el.classList.add("fail");
    } else if (execution.stage_failed === "semantic") {
      if (num <= 4) el.classList.add("pass");
      else el.classList.add("fail");
    }
  });

  // Tokens view
  const tokens = (execution.tokens || []).filter((t) => t.type !== "NEWLINE");
  document.getElementById("tokenCountBadge").textContent = `${tokens.length} tokens`;
  const tokensView = document.getElementById("tokensView");
  if (!tokens.length) {
    tokensView.innerHTML = `<div class="empty-muted">(no tokens)</div>`;
  } else {
    tokensView.innerHTML = tokens
      .map(
        (t) =>
          `<span class="token-pill ${tokenCategoryClass(t.type)}" title="Line ${t.line}, Col ${t.column}">
             <span class="token-type">${escapeHtml(t.type)}</span>
             <span>${escapeHtml(t.text)}</span>
           </span>`
      )
      .join("");
  }

  document.getElementById("parseTreeView").textContent =
    execution.parse_tree || "(no parse tree)";
  document.getElementById("astTreeView").textContent =
    execution.ast_tree || "(no AST)";
}
