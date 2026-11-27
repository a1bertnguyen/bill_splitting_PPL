import React from "react";

export default function BalancesTab({ state, onMarkPaid }) {
  const balances = state?.balances || [];
  const transfers = state?.transfers || [];

  return (
    <div className="tab-content">
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Total Spent</div>
          <div className="kpi-value text-cyan">{state?.total_spent || "0 VND"}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Members</div>
          <div className="kpi-value text-violet">{state?.members?.length || 0}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Expenses / Bills</div>
          <div className="kpi-value text-amber">{state?.expense_count || 0}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Min Transfers</div>
          <div className="kpi-value text-emerald">{transfers.length}</div>
        </div>
      </div>

      <div className="section-block">
        <div className="section-title">Member Balances</div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Member</th>
                <th className="num">Total Paid</th>
                <th className="num">Total Share</th>
                <th className="num">Net Balance</th>
              </tr>
            </thead>
            <tbody>
              {balances.length === 0 ? (
                <tr>
                  <td colSpan={4} className="empty-muted">
                    No members yet. Try: <code>add members alice, bob, charlie</code>
                  </td>
                </tr>
              ) : (
                balances.map((b) => {
                  const cls = b.net_raw > 0 ? "net-pos" : b.net_raw < 0 ? "net-neg" : "net-zero";
                  return (
                    <tr key={b.member}>
                      <td>
                        <div className="member-cell">
                          <span className="avatar">{b.member.slice(0, 2)}</span>
                          <span>{b.member}</span>
                        </div>
                      </td>
                      <td className="num">{b.paid}</td>
                      <td className="num">{b.owed}</td>
                      <td className="num">
                        <span className={`net-pill ${cls}`}>{b.net}</span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="section-block">
        <div className="section-title text-emerald">
          Optimal Settlement Plan
          <span className="section-sub">Greedy Minimum Cash Flow (&le; N &minus; 1 transfers)</span>
        </div>
        <div className="transfers-list">
          {transfers.length === 0 ? (
            <div className="empty-muted">All settled up! No transfers needed.</div>
          ) : (
            transfers.map((tr, idx) => (
              <div key={`${tr.from}-${tr.to}-${idx}`} className="transfer-card">
                <div className="transfer-flow">
                  <span>{tr.from}</span>
                  <span className="transfer-arrow">&rarr;</span>
                  <span>{tr.to}</span>
                </div>
                <div className="transfer-right">
                  <span className="transfer-amount">{tr.formatted}</span>
                  <button
                    type="button"
                    className="mark-paid-btn"
                    onClick={() => onMarkPaid(tr.from, tr.to, tr.amount)}
                  >
                    Mark Paid
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
