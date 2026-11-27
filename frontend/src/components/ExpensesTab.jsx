import React from "react";

export default function ExpensesTab({ expenses }) {
  return (
    <div className="tab-content">
      <div className="section-title">
        Recorded Expenses &amp; Itemized Bills
        <span className="section-sub">Newest first &middot; Encrypted descriptions &middot; Exact rounding</span>
      </div>

      <div className="expenses-list">
        {!expenses || expenses.length === 0 ? (
          <div className="empty-muted">No expenses recorded in this group yet.</div>
        ) : (
          expenses.map((e) => {
            const isItemized = e.kind === "bill";
            return (
              <div key={e.id} className="expense-card">
                <div className="expense-top">
                  <div>
                    <div className="expense-title">
                      <span>
                        #{e.id} {e.description}
                      </span>
                      <span className={`mode-badge ${isItemized ? "mode-itemized" : ""}`}>
                        {e.mode}
                      </span>
                    </div>
                    <div className="expense-meta">
                      Paid by <strong>{e.payer}</strong> on {e.date}
                    </div>
                  </div>
                  <div className="expense-total">{e.total}</div>
                </div>

                {(e.discount || e.tax || e.tip) && (
                  <div className="mod-tags">
                    {e.discount && <span className="mod-tag">Discount -{e.discount}</span>}
                    {e.tax && <span className="mod-tag">Tax +{e.tax}</span>}
                    {e.tip && <span className="mod-tag">Tip +{e.tip}</span>}
                  </div>
                )}

                {isItemized && e.items && (
                  <div className="bill-items">
                    {e.items.map((it, idx) => (
                      <div key={idx} className="bill-item-row">
                        <span>
                          &bull; {it.name} ({it.consumers.join(", ")})
                        </span>
                        <span>{it.amount}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="shares-row">
                  {(e.shares || []).map((s) => (
                    <span key={s.member} className="share-chip">
                      {s.member}: {s.formatted}
                    </span>
                  ))}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
