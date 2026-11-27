import React, { useEffect, useRef } from "react";

const QUICK_CHIPS = [
  { label: "+ Members", code: "add members alice, bob, charlie, dave" },
  { label: "Equal", code: 'alice paid 300k for "Dinner" split equally' },
  {
    label: "Ratio + Tax",
    code: 'bob paid 120k + 30k * 2 for "Hotpot" split ratio alice: 2, bob: 1, charlie: 1 with tax 10%',
  },
  {
    label: "Itemized Bill",
    code:
      'bill "BBQ Night" paid by alice {\n' +
      '    item "Wagyu Beef" 480k for all\n' +
      '    item "Beer Tower" 240k for alice, bob, dave\n' +
      '    item "Matcha Tea" 60k for charlie\n' +
      "    discount 60k\n" +
      "    tax 10%\n" +
      "    tip 5%\n" +
      "}",
  },
  { label: "Settle Up", code: "settle up" },
  { label: "Syntax Error", code: "hello splitlang", danger: true },
  {
    label: "Semantic Error",
    code: "alice paid 100k for snacks split percent alice: 60%, bob: 30%",
    danger: true,
  },
];

export default function ConsolePanel({
  logs,
  inputCode,
  onInputChange,
  onExecute,
  onClearLogs,
  history,
  historyIdx,
  onHistoryNav,
  busy,
}) {
  const logEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (inputCode.trim()) onExecute(inputCode, true);
    } else if (e.key === "ArrowUp" && !inputCode.includes("\n")) {
      if (historyIdx > 0) {
        e.preventDefault();
        onHistoryNav(historyIdx - 1);
      }
    } else if (e.key === "ArrowDown" && !inputCode.includes("\n")) {
      if (historyIdx < history.length) {
        e.preventDefault();
        onHistoryNav(historyIdx + 1);
      }
    }
  };

  return (
    <section className="panel console-panel">
      <div className="panel-header">
        <div className="panel-title">
          <span className="dot" />
          DSL Console &amp; Transcript
        </div>
        <button type="button" className="btn-ghost" onClick={onClearLogs}>
          Clear Log
        </button>
      </div>

      <div className="console-log" aria-live="polite">
        <div className="log-entry log-banner">
          <strong>Welcome to SplitLang!</strong> — Secure Bill-Splitting DSL (React + MySQL + ANTLR 4.9.2).
          <br />
          Type commands below (<kbd>Ctrl+Enter</kbd>), click <strong>Run Demo</strong>, or inspect the{" "}
          <strong>PPL Inspector</strong> tab to view Lexer Tokens, Parse Tree, and AST live.
        </div>

        {logs.map((entry) => (
          <div key={entry.id} className={`log-entry log-${entry.kind}`}>
            {entry.badge && <div className="err-badge">{entry.badge}</div>}
            <div>{entry.text}</div>
          </div>
        ))}
        <div ref={logEndRef} />
      </div>

      <div className="chips-section">
        <span className="chips-label">Quick insert:</span>
        <div className="chips-list">
          {QUICK_CHIPS.map((item) => (
            <button
              key={item.label}
              type="button"
              className={`chip ${item.danger ? "chip-danger" : ""}`}
              onClick={() => {
                onInputChange(item.code);
                textareaRef.current?.focus();
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="editor-section">
        <div className="editor-meta">
          <span>Enter SplitLang command or multi-line script</span>
          <span>
            <kbd>Ctrl</kbd> + <kbd>Enter</kbd> to run &middot; <kbd>&uarr;</kbd>/<kbd>&darr;</kbd> history
          </span>
        </div>
        <div className="editor-row">
          <textarea
            ref={textareaRef}
            className="dsl-input"
            rows={5}
            spellCheck={false}
            value={inputCode}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='e.g. alice paid 120k + 30k * 2 for "Hotpot" split equally with tax 10%'
          />
          <button
            type="button"
            className="btn btn-primary run-btn"
            disabled={busy || !inputCode.trim()}
            onClick={() => onExecute(inputCode, true)}
          >
            <span>{busy ? "Running" : "Run DSL"}</span>
            <small>Ctrl+Enter</small>
          </button>
        </div>
      </div>
    </section>
  );
}
