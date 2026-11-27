import React from "react";

const NUM_TYPES = new Set(["NUMBER", "MONEY_K", "MONEY_M", "MONEY_USD", "PERCENT_LIT", "DATE"]);
const OP_TYPES = new Set(["PLUS", "MINUS", "STAR", "SLASH"]);
const PUNCT_TYPES = new Set([
  "LPAREN",
  "RPAREN",
  "LBRACE",
  "RBRACE",
  "COMMA",
  "COLON",
  "SEMI",
  "QUESTIONMARK",
  "NEWLINE",
]);

function tokenClass(type) {
  if (type === "ID") return "tok-id";
  if (type === "STRING") return "tok-str";
  if (NUM_TYPES.has(type)) return "tok-num";
  if (OP_TYPES.has(type)) return "tok-op";
  if (PUNCT_TYPES.has(type)) return "tok-punct";
  return "tok-kw";
}

function stageStatus(execution, num) {
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

const STAGES = [
  [1, "Input"],
  [2, "Lexer"],
  [3, "Parser"],
  [4, "Visitor & AST"],
  [5, "Action & DB"],
];

export default function PPLInspectorTab({ execution }) {
  const tokens = (execution?.tokens || []).filter((t) => t.type !== "NEWLINE");

  return (
    <div className="tab-content">
      <div className="pipeline-stepper">
        {STAGES.map(([num, label], i) => (
          <React.Fragment key={num}>
            <div className={`stage-step ${stageStatus(execution, num)}`}>
              <span className="stage-num">{num}</span> {label}
            </div>
            {i < STAGES.length - 1 && <div className="stage-arrow">&rarr;</div>}
          </React.Fragment>
        ))}
      </div>

      <div className="inspector-card">
        <div className="inspector-header">
          <span>Stage 2 &middot; Lexical Analysis (SplitLangLexer Tokens)</span>
          <span className="mini-pill">{tokens.length} tokens</span>
        </div>
        <div className="tokens-grid">
          {tokens.length === 0 ? (
            <div className="empty-muted">Run any SplitLang command to inspect tokens.</div>
          ) : (
            tokens.map((t, idx) => (
              <span
                key={idx}
                className={`token-pill ${tokenClass(t.type)}`}
                title={`Line ${t.line}, Col ${t.column}`}
              >
                <span className="token-type">{t.type}</span>
                <span>{t.text}</span>
              </span>
            ))
          )}
        </div>
      </div>

      <div className="inspector-grid">
        <div className="inspector-card">
          <div className="inspector-header">
            <span>Stage 3 &middot; Concrete Parse Tree (SplitLangParser)</span>
          </div>
          <pre className="code-box">{execution?.parse_tree || "(no parse tree yet)"}</pre>
        </div>

        <div className="inspector-card">
          <div className="inspector-header">
            <span>Stage 4 &middot; Abstract Syntax Tree (Distilled Op Nodes)</span>
          </div>
          <pre className="code-box ast-box">{execution?.ast_tree || "(no AST yet)"}</pre>
        </div>
      </div>
    </div>
  );
}
