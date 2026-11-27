import React, { useEffect, useState } from "react";
import { api, setCsrfToken } from "./api/client";
import AuthScreen from "./components/AuthScreen.jsx";
import PlaygroundPage from "./components/PlaygroundPage.jsx";
import { ConfirmModal, ToastStack } from "./components/ToastAndModal.jsx";
import TopNav from "./components/TopNav.jsx";
import WorkspacePage from "./components/WorkspacePage.jsx";

let logSeq = 1;
let toastSeq = 1;

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem("splitlang_theme") || "dark");
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [state, setState] = useState(null);
  const [mode, setMode] = useState("workspace"); // "workspace" | "playground"
  const [code, setCode] = useState("");
  const [logs, setLogs] = useState([]);
  const [lastExecution, setLastExecution] = useState(null);
  const [busy, setBusy] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("splitlang_theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  const notify = (kind, message) => {
    const id = toastSeq++;
    setToasts((prev) => [...prev, { id, kind, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  };

  const pushLog = (kind, text, badge = null) => {
    setLogs((prev) => [...prev, { id: logSeq++, kind, text, badge }]);
  };

  useEffect(() => {
    (async () => {
      try {
        const me = await api.getMe();
        setCsrfToken(me.csrf_token);
        setUser(me.user);
        setState(await api.getState());
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
    setState(await api.getState());
    notify("ok", `Signed in as ${authedUser.username}`);
  };

  const handleExecute = async (sourceCode) => {
    const trimmed = sourceCode.trim();
    if (!trimmed) return;
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
          ? "Stage 02/03 · Lexer / Parser Rejected"
          : "Stage 05 · Semantic Validation Error";
        pushLog(data.execution.ok ? "ok" : "err", data.execution.messages.join("\n"), badge);
        notify(data.execution.ok ? "ok" : "err", data.execution.messages[0].split("\n")[0]);
      }
    } catch (err) {
      if (err.status === 401) {
        setUser(null);
        return;
      }
      pushLog("err", err.message, "API Error");
      notify("err", err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleRunDemo = async (demoName) => {
    setBusy(true);
    try {
      const data = await api.runDemo(demoName);
      pushLog("cmd", `/* Demo: ${demoName} */\n${data.code.trim()}`);
      pushLog(data.execution.ok ? "ok" : "err", (data.execution.messages || []).join("\n"));
      setLastExecution(data.execution);
      setState(data.state);
      notify("ok", `Loaded '${data.state.group.name}' (${data.state.expense_count} expenses)`);
    } catch (err) {
      notify("err", err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleSelectGroup = async (groupId) => {
    try {
      const s = await api.selectGroup(groupId);
      setState(s);
      notify("ok", `Switched to '${s.group.name}' (${s.currency})`);
    } catch (err) {
      notify("err", err.message);
    }
  };

  const handleCreateGroup = async (name, currency) => {
    const safe = name.replaceAll('"', '\\"');
    await handleExecute(`group "${safe}"\ncurrency ${currency}`);
  };

  const handleUploadFile = async (file) => {
    try {
      const res = await api.uploadSplitFile(file);
      setCode(res.code);
      setMode("playground");
      notify("ok", `Loaded '${res.filename}' (${res.size_bytes} bytes)`);
    } catch (err) {
      notify("err", err.message);
    }
  };

  const handleInspectInPlayground = async (dsl) => {
    setCode(dsl);
    setMode("playground");
    await handleExecute(dsl);
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

  if (checkingAuth) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <span className="t-label">Loading splitlang...</span>
      </div>
    );
  }

  if (!user) {
    return (
      <>
        <AuthScreen theme={theme} onToggleTheme={toggleTheme} onAuthenticated={handleAuthenticated} />
        <ToastStack toasts={toasts} onDismiss={(id) => setToasts((p) => p.filter((t) => t.id !== id))} />
      </>
    );
  }

  return (
    <div>
      <TopNav
        user={user}
        state={state}
        mode={mode}
        onModeChange={setMode}
        onSelectGroup={handleSelectGroup}
        onCreateGroup={handleCreateGroup}
        onUndo={() => handleExecute("undo")}
        onOpenReset={() => setResetOpen(true)}
        theme={theme}
        onToggleTheme={toggleTheme}
        onLogout={handleLogout}
      />

      <main className="wrap page-main">
        {mode === "workspace" ? (
          <WorkspacePage
            state={state}
            busy={busy}
            onExecute={handleExecute}
            onRunDemo={handleRunDemo}
            onInspectInPlayground={handleInspectInPlayground}
          />
        ) : (
          <PlaygroundPage
            code={code}
            onCodeChange={setCode}
            logs={logs}
            onClearLogs={() => setLogs([])}
            onExecute={handleExecute}
            onUploadFile={handleUploadFile}
            lastExecution={lastExecution}
            busy={busy}
          />
        )}
      </main>

      <ConfirmModal
        open={resetOpen}
        title={`Reset "${state?.group?.name || "Group"}"?`}
        message="This clears all members, expenses, bills, and repayments in the active group."
        confirmLabel="Reset Group"
        onCancel={() => setResetOpen(false)}
        onConfirm={() => {
          setResetOpen(false);
          handleExecute("reset");
        }}
      />

      <ToastStack
        toasts={toasts}
        onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))}
      />
    </div>
  );
}
