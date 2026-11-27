import React, { useEffect, useRef, useState } from "react";
import { Play, Trash2, Upload } from "lucide-react";

const QUICK_EXAMPLES = [
  { label: "+ Members", code: "add members alice, bob, charlie, dave" },
  { label: "Math + Equal", code: 'alice paid 120k + 30k * 4 for "Grab & Parking" split equally' },
  {
    label: "Ratio + Tax",
    code: 'bob paid 400k for "Hotpot" split ratio alice: 2, bob: 1, charlie: 1 with tax 10%',
  },
  {
    label: "Itemized Bill",
    code:
      'bill "BBQ Night" paid by alice {\n' +
      '    item "Wagyu Beef" 480k for all\n' +
      '    item "Craft Beer" 240k for alice, bob, dave\n' +
      '    item "Matcha Tea" 60k for charlie\n' +
      "    discount 60k\n" +
      "    tax 10%\n" +
      "    tip 5%\n" +
      "}",
  },
  { label: "Settle Up", code: "settle up" },
  { label: "Syntax Error", code: "hello splitlang" },
  { label: "Semantic Error", code: "alice paid 100k for snacks split percent alice: 60%, bob: 30%" },
];

const SYNTAX_GUIDE = [
  ["Groups", 'group "Da Lat Trip"\ncurrency VND  // VND, USD, EUR, JPY, GBP, SGD'],
  ["Members", "add members alice, bob, charlie, dave\nremove member dave"],
  ["Equal + Math", 'alice paid 120k + 30k * 4 for "Taxi" split equally\nbob paid 180k for "Coffee" excluding dave'],
  ["Exact / % / Ratio", 'bob paid 150k for coffee split exact alice: 60k, bob: 50k, charlie: 40k\nalice paid 1m for hotel split percent alice: 40%, bob: 30%, charlie: 30%\ncharlie paid 400k for hotpot split ratio alice: 2, bob: 1, charlie: 1 with tax 10%'],
  ["Itemized Bill", 'bill "BBQ" paid by alice {\n    item "Beef" 450k for all\n    item "Tea" 60k for charlie\n    discount 50k; tax 10%; tip 5%\n}'],
  ["Settle & Query", "dave pays alice 100k\nshow balances; who owes whom?; settle up"],
];

function stepClass(execution, num) {
  if (!execution) return "";
  if (execution.ok) return "pass";
  if (execution.stage_failed === "lexer_parser") {
    if (num === 1) return "pass";
    if (num === 2 || num === 3) return "fail";
    return "";
  }
  if (execution.stage_failed === "semantic") {
    return num <= 4 ? "pass" : "fail";
  }
  return "";
}

