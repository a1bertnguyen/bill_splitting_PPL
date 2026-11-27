import React, { useMemo, useState } from "react";
import { ArrowRight, Check, Search, Sparkles, UserPlus, X } from "lucide-react";
import ExpenseComposer from "./ExpenseComposer.jsx";

export default function WorkspacePage({
  state,
  busy,
  onExecute,
  onRunDemo,
  onInspectInPlayground,
}) {
  const [newMember, setNewMember] = useState("");
  const [search, setSearch] = useState("");
  const [modeFilter, setModeFilter] = useState("ALL");

  const members = state?.members || [];
  const balances = state?.balances || [];
  const transfers = state?.transfers || [];
  const expenses = state?.expenses || [];

  const maxAbsNet = Math.max(1, ...balances.map((b) => Math.abs(b.net_raw || 0)));

  const filteredExpenses = useMemo(() => {
    return expenses.filter((e) => {
      if (modeFilter !== "ALL" && e.mode !== modeFilter) return false;
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        e.description.toLowerCase().includes(q) ||
        e.payer.toLowerCase().includes(q) ||
        e.shares_text.toLowerCase().includes(q)
      );
    });
  }, [expenses, search, modeFilter]);

  const handleAddMember = (e) => {
    e.preventDefault();
    const cleaned = newMember.trim();
    if (!cleaned) return;
    onExecute(`member add [${cleaned}]`);
    setNewMember("");
  };

  return (
    <div>
      {/* Friendly Onboarding Strip when group is empty */}
      {members.length === 0 && (
        <div className="onboarding-banner">
          <div style={{ maxWidth: 560 }}>
            <div className="t-label" style={{ marginBottom: 4 }}>// quick start</div>
            <h1 className="t-h1" style={{ marginBottom: 6 }}>
              Start splitting in "{state?.group?.name || "Default"}"
            </h1>
            <p style={{ color: "var(--secondary)", fontSize: "0.9rem" }}>
              Add friends below (comma-separated, e.g.{" "}
              <span className="mono" style={{ color: "var(--primary)" }}>alice, bob, charlie</span>)
              or load a full demo trip with one click.
            </p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => onRunDemo("dinner")}
            >
              <Sparkles size={15} />
              <span>Try Saigon Weekend (VND)</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => onRunDemo("trip")}
            >
              <span>Try Tokyo Trip (USD)</span>
            </button>
          </div>
        </div>
      )}

      {/* Always-Accessible Member Strip */}
      <div className="member-bar">
        <div className="member-chips">
          <span className="t-label">Members ({members.length}):</span>
          {members.length === 0 ? (
            <span style={{ fontSize: "0.84rem", color: "var(--secondary)" }}>None yet</span>
          ) : (
            members.map((m) => (
              <span key={m} className="member-chip">
                <span>{m}</span>
                <button
                  type="button"
                  onClick={() => onExecute(`member remove [${m}]`)}
                  title={`Remove ${m}`}
                  aria-label={`Remove ${m}`}
                >
                  <X size={12} />
                </button>
              </span>
            ))
          )}
        </div>

        <form onSubmit={handleAddMember} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="input"
            style={{ width: 210, padding: "7px 10px", fontSize: "0.84rem" }}
            placeholder="Add: alice, bob, charlie..."
            value={newMember}
            onChange={(e) => setNewMember(e.target.value)}
            aria-label="Add members"
          />
          <button type="submit" className="btn btn-secondary btn-sm" disabled={busy || !newMember.trim()}>
            <UserPlus size={14} />
            <span>Add</span>
          </button>
          {members.length > 0 && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={busy}
              onClick={() => onRunDemo("dinner")}
              title="Load Saigon Weekend demo"
            >
              Load Demo
            </button>
          )}
        </form>
      </div>

      {/* Main All-in-One 2-Column Workspace */}
      <div className="workspace-grid">
        {/* Left Column: Inline Visual Expense & Itemized Bill Builder */}
        <ExpenseComposer
          members={members}
          currency={state?.currency || "VND"}
          busy={busy}
          onExecute={onExecute}
          onInspectInPlayground={onInspectInPlayground}
        />

        {/* Right Column: Live Telemetry, Optimal Transfers, Balances & Expense History */}
        <div className="stack">
          {/* Compact Summary Strip */}
          <div className="stats-bar">
            <div className="stat-box">
              <span className="t-label">Total Spent</span>
              <span className="stat-num tnum">{state?.total_spent || "0 VND"}</span>
            </div>
            <div className="stat-box">
              <span className="t-label">Expenses</span>
              <span className="stat-num tnum">{state?.expense_count || 0}</span>
            </div>
            <div className="stat-box">
              <span className="t-label">Transfers Left</span>
              <span className="stat-num tnum">{transfers.length}</span>
            </div>
          </div>

          {/* 1. Who Owes Whom (Optimal Settlements — right at top!) */}
          <section className="card">
            <div className="card-head">
              <div>
                <h2 className="t-h2">Who Owes Whom</h2>
                <div className="t-label">Optimal Minimum Cash Flow (&le; N &minus; 1 transfers)</div>
              </div>
              <span className="tag">{transfers.length} to settle</span>
            </div>

            {transfers.length === 0 ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--secondary)", padding: "6px 0" }}>
                <Check size={16} />
                <span>Everyone is settled up. No transfers needed.</span>
              </div>
            ) : (
              transfers.map((tr, i) => (
                <div key={`${tr.from}-${tr.to}-${i}`} className="transfer-row">
                  <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 500 }}>
                    <span className="mono">{tr.from}</span>
                    <ArrowRight size={14} color="var(--secondary)" />
                    <span className="mono">{tr.to}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="tnum" style={{ fontWeight: 600 }}>{tr.formatted}</span>
                    <button
                      type="button"
                      className="btn btn-secondary btn-xs"
                      disabled={busy}
                      onClick={() => onExecute(`transfer ${tr.from} -> ${tr.to} = ${tr.amount}`)}
                    >
                      Mark Paid
                    </button>
                  </div>
                </div>
              ))
            )}
          </section>

          {/* 2. Member Balances */}
          {balances.length > 0 && (
            <section className="card">
              <div className="card-head">
                <h2 className="t-h2">Member Balances</h2>
                <span className="t-label">Paid vs Share</span>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Member</th>
                    <th className="num">Paid</th>
                    <th className="num">Share</th>
                    <th className="num">Net</th>
                  </tr>
                </thead>
                <tbody>
                  {balances.map((b) => {
                    const pct = Math.min(100, Math.round((Math.abs(b.net_raw) / maxAbsNet) * 100));
                    return (
                      <tr key={b.member}>
                        <td style={{ paddingRight: 12 }}>
                          <div className="mono" style={{ fontSize: "0.84rem", fontWeight: 500 }}>{b.member}</div>
                          <div className="bar-track">
                            <div
                              className={`bar-fill ${b.net_raw < 0 ? "neg" : ""}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </td>
                        <td className="num tnum" style={{ fontSize: "0.82rem", color: "var(--secondary)" }}>{b.paid}</td>
                        <td className="num tnum" style={{ fontSize: "0.82rem", color: "var(--secondary)" }}>{b.owed}</td>
                        <td className="num tnum">
                          <span className={`tag ${b.net_raw > 0 ? "tag-bright" : ""}`}>{b.net}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
          )}

          {/* 3. Recorded Expenses & Itemized Bills (Inline, searchable!) */}
          <section className="card">
            <div className="card-head" style={{ flexWrap: "wrap" }}>
              <h2 className="t-h2">History ({expenses.length})</h2>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <div style={{ position: "relative", width: 170 }}>
                  <Search
                    size={13}
                    style={{
                      position: "absolute",
                      left: 9,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--secondary)",
                    }}
                  />
                  <input
                    className="input"
                    style={{ padding: "5px 8px 5px 28px", fontSize: "0.78rem" }}
                    placeholder="Search..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <select
                  className="select-input"
                  style={{ width: 108, padding: "5px 8px", fontSize: "0.78rem" }}
                  value={modeFilter}
                  onChange={(e) => setModeFilter(e.target.value)}
                  aria-label="Filter by split mode"
                >
                  {["ALL", "ITEMIZED", "EQUAL", "EXACT", "PERCENT", "RATIO"].map((m) => (
                    <option key={m} value={m}>{m === "ALL" ? "All modes" : m}</option>
                  ))}
                </select>
              </div>
            </div>

            {filteredExpenses.length === 0 ? (
              <div style={{ color: "var(--secondary)", fontSize: "0.86rem", padding: "8px 0" }}>
                No expenses recorded yet. Use the form on the left to add your first one.
              </div>
            ) : (
              filteredExpenses.map((e) => (
                <div key={e.id} className="expense-row">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <strong style={{ fontSize: "0.92rem" }}>#{e.id} {e.description}</strong>
                        <span className="tag">{e.mode}</span>
                      </div>
                      <div style={{ fontSize: "0.78rem", color: "var(--secondary)", marginTop: 2 }}>
                        Paid by <strong style={{ color: "var(--primary)" }}>{e.payer}</strong> · {e.date}
                        {e.discount ? ` · disc -${e.discount}` : ""}
                        {e.tax ? ` · tax +${e.tax}` : ""}
                        {e.tip ? ` · tip +${e.tip}` : ""}
                      </div>
                    </div>
                    <span className="tnum" style={{ fontWeight: 600 }}>{e.total}</span>
                  </div>

                  {e.kind === "bill" && e.items && (
                    <div
                      style={{
                        backgroundColor: "var(--neutral)",
                        border: "1px solid var(--line)",
                        borderRadius: "var(--r-sm)",
                        padding: "8px 10px",
                        fontSize: "0.78rem",
                        display: "flex",
                        flexDirection: "column",
                        gap: 4,
                      }}
                    >
                      {e.items.map((it, idx) => (
                        <div key={idx} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                          <span>
                            • {it.name} <span style={{ color: "var(--secondary)" }}>({it.consumers.join(", ")})</span>
                          </span>
                          <span className="tnum">{it.amount}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="choice-row">
                    {(e.shares || []).map((s) => (
                      <span key={s.member} className="tag tnum">
                        {s.member}: {s.formatted}
                      </span>
                    ))}
                  </div>
                </div>
              ))
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
