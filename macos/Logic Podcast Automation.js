ObjC.import("Foundation");

const app = Application.currentApplication();
app.includeStandardAdditions = true;

function run() {
  try {
    const repoRoot = getRepoRoot();
    const pythonPath = repoRoot + "/.venv/bin/python";
    const launchCommand =
      "cd " +
      shellQuote(repoRoot) +
      " && PYTHONPATH=src " +
      shellQuote(pythonPath) +
      " -m daw_podcast_automation.gui >/tmp/logic-podcast-automation-gui.log 2>&1 &";

    app.doShellScript(launchCommand);
  } catch (error) {
    const message = [
      "No se pudo abrir la app.",
      "",
      error.message || String(error),
    ].join("\n");
    app.displayDialog(message, {
      withTitle: "Logic Podcast Automation",
      buttons: ["Cerrar"],
      defaultButton: "Cerrar",
    });
  }
}

function getRepoRoot() {
  const bundlePath = ObjC.unwrap($.NSBundle.mainBundle.bundlePath);
  return dirname(bundlePath);
}

function dirname(inputPath) {
  return app.doShellScript("dirname " + shellQuote(inputPath));
}

function shellQuote(value) {
  return "'" + String(value).replace(/'/g, "'\"'\"'") + "'";
}
