import React, { useRef } from "react";

export default function HeaderBar({
  user,
  state,
  demoName,
  onDemoNameChange,
  onRunDemo,
  onSelectGroup,
  onUploadFile,
  onUndo,
  onHelp,
  onReset,
  onLogout,
}) {
  const fileRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      onUploadFile(file);
    }
    e.target.value = "";
  };

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-logo">SL</div>
        <div>
          <div className="brand-title">SplitLang</div>
          <div className="brand-sub">
            Bill-Splitting Custom DSL &middot; React + MySQL + ANTLR 4.9.2
          </div>
        </div>
      </div>

      <div className="topbar-actions">
        <div className="group-picker">
          <span className="group-picker-label">Group</span>
          <select
            value={state?.group?.id || ""}
            onChange={(e) => onSelectGroup(Number(e.target.value))}
            title="Switch active group"
          >
            {(state?.groups || []).map((g) => (
              <option key={g.id} value={g.id}>
                {g.name} ({g.member_count})
              </option>
            ))}
          </select>
          <span className="currency-pill">{state?.currency || "VND"}</span>
        </div>

        <div className="demo-dropdown">
          <select
            value={demoName}
            onChange={(e) => onDemoNameChange(e.target.value)}
            title="Select demo scenario"
          >
            <option value="dinner">Saigon Weekend (VND)</option>
            <option value="trip">Tokyo Trip (USD)</option>
          </select>
          <button type="button" className="btn btn-emerald" onClick={onRunDemo}>
            Run Demo
          </button>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => fileRef.current?.click()}
        >
          Open .split
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".split"
          hidden
          onChange={handleFileChange}
        />

        <button type="button" className="btn btn-secondary" onClick={onUndo}>
          Undo
        </button>
        <button type="button" className="btn btn-secondary" onClick={onHelp}>
          Help
        </button>
        <button type="button" className="btn btn-danger" onClick={onReset}>
          Reset
        </button>

        <div className="user-chip">
          <span className="avatar">{(user?.username || "U").slice(0, 2)}</span>
          <span style={{ fontSize: 12, fontWeight: 600 }}>{user?.username}</span>
          <button type="button" className="btn-ghost" onClick={onLogout}>
            Sign Out
          </button>
        </div>
      </div>
    </header>
  );
}
