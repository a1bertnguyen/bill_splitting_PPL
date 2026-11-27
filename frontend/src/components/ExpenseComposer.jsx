import React, { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Plus, Terminal, Trash2 } from "lucide-react";

const QUICK_DESCS = ["Dinner", "Coffee", "Hotpot", "Grab / Taxi", "Hotel", "Groceries"];

export default function ExpenseComposer({
  members,
  currency,
  busy,
  onExecute,
  onInspectInPlayground,
}) {
  const [kind, setKind] = useState("expense"); // "expense" | "bill"
  const [payer, setPayer] = useState(members[0] || "");

  // Quick Expense state
  const [amount, setAmount] = useState(currency === "USD" ? "$60" : "300k");
  const [desc, setDesc] = useState("Dinner");
  const [mode, setMode] = useState("equal");
  const [selected, setSelected] = useState(members);
  const [allocs, setAllocs] = useState({});

  // Shared Modifiers (collapsed by default for clean UX)
  const [showMods, setShowMods] = useState(false);
  const [discount, setDiscount] = useState("");
  const [taxPct, setTaxPct] = useState("");
  const [tipPct, setTipPct] = useState("");

  // Itemized Bill state
  const [billTitle, setBillTitle] = useState("BBQ Night");
  const [items, setItems] = useState([
    { id: 1, name: "Main Dish", price: currency === "USD" ? "$40" : "400k", forAll: true, consumers: [] },
    { id: 2, name: "Drinks", price: currency === "USD" ? "$20" : "180k", forAll: true, consumers: [] },
  ]);

  const [showDsl, setShowDsl] = useState(true);

  useEffect(() => {
    setPayer((prev) => (members.includes(prev) ? prev : members[0] || ""));
    setSelected(members);
    setAllocs((prev) => {
      const next = {};
      const evenPct = members.length ? Math.floor(100 / members.length) : 0;
      members.forEach((m, idx) => {
        if (prev[m] !== undefined) next[m] = prev[m];
        else next[m] = mode === "percent" ? String(idx === 0 ? 100 - evenPct * (members.length - 1) : evenPct) : "1";
      });
      return next;
    });
  }, [members]);

  const handleModeChange = (nextMode) => {
    setMode(nextMode);
    if (!members.length) return;
    const next = {};
    if (nextMode === "percent") {
      const base = Math.floor(100 / members.length);
      members.forEach((m, i) => {
        next[m] = String(i === 0 ? 100 - base * (members.length - 1) : base);
      });
    } else if (nextMode === "ratio") {
      members.forEach((m) => {
        next[m] = "1";
      });
    } else if (nextMode === "exact") {
      members.forEach((m) => {
        next[m] = "";
      });
    }
    setAllocs(next);
  };

  // Live percentage helper
  const percentSum = useMemo(() => {
    if (mode !== "percent") return 100;
    return members.reduce((acc, m) => acc + (parseFloat(String(allocs[m] || "0").replace("%", "")) || 0), 0);
  }, [mode, members, allocs]);

  // Generate real SplitLang DSL
  const generatedDSL = useMemo(() => {
    if (!payer || !members.length) return "";
    if (kind === "expense") {
      if (!amount.trim()) return "";
      const safeDesc = desc.trim().replaceAll('"', '\\"') || "Expense";
      let cmd = `${payer} paid ${amount.trim()} for "${safeDesc}"`;
      if (mode === "equal") {
        if (selected.length > 0 && selected.length < members.length) {
          cmd += ` split equally among ${selected.join(", ")}`;
        } else {
          cmd += " split equally";
        }
      } else if (mode === "exact") {
        const pairs = members
          .filter((m) => (allocs[m] || "").trim())
          .map((m) => `${m}: ${allocs[m].trim()}`);
        if (pairs.length) cmd += ` split exact ${pairs.join(", ")}`;
      } else if (mode === "percent") {
        const pairs = members
          .filter((m) => (allocs[m] || "").trim())
          .map((m) => `${m}: ${String(allocs[m]).trim().replace(/%$/, "")}%`);
        if (pairs.length) cmd += ` split percent ${pairs.join(", ")}`;
      } else if (mode === "ratio") {
        const pairs = members
          .filter((m) => (allocs[m] || "").trim())
          .map((m) => `${m}: ${allocs[m].trim()}`);
        if (pairs.length) cmd += ` split ratio ${pairs.join(", ")}`;
      }
      if (discount.trim()) cmd += ` with discount ${discount.trim()}`;
      if (taxPct.trim()) cmd += ` with tax ${taxPct.trim().replace(/%$/, "")}%`;
      if (tipPct.trim()) cmd += ` with tip ${tipPct.trim().replace(/%$/, "")}%`;
      return cmd;
    }

    // Itemized bill block
    const validItems = items.filter((it) => it.name.trim() && it.price.trim());
    if (!validItems.length) return "";
    const safeTitle = billTitle.trim().replaceAll('"', '\\"') || "Itemized Bill";
    const lines = [`bill "${safeTitle}" paid by ${payer} {`];
    for (const it of validItems) {
      const target = it.forAll || !it.consumers.length ? "all" : it.consumers.join(", ");
      lines.push(`    item "${it.name.trim().replaceAll('"', '\\"')}" ${it.price.trim()} for ${target}`);
    }
    if (discount.trim()) lines.push(`    discount ${discount.trim()}`);
    if (taxPct.trim()) lines.push(`    tax ${taxPct.trim().replace(/%$/, "")}%`);
    if (tipPct.trim()) lines.push(`    tip ${tipPct.trim().replace(/%$/, "")}%`);
    lines.push("}");
    return lines.join("\n");
  }, [kind, payer, members, amount, desc, mode, selected, allocs, discount, taxPct, tipPct, billTitle, items]);

  const amountPresets = currency === "USD" ? ["$15", "$30", "$60", "$120"] : ["50k", "150k", "300k", "500k"];

  const toggleItemConsumer = (itemId, member) => {
    setItems((prev) =>
      prev.map((it) => {
        if (it.id !== itemId) return it;
        const base = it.forAll ? [...members] : [...it.consumers];
        const next = base.includes(member) ? base.filter((x) => x !== member) : [...base, member];
        return {
          ...it,
          forAll: next.length === members.length,
          consumers: next.length === members.length ? [] : next,
        };
      })
    );
  };

  const disabled = busy || !members.length || !generatedDSL;

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2 className="t-h2">Add Expense</h2>
          <div className="t-label">Pick visually — generates valid SplitLang DSL</div>
        </div>
        <span className="tag">{currency}</span>
      </div>

      {/* Mode Tabs: Quick Expense vs Itemized Bill */}
      <div className="composer-tabs">
        <button
          type="button"
          className={`composer-tab ${kind === "expense" ? "active" : ""}`}
          onClick={() => setKind("expense")}
        >
          Quick Expense
        </button>
        <button
          type="button"
          className={`composer-tab ${kind === "bill" ? "active" : ""}`}
          onClick={() => setKind("bill")}
        >
          Itemized Bill (Multiple Dishes)
        </button>
      </div>

      {!members.length ? (
        <div style={{ padding: "18px 0", color: "var(--secondary)", fontSize: "0.88rem" }}>
          Add at least 2 members in the bar above (or click <strong>Load Demo</strong>) to start splitting.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* 1. Paid By (1-click pills!) */}
          <div>
            <label className="field-label">1. Who paid?</label>
            <div className="choice-row">
              {members.map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`choice-btn ${payer === m ? "active" : ""}`}
                  onClick={() => setPayer(m)}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          {kind === "expense" ? (
            <>
              {/* 2. Amount & Description */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: 12 }}>
                <div>
                  <label className="field-label" htmlFor="c-amt">2. Amount (supports math)</label>
                  <input
                    id="c-amt"
                    className="input mono"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder={currency === "USD" ? "$60 or $25 * 2" : "300k or 120k + 30k * 2"}
                  />
                  <div className="choice-row" style={{ marginTop: 6 }}>
                    {amountPresets.map((p) => (
                      <button
                        key={p}
                        type="button"
                        className="btn btn-ghost btn-xs"
                        style={{ border: "1px solid var(--line)" }}
                        onClick={() => setAmount(p)}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="field-label" htmlFor="c-desc">3. What for?</label>
                  <input
                    id="c-desc"
                    className="input"
                    value={desc}
                    onChange={(e) => setDesc(e.target.value)}
                    placeholder="Dinner, Coffee, Taxi..."
                  />
                  <div className="choice-row" style={{ marginTop: 6 }}>
                    {QUICK_DESCS.slice(0, 4).map((d) => (
                      <button
                        key={d}
                        type="button"
                        className="btn btn-ghost btn-xs"
                        style={{ border: "1px solid var(--line)" }}
                        onClick={() => setDesc(d)}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* 4. Split Mode */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <label className="field-label" style={{ marginBottom: 0 }}>4. How to split?</label>
                  {mode === "percent" && (
                    <span className="t-label" style={{ color: Math.abs(percentSum - 100) < 0.01 ? "var(--primary)" : "var(--secondary)" }}>
                      Sum: {percentSum}% {Math.abs(percentSum - 100) < 0.01 ? "✓" : "(must equal 100%)"}
                    </span>
                  )}
                </div>

                <div className="choice-row" style={{ marginBottom: 10 }}>
                  {[
                    ["equal", "Equal"],
                    ["exact", "Exact Amounts"],
                    ["percent", "Percent %"],
                    ["ratio", "Ratio / Shares"],
                  ].map(([k, lbl]) => (
                    <button
                      key={k}
                      type="button"
                      className={`choice-btn ${mode === k ? "active" : ""}`}
                      onClick={() => handleModeChange(k)}
                    >
                      {lbl}
                    </button>
                  ))}
                </div>

                {mode === "equal" ? (
                  <div>
                    <div className="t-label" style={{ marginBottom: 6 }}>Split between (click to toggle):</div>
                    <div className="choice-row">
                      {members.map((m) => {
                        const on = selected.includes(m);
                        return (
                          <button
                            key={m}
                            type="button"
                            className={`choice-btn ${on ? "active" : ""}`}
                            onClick={() =>
                              setSelected((prev) =>
                                prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]
                              )
                            }
                          >
                            {on ? "✓" : "○"} {m}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    {members.map((m) => (
                      <div key={m} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span className="mono" style={{ minWidth: 66, fontSize: "0.8rem" }}>{m}</span>
                        <input
                          className="input mono"
                          style={{ padding: "6px 9px", fontSize: "0.82rem" }}
                          value={allocs[m] || ""}
                          onChange={(e) => setAllocs((prev) => ({ ...prev, [m]: e.target.value }))}
                          placeholder={mode === "percent" ? "25%" : mode === "exact" ? "100k" : "1"}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            /* Itemized Bill Builder */
            <>
              <div>
                <label className="field-label" htmlFor="b-title">2. Bill / Restaurant Name</label>
                <input
                  id="b-title"
                  className="input"
                  value={billTitle}
                  onChange={(e) => setBillTitle(e.target.value)}
                  placeholder="BBQ Night"
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <label className="field-label" style={{ marginBottom: 0 }}>3. Items &amp; who shared each</label>
                  <button
                    type="button"
                    className="btn btn-secondary btn-xs"
                    onClick={() =>
                      setItems((prev) => [
                        ...prev,
                        { id: Date.now(), name: "", price: "", forAll: true, consumers: [] },
                      ])
                    }
                  >
                    <Plus size={12} />
                    <span>Add Item</span>
                  </button>
                </div>

                {items.map((it) => (
                  <div key={it.id} className="item-builder-row">
                    <div style={{ display: "grid", gridTemplateColumns: "1.4fr 0.8fr auto", gap: 8 }}>
                      <input
                        className="input"
                        style={{ padding: "6px 9px", fontSize: "0.84rem" }}
                        placeholder="Item name (e.g. Wagyu Beef)"
                        value={it.name}
                        onChange={(e) =>
                          setItems((prev) =>
                            prev.map((x) => (x.id === it.id ? { ...x, name: e.target.value } : x))
                          )
                        }
                      />
                      <input
                        className="input mono"
                        style={{ padding: "6px 9px", fontSize: "0.84rem" }}
                        placeholder={currency === "USD" ? "$24" : "240k"}
                        value={it.price}
                        onChange={(e) =>
                          setItems((prev) =>
                            prev.map((x) => (x.id === it.id ? { ...x, price: e.target.value } : x))
                          )
                        }
                      />
                      <button
                        type="button"
                        className="btn btn-ghost btn-xs"
                        disabled={items.length <= 1}
                        onClick={() => setItems((prev) => prev.filter((x) => x.id !== it.id))}
                        aria-label="Remove item"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                    <div className="choice-row">
                      <button
                        type="button"
                        className={`choice-btn ${it.forAll ? "active" : ""}`}
                        style={{ padding: "3px 8px", fontSize: "0.7rem" }}
                        onClick={() =>
                          setItems((prev) =>
                            prev.map((x) => (x.id === it.id ? { ...x, forAll: true, consumers: [] } : x))
                          )
                        }
                      >
                        All
                      </button>
                      {members.map((m) => {
                        const checked = it.forAll || it.consumers.includes(m);
                        return (
                          <button
                            key={m}
                            type="button"
                            className={`choice-btn ${!it.forAll && checked ? "active" : ""}`}
                            style={{ padding: "3px 8px", fontSize: "0.7rem" }}
                            onClick={() => toggleItemConsumer(it.id, m)}
                          >
                            {m}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Optional Tax / Tip / Discount */}
          <div>
            <button
              type="button"
              className="btn btn-ghost btn-xs"
              style={{ paddingLeft: 0 }}
              onClick={() => setShowMods((v) => !v)}
            >
              {showMods ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              <span>{showMods ? "Hide tax, tip & discount" : "+ Add tax, tip or discount (optional)"}</span>
            </button>

            {showMods && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginTop: 8 }}>
                <div>
                  <label className="field-label">Discount</label>
                  <input
                    className="input mono"
                    style={{ padding: "7px 9px", fontSize: "0.82rem" }}
                    value={discount}
                    onChange={(e) => setDiscount(e.target.value)}
                    placeholder="50k / 10%"
                  />
                </div>
                <div>
                  <label className="field-label">Tax %</label>
                  <input
                    className="input mono"
                    style={{ padding: "7px 9px", fontSize: "0.82rem" }}
                    value={taxPct}
                    onChange={(e) => setTaxPct(e.target.value)}
                    placeholder="10"
                  />
                </div>
                <div>
                  <label className="field-label">Tip %</label>
                  <input
                    className="input mono"
                    style={{ padding: "7px 9px", fontSize: "0.82rem" }}
                    value={tipPct}
                    onChange={(e) => setTipPct(e.target.value)}
                    placeholder="5"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Live Generated SplitLang DSL Preview */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                style={{ padding: 0 }}
                onClick={() => setShowDsl((v) => !v)}
              >
                <span className="t-label">// generated splitlang dsl {showDsl ? "▾" : "▸"}</span>
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                disabled={!generatedDSL}
                onClick={() => onInspectInPlayground(generatedDSL)}
              >
                <Terminal size={12} />
                <span>Inspect AST</span>
              </button>
            </div>
            {showDsl && <pre className="dsl-preview">{generatedDSL || "// Fill fields above"}</pre>}
          </div>

          {/* Sole Primary Action on Workspace */}
          <button
            type="button"
            className="btn btn-primary"
            style={{ width: "100%" }}
            disabled={disabled}
            onClick={() => onExecute(generatedDSL)}
          >
            <Plus size={15} />
            <span>{busy ? "Recording..." : kind === "bill" ? "Record Itemized Bill" : "Record Expense"}</span>
          </button>
        </div>
      )}
    </section>
  );
}
