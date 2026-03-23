ObjC.import("Foundation");

const app = Application.currentApplication();
app.includeStandardAdditions = true;

function run() {
  const repoRoot = getRepoRoot();
  const sourceProject = promptForProject();
  if (!sourceProject) {
    return;
  }

  const baseOutputFolder = dirname(sourceProject);
  const outputFolder = promptForOutput(baseOutputFolder);
  if (!outputFolder) {
    return;
  }

  const profileName = promptForProfile();
  if (!profileName) {
    return;
  }

  const introText =
    "Se va a crear una copia de trabajo, abrir Logic Pro, hacer bounce, medir loudness y generar un master corregido.";
  const confirmation = app.displayDialog(introText, {
    withTitle: "DAW Podcast Automation",
    buttons: ["Cancelar", "Continuar"],
    defaultButton: "Continuar",
  });
  if (confirmation.buttonReturned !== "Continuar") {
    return;
  }

  const shellCommand =
    "cd " +
    shellQuote(repoRoot) +
    " && PYTHONPATH=src python3 -m daw_podcast_automation run --source " +
    shellQuote(sourceProject) +
    " --profile " +
    shellQuote(profileName) +
    " --output-root " +
    shellQuote(outputFolder);

  try {
    const commandOutput = app.doShellScript(shellCommand);
    const finalResult = app.displayDialog("Proceso terminado.\n\n" + commandOutput, {
      withTitle: "DAW Podcast Automation",
      buttons: ["Cerrar", "Abrir carpeta"],
      defaultButton: "Abrir carpeta",
    });
    if (finalResult.buttonReturned === "Abrir carpeta") {
      app.doShellScript("open " + shellQuote(outputFolder));
    }
  } catch (error) {
    const message = [
      "No se pudo terminar el proceso.",
      "",
      error.message || String(error),
    ].join("\n");
    app.displayDialog(message, {
      withTitle: "DAW Podcast Automation",
      buttons: ["Cerrar"],
      defaultButton: "Cerrar",
    });
  }
}

function getRepoRoot() {
  const bundlePath = ObjC.unwrap($.NSBundle.mainBundle.bundlePath);
  return dirname(bundlePath);
}

function promptForProject() {
  const selectionMode = app.displayDialog(
    "Selecciona el proyecto de Logic. Si tu proyecto esta dentro de una carpeta, tambien puedes elegir esa carpeta y se intentara resolver el .logicx dentro.",
    {
      withTitle: "DAW Podcast Automation",
      buttons: ["Cancelar", "Elegir archivo", "Elegir carpeta"],
      defaultButton: "Elegir archivo",
    },
  );

  const selectedButton = selectionMode.buttonReturned;
  if (selectedButton === "Cancelar") {
    return null;
  }

  try {
    if (selectedButton === "Elegir archivo") {
      return app.chooseFile({
        withPrompt: "Selecciona el proyecto de Logic",
      }).toString();
    }

    return app.chooseFolder({
      withPrompt: "Selecciona la carpeta del proyecto o una carpeta que lo contenga",
    }).toString();
  } catch (error) {
    return null;
  }
}

function promptForOutput(baseOutputFolder) {
  const outputMode = app.displayDialog(
    "Donde quieres dejar la copia de trabajo y los archivos exportados?",
    {
      withTitle: "DAW Podcast Automation",
      buttons: ["Cancelar", "Elegir carpeta", "Usar misma carpeta"],
      defaultButton: "Usar misma carpeta",
    },
  );

  const selectedButton = outputMode.buttonReturned;
  if (selectedButton === "Cancelar") {
    return null;
  }
  if (selectedButton === "Usar misma carpeta") {
    return baseOutputFolder;
  }

  try {
    return app.chooseFolder({
      withPrompt: "Selecciona la carpeta de salida",
    }).toString();
  } catch (error) {
    return null;
  }
}

function promptForProfile() {
  const selectedProfile = app.chooseFromList(["podcast-stereo", "podcast-mono"], {
    withTitle: "DAW Podcast Automation",
    withPrompt: "Elige el perfil de salida:",
    defaultItems: ["podcast-stereo"],
    okButtonName: "Continuar",
    cancelButtonName: "Cancelar",
  });

  if (!selectedProfile || selectedProfile.length === 0) {
    return null;
  }
  return selectedProfile[0];
}

function dirname(inputPath) {
  return app.doShellScript("dirname " + shellQuote(inputPath));
}

function shellQuote(value) {
  return "'" + String(value).replace(/'/g, "'\"'\"'") + "'";
}
