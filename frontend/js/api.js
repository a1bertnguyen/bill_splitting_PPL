/**
 * API client module for communicating with the SplitLang FastAPI backend.
 */

export async function fetchState() {
  const res = await fetch("/api/state");
  if (!res.ok) throw new Error(`Failed to fetch state (${res.status})`);
  return res.json();
}

export async function executeDSL(code) {
  const res = await fetch("/api/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) throw new Error(`Execution request failed (${res.status})`);
  return res.json();
}

export async function runDemoScenario(name) {
  const res = await fetch("/api/demo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`Demo request failed (${res.status})`);
  return res.json();
}
