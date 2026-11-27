import React, { useEffect, useState } from "react";
import { api, setCsrfToken } from "../api/client";

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [website, setWebsite] = useState(""); // Honeypot (must stay empty)
  const [challenge, setChallenge] = useState({ challenge_token: "", question: "..." });
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadChallenge = async () => {
    try {
      const ch = await api.getChallenge();
      setChallenge(ch);
      setAnswer("");
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadChallenge();
  }, [mode]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const payload =
        mode === "register"
          ? {
              username,
              email: email.trim() || null,
              password,
              website,
              challenge_token: challenge.challenge_token,
              challenge_answer: answer,
            }
          : {
              username,
              password,
              website,
              challenge_token: challenge.challenge_token,
              challenge_answer: answer,
            };

      const res = mode === "register" ? await api.register(payload) : await api.login(payload);
      setCsrfToken(res.csrf_token);
      onAuthenticated(res.user);
    } catch (err) {
      setError(err.message);
      await loadChallenge();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="brand">
          <div className="brand-logo">SL</div>
          <div>
            <div className="brand-title">SplitLang</div>
            <div className="brand-sub">Secure Bill-Splitting DSL &middot; React + MySQL + ANTLR 4.9.2</div>
          </div>
        </div>

        <div className="auth-tabs">
          <button
            type="button"
            className={`auth-tab ${mode === "login" ? "active" : ""}`}
            onClick={() => {
              setError("");
              setMode("login");
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            className={`auth-tab ${mode === "register" ? "active" : ""}`}
            onClick={() => {
              setError("");
              setMode("register");
            }}
          >
            Create Account
          </button>
        </div>

        {error && <div className="alert-err">{error}</div>}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="form-group">
            <label htmlFor="auth-username">Username</label>
            <input
              id="auth-username"
              className="form-input"
              type="text"
              autoComplete="username"
              required
              minLength={3}
              maxLength={32}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. minh_nguyen"
            />
          </div>

          {mode === "register" && (
            <div className="form-group">
              <label htmlFor="auth-email">Email (optional, encrypted at rest)</label>
              <input
                id="auth-email"
                className="form-input"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="auth-password">
              Password {mode === "register" ? "(8+ chars, upper, lower, digit)" : ""}
            </label>
            <input
              id="auth-password"
              className="form-input"
              type="password"
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              required
              minLength={mode === "register" ? 8 : 1}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {/* Control #12: Hidden honeypot field to trap automated bots */}
          <div className="honeypot-field" aria-hidden="true">
            <label htmlFor="auth-website">Website</label>
            <input
              id="auth-website"
              type="text"
              tabIndex={-1}
              autoComplete="off"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
            />
          </div>

          {/* Control #12: Signed single-use human verification challenge */}
          <div className="form-group">
            <label htmlFor="auth-challenge">Anti-Bot Verification</label>
            <div className="challenge-box">
              <div>
                Solve: <span className="challenge-q">{challenge.question} = ?</span>
              </div>
              <button type="button" className="btn-ghost" onClick={loadChallenge}>
                New
              </button>
            </div>
            <input
              id="auth-challenge"
              className="form-input"
              type="text"
              inputMode="numeric"
              required
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Enter result"
            />
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading
              ? "Verifying..."
              : mode === "register"
              ? "Create Account & Sign In"
              : "Sign In"}
          </button>
        </form>

        <div className="security-badges">
          <span className="sec-pill">Argon2id</span>
          <span className="sec-pill">HttpOnly + CSRF</span>
          <span className="sec-pill">Fernet AES</span>
          <span className="sec-pill">Row-Level Auth</span>
          <span className="sec-pill">Rate Limited</span>
        </div>
      </div>
    </div>
  );
}
