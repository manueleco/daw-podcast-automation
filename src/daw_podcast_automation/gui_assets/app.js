const state = {
  outputPath: "",
  processRunning: false,
  generalLogPath: "",
  errorLogPath: "",
};

const els = {
  projectPath: document.getElementById("project-path"),
  outputPath: document.getElementById("output-path"),
  profileSelect: document.getElementById("profile-select"),
  modeSelect: document.getElementById("mode-select"),
  openInLogic: document.getElementById("open-in-logic"),
  trackPath: document.getElementById("track-path"),
  trackReport: document.getElementById("track-report"),
  windowSeconds: document.getElementById("window-seconds"),
  deltaDb: document.getElementById("delta-db"),
  silenceTopDb: document.getElementById("silence-top-db"),
  runtimePill: document.getElementById("runtime-pill"),
  pythonPill: document.getElementById("python-pill"),
  logSurface: document.getElementById("log-surface"),
  pickProject: document.getElementById("pick-project"),
  pickOutput: document.getElementById("pick-output"),
  pickTrack: document.getElementById("pick-track"),
  runSession: document.getElementById("run-session"),
  openOutput: document.getElementById("open-output"),
  analyzeTrack: document.getElementById("analyze-track"),
  clearLog: document.getElementById("clear-log"),
};

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  await hydrateInitialState();
  addLogLine("Listo. La app ya puede correr sesiones y generar analisis con segmentos, marcadores y automation draft.", "stage");
  addLogLine(`Logs: ${state.generalLogPath}`, "stage");
});

function bindEvents() {
  els.pickProject.addEventListener("click", async () => {
    const selected = await window.pywebview.api.pick_logic_project();
    if (selected) {
      els.projectPath.value = selected;
      if (!els.outputPath.value) {
        els.outputPath.value = state.outputPath;
      }
    }
  });

  els.pickOutput.addEventListener("click", async () => {
    const selected = await window.pywebview.api.pick_output_folder();
    if (selected) {
      els.outputPath.value = selected;
      state.outputPath = selected;
    }
  });

  els.pickTrack.addEventListener("click", async () => {
    const selected = await window.pywebview.api.pick_audio_track();
    if (selected) {
      els.trackPath.value = selected;
      if (!els.trackReport.value) {
        els.trackReport.value = selected.replace(/\.[^.]+$/, "__analysis.json");
      }
    }
  });

  els.runSession.addEventListener("click", async () => {
    try {
      addLogLine("Lanzando session run...", "stage");
      await window.pywebview.api.run_session({
        source: els.projectPath.value,
        output_root: els.outputPath.value,
        profile: els.profileSelect.value || "podcast-stereo",
        mode: els.modeSelect.value,
        open_in_logic: els.openInLogic.checked,
      });
    } catch (error) {
      addLogLine(String(error), "error");
    }
  });

  els.openOutput.addEventListener("click", async () => {
    try {
      await window.pywebview.api.open_path(els.outputPath.value);
    } catch (error) {
      addLogLine(String(error), "error");
    }
  });

  els.analyzeTrack.addEventListener("click", async () => {
    try {
      addLogLine("Lanzando analyze-track...", "stage");
      await window.pywebview.api.analyze_audio_track({
        source: els.trackPath.value,
        report: els.trackReport.value,
        profile: els.profileSelect.value || "podcast-stereo",
        window_seconds: els.windowSeconds.value,
        delta_db: els.deltaDb.value,
        silence_top_db: els.silenceTopDb.value,
      });
    } catch (error) {
      addLogLine(String(error), "error");
    }
  });

  els.clearLog.addEventListener("click", () => {
    els.logSurface.innerHTML = "";
  });
}

async function hydrateInitialState() {
  const initial = await window.pywebview.api.get_initial_state();
  state.outputPath = initial.default_output_root;
  state.generalLogPath = initial.general_log_path;
  state.errorLogPath = initial.error_log_path;
  els.outputPath.value = initial.default_output_root;
  els.pythonPill.textContent = initial.python_label;
  for (const profile of initial.profiles) {
    const option = document.createElement("option");
    option.value = profile;
    option.textContent = profile;
    els.profileSelect.appendChild(option);
  }
  els.profileSelect.value = initial.default_profile;
}

function setProcessRunning(isRunning) {
  state.processRunning = isRunning;
  for (const element of [els.runSession, els.analyzeTrack, els.pickProject, els.pickOutput, els.pickTrack]) {
    element.disabled = isRunning;
  }
}

function addLogLine(text, kind = "") {
  const line = document.createElement("div");
  line.className = `log-line ${kind}`.trim();
  line.textContent = text;
  els.logSurface.appendChild(line);
  els.logSurface.scrollTop = els.logSurface.scrollHeight;
}

window.onProcessLine = (payload) => {
  const text = payload.line || "";
  let kind = "";
  if (text.startsWith("[stage:")) {
    kind = "stage";
  } else if (text.startsWith("error:")) {
    kind = "error";
  }
  addLogLine(text, kind);
};

window.onProcessState = (payload) => {
  if (payload.status === "running") {
    setProcessRunning(true);
    els.runtimePill.textContent = "Running";
    els.runtimePill.className = "pill pill-running";
    if (payload.session_log_path) {
      addLogLine(`Session log: ${payload.session_log_path}`, "stage");
    }
  } else if (payload.status === "success") {
    setProcessRunning(false);
    els.runtimePill.textContent = "Done";
    els.runtimePill.className = "pill pill-success";
    addLogLine(payload.message || "Proceso terminado.", "stage");
    if (payload.session_log_path) {
      addLogLine(`Session log: ${payload.session_log_path}`, "stage");
    }
  } else if (payload.status === "error") {
    setProcessRunning(false);
    els.runtimePill.textContent = "Needs attention";
    els.runtimePill.className = "pill pill-warning";
    addLogLine(payload.message || "Proceso terminado con error.", "error");
    if (payload.session_log_path) {
      addLogLine(`Session log: ${payload.session_log_path}`, "error");
    }
    if (state.errorLogPath) {
      addLogLine(`Error log: ${state.errorLogPath}`, "error");
    }
  } else {
    setProcessRunning(false);
    els.runtimePill.textContent = "Listo";
    els.runtimePill.className = "pill pill-success";
  }
};