export default function PlaygroundPage({
  code,
  onCodeChange,
  logs,
  onClearLogs,
  onExecute,
  onUploadFile,
  lastExecution,
  busy,
}) {
  const [tab, setTab] = useState("tokens"); // tokens | tree | ast | guide
  const fileRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const tokens = (lastExecution?.tokens || []).filter((t) => t.type !== "NEWLINE");

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (code.trim()) onExecute(code);
    }
  };

  return (
    <div>
      {/* Visible Quick Example Bar — click any pill to insert & optionally run */}
      <div className="member-bar" style={{ marginBottom: 18 }}>
        <div className="choice-row" style={{ flex: 1 }}>
          <span className="t-label" style={{ alignSelf: "center", marginRight: 4 }}>Try:</span>
          {QUICK_EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              className="choice-btn"
              onClick={() => onCodeChange(ex.code)}
            >
              {ex.label}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => fileRef.current?.click()}
          >
            <Upload size={13} />
            <span>Upload .split</span>
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".split"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onUploadFile(f);
              e.target.value = "";
            }}
          />

          {/* Sole Primary Action on DSL Playground */}
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={busy || !code.trim()}
            onClick={() => onExecute(code)}
          >
            <Play size={13} />
            <span>{busy ? "Running..." : "Run SplitLang (Ctrl+Enter)"}</span>
          </button>
        </div>
      </div>

      <div className="playground-split">
        {/* Left: Editor + Output */}
        <div className="stack">
          <section className="card-flush">
            <div className="card-head">
              <h2 className="t-h2">SplitLang Editor</h2>
              <span className="t-label">Ctrl+Enter to execute</span>
            </div>
            <textarea
              className="editor-textarea"
              spellCheck={false}
              value={code}
              onChange={(e) => onCodeChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={'// Click any example above or type commands:\nadd members alice, bob, charlie\nalice paid 300k for "Dinner" split equally'}
            />
          </section>

          <section className="card-flush">
            <div className="card-head">
              <h2 className="t-h2">Console Output</h2>
              <button type="button" className="btn btn-ghost btn-xs" onClick={onClearLogs}>
                <Trash2 size={13} />
                <span>Clear</span>
              </button>
            </div>
            <div className="output-stream">
              {logs.length === 0 ? (
                <div style={{ color: "var(--secondary)" }}>
                  Execution results, balances, and parser errors appear here.
                </div>
              ) : (
                logs.map((row) => (
                  <div key={row.id} className={`log-row ${row.kind}`}>
                    {row.badge && (
                      <div className="t-label" style={{ marginBottom: 4, color: "var(--primary)" }}>
                        {row.badge}
                      </div>
                    )}
                    <div>{row.text}</div>
                  </div>
                ))
              )}
              <div ref={endRef} />
            </div>
          </section>
        </div>

        {/* Right: 5-Stage PPL Pipeline Inspector + Built-in Grammar Cheatsheet */}
        <div>
          <div className="pipeline-bar">
            {[
              [1, "01 Input"],
              [2, "02 Lexer"],
              [3, "03 Parser"],
              [4, "04 AST"],
              [5, "05 Action"],
            ].map(([n, label]) => (
              <div key={n} className={`stage-cell ${stepClass(lastExecution, n)}`}>
                {label}
              </div>
            ))}
          </div>

          <section className="card-flush">
            <div className="card-head">
              <h2 className="t-h2">ANTLR 4.9.2 Inspector</h2>
              <span className="tag">{tokens.length} tokens</span>
            </div>

            <div className="subtab-bar">
              {[
                ["tokens", "Tokens"],
                ["tree", "Parse Tree"],
                ["ast", "AST"],
                ["guide", "Syntax Guide"],
              ].map(([id, lbl]) => (
                <button
                  key={id}
                  type="button"
                  className={`subtab-btn ${tab === id ? "active" : ""}`}
                  onClick={() => setTab(id)}
                >
                  {lbl}
                </button>
              ))}
            </div>

            {tab === "tokens" && (
              <div className="tokens-matrix">
                {tokens.length === 0 ? (
                  <div style={{ color: "var(--secondary)", fontSize: "0.84rem" }}>
                    Run any command to inspect its ANTLR 4.9.2 Lexer tokens.
                  </div>
                ) : (
                  tokens.map((t, i) => (
                    <span
                      key={i}
                      className="tok-chip"
                      title={`Line ${t.line}, Col ${t.column}`}
                    >
                      <span className="tt">{t.type}</span>
                      <span>{t.text}</span>
                    </span>
                  ))
                )}
              </div>
            )}

            {tab === "tree" && (
              <pre className="tree-code">
                {lastExecution?.parse_tree || "// Run a command to inspect the Concrete Parse Tree"}
              </pre>
            )}

            {tab === "ast" && (
              <pre className="tree-code">
                {lastExecution?.ast_tree || "// Run a command to inspect distilled AST Op nodes"}
              </pre>
            )}

            {tab === "guide" && (
              <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12, maxHeight: 460, overflowY: "auto" }}>
                {SYNTAX_GUIDE.map(([title, snippet]) => (
                  <div key={title}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <span className="t-label" style={{ color: "var(--primary)" }}>{title}</span>
                      <button
                        type="button"
                        className="btn btn-ghost btn-xs"
                        onClick={() => onCodeChange(snippet)}
                      >
                        Insert
                      </button>
                    </div>
                    <pre className="dsl-preview">{snippet}</pre>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
