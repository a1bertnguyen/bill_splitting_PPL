/**
 * Main Web Frontend controller for SplitLang.
 */

import { executeDSL, fetchState, runDemoScenario } from "./api.js";
import {
  appendConsoleBanner,
  appendConsoleCommand,
  appendConsoleExecution,
  renderDashboard,
  renderPPLInspector,
} from "./render.js";

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

const consoleLog = document.getElementById("consoleLog");
const dslInput = document.getElementById("dslInput");
const commandHistory = [];
let historyIdx = -1;

async function handleExecute(code, { clearInput = false } = {}) {
  const trimmed = code.trim();
  if (!trimmed) return;

  commandHistory.push(trimmed);
  historyIdx = commandHistory.length;

  appendConsoleCommand(consoleLog, trimmed);
  if (clearInput) dslInput.value = "";

  try {
    const data = await executeDSL(trimmed);
    const cleared = (data.execution.ops || []).some((op) => op.result && op.result.clear_ui);
    if (cleared) {
      consoleLog.innerHTML = "";
    } else {
      appendConsoleExecution(consoleLog, data.execution);
    }
    renderPPLInspector(data.execution);
    renderDashboard(data.state, { onMarkPaid: handleMarkPaid });
  } catch (err) {
    appendConsoleExecution(consoleLog, {
      ok: false,
      stage_failed: "semantic",
      messages: [String(err)],
    });
  }
}

function handleMarkPaid(fromMember, toMember, amount) {
  handleExecute(`${fromMember} pays ${toMember} ${amount}`);
}

function setupQuickChips() {
  const container = document.getElementById("quickChips");
  for (const item of QUICK_CHIPS) {
    const btn = document.createElement("button");
    btn.className = `chip ${item.danger ? "chip-danger" : ""}`;
    btn.textContent = item.label;
    btn.addEventListener("click", () => {
      dslInput.value = item.code;
      dslInput.focus();
    });
    container.appendChild(btn);
  }
}

function setupTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      tabBtns.forEach((b) => b.classList.toggle("active", b === btn));
      document.querySelectorAll(".tab-content").forEach((pane) => {
        pane.classList.toggle("active", pane.id === `tab-${target}`);
      });
    });
  });
}

function setupEvents() {
  document.getElementById("btnRun").addEventListener("click", () => {
    handleExecute(dslInput.value, { clearInput: true });
  });

  dslInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleExecute(dslInput.value, { clearInput: true });
    } else if (e.key === "ArrowUp" && !dslInput.value.includes("\n") && dslInput.selectionStart === 0) {
      if (historyIdx > 0) {
        historyIdx -= 1;
        dslInput.value = commandHistory[historyIdx];
      }
    } else if (e.key === "ArrowDown" && !dslInput.value.includes("\n")) {
      if (historyIdx < commandHistory.length - 1) {
        historyIdx += 1;
        dslInput.value = commandHistory[historyIdx];
      } else {
        historyIdx = commandHistory.length;
        dslInput.value = "";
      }
    }
  });

  document.getElementById("btnClearLog").addEventListener("click", () => {
    consoleLog.innerHTML = "";
  });

  document.getElementById("btnRunDemo").addEventListener("click", async () => {
    const demoName = document.getElementById("demoSelect").value;
    try {
      const data = await runDemoScenario(demoName);
      appendConsoleCommand(consoleLog, `/* Loaded demo: ${demoName} */\n${data.code.trim()}`);
      appendConsoleExecution(consoleLog, data.execution);
      renderPPLInspector(data.execution);
      renderDashboard(data.state, { onMarkPaid: handleMarkPaid });
    } catch (err) {
      appendConsoleExecution(consoleLog, {
        ok: false,
        stage_failed: "semantic",
        messages: [String(err)],
      });
    }
  });

  document.getElementById("groupSelect").addEventListener("change", (e) => {
    const selected = e.target.value;
    if (selected) {
      handleExecute(`use group "${selected}"`);
    }
  });

  document.getElementById("fileInput").addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    dslInput.value = await file.text();
    dslInput.focus();
    e.target.value = "";
  });

  document.getElementById("btnUndo").addEventListener("click", () => handleExecute("undo"));
  document.getElementById("btnHelp").addEventListener("click", () => handleExecute("help"));
  document.getElementById("btnReset").addEventListener("click", () => {
    if (window.confirm("Clear all members, expenses, and settlements in the active group?")) {
      handleExecute("reset");
    }
  });
}

async function init() {
  appendConsoleBanner(consoleLog);
  setupQuickChips();
  setupTabs();
  setupEvents();

  try {
    const state = await fetchState();
    renderDashboard(state, { onMarkPaid: handleMarkPaid });
  } catch (err) {
    appendConsoleExecution(consoleLog, {
      ok: false,
      stage_failed: "semantic",
      messages: [`Could not load initial state: ${err}`],
    });
  }
}

init();
