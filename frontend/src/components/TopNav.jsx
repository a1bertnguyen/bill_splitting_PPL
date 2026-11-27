import React, { useState } from "react";
import { LayoutGrid, LogOut, Moon, Plus, RotateCcw, Sun, Terminal, Trash2, X } from "lucide-react";

const CURRENCIES = ["VND", "USD", "EUR", "JPY", "GBP", "SGD"];

export default function TopNav({
  user,
  state,
  mode,
  onModeChange,
  onSelectGroup,
  onCreateGroup,
  onUndo,
  onOpenReset,
  theme,
  onToggleTheme,
  onLogout,
}) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCur, setNewCur] = useState("VND");

  const handleCreate = (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    onCreateGroup(newName.trim(), newCur);
    setNewName("");
    setCreating(false);
  };

  return (
    <header className="topnav">
      <div className="wrap topnav-inner">
        <div className="brand-lockup">
          <span className="brand-glyph">&gt;_</span>
          <span>splitlang</span>
        </div>

        {/* Simple 2-Mode Switcher — no 4-page maze */}
        <div className="mode-switch" role="tablist" aria-label="Workspace mode">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "workspace"}
            className={`mode-btn ${mode === "workspace" ? "active" : ""}`}
            onClick={() => onModeChange("workspace")}
          >
            <LayoutGrid size={14} />
            <span>Workspace</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "playground"}
            className={`mode-btn ${mode === "playground" ? "active" : ""}`}
            onClick={() => onModeChange("playground")}
          >
            <Terminal size={14} />
            <span>DSL &amp; PPL Inspector</span>
          </button>
        </div>

        <div className="topnav-right">
          <div className="group-switcher">
            <select
              value={state?.group?.id || ""}
              onChange={(e) => onSelectGroup(Number(e.target.value))}
              aria-label="Active group"
            >
              {(state?.groups || []).map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name} ({g.currency})
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn-ghost"
              style={{ padding: 4, borderRadius: "var(--r-sm)" }}
              onClick={() => setCreating((v) => !v)}
              title="New group"
              aria-label="Create new group"
            >
              {creating ? <X size={14} /> : <Plus size={14} />}
            </button>
          </div>

          <button
            type="button"
            className="btn btn-secondary btn-xs"
            onClick={onUndo}
            title="Undo last expense or settlement"
          >
            <RotateCcw size={13} />
            <span>Undo</span>
          </button>

          <button
            type="button"
            className="btn btn-ghost btn-xs"
            onClick={onOpenReset}
            title="Reset active group"
            aria-label="Reset active group"
          >
            <Trash2 size={14} />
          </button>

          <button
            type="button"
            className="btn btn-secondary btn-xs"
            onClick={onToggleTheme}
            title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
            aria-label="Toggle light and dark theme"
          >
            {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
            <span>{theme === "dark" ? "Light" : "Dark"}</span>
          </button>

          <button
            type="button"
            className="btn btn-ghost btn-xs"
            onClick={onLogout}
            title={`Sign out (${user?.username})`}
            aria-label="Sign out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>

      {creating && (
        <div style={{ borderTop: "1px solid var(--line)", backgroundColor: "var(--surface)" }}>
          <form
            className="wrap"
            onSubmit={handleCreate}
            style={{ display: "flex", alignItems: "center", gap: 10, paddingTop: 10, paddingBottom: 10 }}
          >
            <span className="t-label">New group:</span>
            <input
              className="input"
              style={{ maxWidth: 240, padding: "6px 10px" }}
              placeholder="e.g. Da Lat Trip"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              autoFocus
            />
            <select
              className="select-input"
              style={{ width: 92, padding: "6px 8px" }}
              value={newCur}
              onChange={(e) => setNewCur(e.target.value)}
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <button type="submit" className="btn btn-secondary btn-sm">
              Create
            </button>
          </form>
        </div>
      )}
    </header>
  );
}
