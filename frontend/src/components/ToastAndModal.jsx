import React from "react";
import { X } from "lucide-react";

export function ToastStack({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind === "err" ? "err" : ""}`}>
          <span style={{ flex: 1 }}>{t.message}</span>
          <button
            type="button"
            className="btn-ghost"
            style={{ padding: 2 }}
            onClick={() => onDismiss(t.id)}
            aria-label="Dismiss notification"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}

export function ConfirmModal({ open, title, message, confirmLabel = "Confirm", onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-box" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()}>
        <div className="card-head">
          <h2 className="t-h2">{title}</h2>
          <button type="button" className="btn-ghost" onClick={onCancel} aria-label="Close modal">
            <X size={16} />
          </button>
        </div>
        <p style={{ color: "var(--secondary)", marginBottom: 24 }}>{message}</p>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary btn-sm" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
