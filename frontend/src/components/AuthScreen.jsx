import React, { useEffect, useState } from "react";
import { Eye, EyeOff, Moon, RefreshCw, Sun } from "lucide-react";
import { api, setCsrfToken } from "../api/client";

export default function AuthScreen({ theme, onToggleTheme, onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [website, setWebsite] = useState("");
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

  const pwRules = [
    ["8+ chars", password.length >= 8],
    ["uppercase", /[A-Z]/.test(password)],
    ["lowercase", /[a-z]/.test(password)],
    ["number", /\d/.test(password)],
  ];

  return (
    <div className="auth-shell">
      <button
        type="button"
        className="btn btn-secondary btn-xs auth-theme-btn"
        onClick={onToggleTheme}
      >
        {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
        <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>
      </button>

      <div className="auth-left">
        <div>
          <div className="brand-lockup" style={{ marginBottom: 32 }}>
            <span className="brand-glyph">&gt;_</span>
            <span>splitlang</span>
          </div>

          <div className="t-label" style={{ marginBottom: 10 }}>
            // bill-splitting custom dsl · antlr 4.9.2 · mysql
          </div>
          <h1 className="t-display">
            Split bills fast.
            <br />
            Verify every cent.
          </h1>
          <p style={{ color: "var(--secondary)", maxWidth: 460, marginTop: 16 }}>
            Use the guided visual builder for everyday dinners and trips, or write SplitLang scripts
            directly and inspect Tokens, Parse Tree, and AST in real time.
          </p>

          <div className="auth-spec-box">
            <div className="auth-spec-bar">
              <span className="t-label">saigon_weekend.split</span>
              <span className="t-label">deterministic math</span>
            </div>
            <div className="auth-spec-code">
              <span className="k">bill</span> "BBQ Night" <span className="k">paid by</span> alice{" "}
              {"{\n"}
              {"    "}
              <span className="k">item</span> "Wagyu Beef" 480k <span className="k">for all</span>
              {"\n    "}
              <span className="k">item</span> "Craft Beer" 240k <span className="k">for</span> alice, bob
              {"\n    "}
              <span className="k">discount</span> 60k; <span className="k">tax</span> 10%;{" "}
              <span className="k">tip</span> 5%{"\n}\n"}
              <span className="k">settle up</span>{" "}
              <span className="c">// Greedy Minimum Cash Flow</span>
            </div>
          </div>
        </div>

        <div className="t-label">
          Argon2id · HttpOnly + CSRF · Fernet AES · Row-Level MySQL Isolation
        </div>
      </div>

      <div className="auth-right">
        <div className="auth-panel">
          <div>
            <div className="t-label" style={{ marginBottom: 4 }}>// account</div>
            <h2 className="t-h1">{mode === "login" ? "Sign in" : "Create account"}</h2>
          </div>

          <div className="composer-tabs" style={{ marginBottom: 0 }}>
            <button
              type="button"
              className={`composer-tab ${mode === "login" ? "active" : ""}`}
              onClick={() => {
                setError("");
                setMode("login");
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`composer-tab ${mode === "register" ? "active" : ""}`}
              onClick={() => {
                setError("");
                setMode("register");
              }}
            >
              Register
            </button>
          </div>

          {error && (
            <div className="dsl-preview" style={{ borderColor: "var(--primary)" }}>
              [error] {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label className="field-label" htmlFor="a-user">Username</label>
              <input
                id="a-user"
                className="input"
                type="text"
                autoComplete="username"
                autoFocus
                required
                minLength={3}
                maxLength={32}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="quangminh"
              />
            </div>

            {mode === "register" && (
              <div>
                <label className="field-label" htmlFor="a-email">Email (optional)</label>
                <input
                  id="a-email"
                  className="input"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@domain.example"
                />
              </div>
            )}

            <div>
              <label className="field-label" htmlFor="a-pw">Password</label>
              <div className="pw-wrap">
                <input
                  id="a-pw"
                  className="input"
                  style={{ paddingRight: 38 }}
                  type={showPw ? "text" : "password"}
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                  required
                  minLength={mode === "register" ? 8 : 1}
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  className="pw-eye"
                  onClick={() => setShowPw((v) => !v)}
                  aria-label="Toggle password visibility"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {mode === "register" && (
                <div className="pw-checks">
                  {pwRules.map(([label, ok]) => (
                    <span key={label} className={ok ? "met" : ""}>
                      {ok ? "✓" : "○"} {label}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="honeypot" aria-hidden="true">
              <input
                type="text"
                tabIndex={-1}
                autoComplete="off"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
              />
            </div>

            <div>
              <label className="field-label" htmlFor="a-bot">Quick verification</label>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div
                  className="mono"
                  style={{
                    padding: "9px 12px",
                    backgroundColor: "var(--neutral)",
                    border: "1px solid var(--line-strong)",
                    borderRadius: "var(--r-md)",
                    whiteSpace: "nowrap",
                    fontSize: "0.86rem",
                  }}
                >
                  {challenge.question} = ?
                </div>
                <input
                  id="a-bot"
                  className="input mono"
                  type="text"
                  inputMode="numeric"
                  required
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  placeholder="Answer"
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ padding: "9px 10px" }}
                  onClick={loadChallenge}
                  aria-label="Refresh verification"
                >
                  <RefreshCw size={14} />
                </button>
              </div>
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={loading}>
              {loading ? "Checking..." : mode === "register" ? "Create Account" : "Sign In"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
