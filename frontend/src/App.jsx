import React, { useEffect, useState } from "react";
import { api, setCsrfToken } from "./api/client";
import AuthScreen from "./components/AuthScreen.jsx";
import BalancesTab from "./components/BalancesTab.jsx";
import ConsolePanel from "./components/ConsolePanel.jsx";
import ExpensesTab from "./components/ExpensesTab.jsx";
import HeaderBar from "./components/HeaderBar.jsx";
import PPLInspectorTab from "./components/PPLInspectorTab.jsx";

let nextLogId = 1;

export default function App() {
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [state, setState] = useState(null);
  const [activeTab, setActiveTab] = useState("balances");
  const [demoName, setDemoName] = useState("dinner");
  const [inputCode, setInputCode] = useState("");
  const [logs, setLogs] = useState([]);
  const [lastExecution, setLastExecution] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyIdx, setHistoryIdx] = useState(0);
  const [busy, setBusy] = useState(false);

  const pushLog = (kind, text, badge = null) => {
    setLogs((prev) => [...prev, { id: nextLogId++, kind, text, badge }]);
  };

  const refreshState = async () => {
    const s = await api.getState();
    setState(s);
  };

  useEffect(() => {
    (async () => {
      try {
        const me = await api.getMe();
        setCsrfToken(me.csrf_token);
        setUser(me.user);
        const s = await api.getState();
        setState(s);
      } catch {
        setUser(null);
      } finally {
        setCheckingAuth(false);
      }
    })();
  }, []);

  const handleAuthenticated = async (authedUser) => {
    setUser(authedUser);
    setLogs([]);
    setLastExecution(null);
    await refreshState();
  };

  const handleExecute = async (code, clearInput = false) => {
    const trimmed = code.trim();
    if (!trimmed) return;

    setHistory((prev) => {
      const next = [...prev, trimmed];
      setHistoryIdx(next.length);
      return next;
    });
    if (clearInput) setInputCode("");
    pushLog("cmd", `>>> ${trimmed}`);
    setBusy(true);

    try {
      const data = await api.execute(trimmed);
      setLastExecution(data.execution);
      setState(data.state);

      const cleared = (data.execution.ops || []).some((op) => op.result && op.result.clear_ui);
      if (cleared) {
        setLogs([]);
      } else if (data.execution.messages?.length) {
        const badge = data.execution.ok
          ? null
          : data.execution.stage_failed === "lexer_parser"
          ? "Stage 2/3 · Lexer / Parser Rejected"
          : "Stage 5 · Semantic Validation Error";
        pushLog(data.execution.ok ? "ok" : "err", data.execution.messages.join("\n"), badge);
      }
    } catch (err) {
      if (err.status === 401) {
        setUser(null);
        return;
      }
      pushLog("err", err.message, "Request Error");
    } finally {
      setBusy(false);
    }
  };

  const handleRunDemo = async () => {
    setBusy(true);
    try {
      const data = await api.runDemo(demoName);
      pushLog("cmd", `/* Loaded demo: ${demoName} */\n${data.code.trim()}`);
      pushLog(
        data.execution.ok ? "ok" : "err",
        (data.execution.messages || []).join("\n")
      );
      setLastExecution(data.execution);
      setState(data.state);
    } catch (err) {
      pushLog("err", err.message, "Demo Error");
    } finally {
      setBusy(false);
    }
  };

  const handleSelectGroup = async (groupId) => {
    try {
      const s = await api.selectGroup(groupId);
      setState(s);
      pushLog("ok", `Switched to group '${s.group.name}' (${s.currency}).`);
    } catch (err) {
      pushLog("err", err.message, "Access Error");
    }
  };

  const handleUploadFile = async (file) => {
    try {
      const res = await api.uploadSplitFile(file);
      setInputCode(res.code);
      pushLog("ok", `Loaded '${res.filename}' (${res.size_bytes} bytes) into editor.`);
    } catch (err) {
      pushLog("err", err.message, "Upload Blocked");
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch {
      // ignore
    }
    setCsrfToken("");
    setUser(null);
    setState(null);
    setLogs([]);
  };

  const handleHistoryNav = (nextIdx) => {
    setHistoryIdx(nextIdx);
    setInputCode(nextIdx < history.length ? history[nextIdx] : "");
  };

  if (checkingAuth) {
    return (
      <div className="auth-page">
        <div className="empty-muted">Loading SplitLang...</div>
      </div>
    );
  }

  if (!user) {
    return <AuthScreen onAuthenticated={handleAuthenticated} />;
  }

  return (
    <div className="app-shell">
      <HeaderBar
        user={user}
        state={state}
        demoName={demoName}
        onDemoNameChange={setDemoName}
        onRunDemo={handleRunDemo}
        onSelectGroup={handleSelectGroup}
        onUploadFile={handleUploadFile}
        onUndo={() => handleExecute("undo")}
        onHelp={() => handleExecute("help")}
        onReset={() => {
          if (window.confirm("Clear all members, expenses, and settlements in the active group?")) {
            handleExecute("reset");
          }
        }}
        onLogout={handleLogout}
      />

      <main className="workspace">
        <ConsolePanel
          logs={logs}
          inputCode={inputCode}
          onInputChange={setInputCode}
          onExecute={handleExecute}
          onClearLogs={() => setLogs([])}
          history={history}
          historyIdx={historyIdx}
          onHistoryNav={handleHistoryNav}
          busy={busy}
        />

        <section className="panel dashboard-panel">
          <nav className="tabs-bar" role="tablist">
            <button
              type="button"
              className={`tab-btn ${activeTab === "balances" ? "active" : ""}`}
              onClick={() => setActiveTab("balances")}
            >
              Balances &amp; Settle Up
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "expenses" ? "active" : ""}`}
              onClick={() => setActiveTab("expenses")}
            >
              Expenses &amp; Bills{" "}
              <span className="tab-badge">{state?.expense_count || 0}</span>
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === "ppl" ? "active" : ""}`}
              onClick={() => setActiveTab("ppl")}
            >
              PPL Inspector <span className="tab-badge badge-indigo">5 Stages</span>
            </button>
          </nav>

          {activeTab === "balances" && (
            <BalancesTab
              state={state}
              onMarkPaid={(from, to, amt) => handleExecute(`${from} pays ${to} ${amt}`)}
            />
          )}
          {activeTab === "expenses" && <ExpensesTab expenses={state?.expenses || []} />}
          {activeTab === "ppl" && <PPLInspectorTab execution={lastExecution} />}
        </section>
      </main>
    </div>
  );
}
