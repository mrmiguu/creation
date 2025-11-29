// Evolve loader - final stable version

(function (global) {
  const E = (global.Evolve = global.Evolve || {});
  E.debug = true;

  const DEFAULT_PYODIDE_BASE = "/pyodide/";
  const DEFAULT_APP_URL = "/app.py";
  const ENGINE_ZIP = "/evolve.zip";

  function log(...msg) {
    if (E.debug) console.log("[Evolve]", ...msg);
  }
  function fail(...msg) {
    console.error("[Evolve ERROR]", ...msg);
  }

  // --------------------------------------------------
  // Wait for kernel.js to initialize
  // --------------------------------------------------
  async function waitForKernel() {
    while (!global.EvolveKernel) {
      await new Promise(r => setTimeout(r, 10));
    }
    return global.EvolveKernel;
  }

  // --------------------------------------------------
  // Load Pyodide
  // --------------------------------------------------
  async function loadPyodideRuntime(base) {
    if (typeof global.loadPyodide !== "function") {
      const script = document.createElement("script");
      script.src = base + "pyodide.js";
      log("Loading pyodide.js:", script.src);

      await new Promise((resolve, reject) => {
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
    }

    return await loadPyodide({ indexURL: base });
  }

  // --------------------------------------------------
  // Load evolve.zip into Pyodide filesystem
  // --------------------------------------------------
  async function loadEngineZip(pyodide) {
    log("Fetching evolve.zip...");

    const r = await fetch(ENGINE_ZIP);
    if (!r.ok) throw new Error("Failed to fetch evolve.zip");

    const buf = await r.arrayBuffer();

    log("Unpacking evolve.zip into FS /");
    pyodide.runPython(`import os; os.chdir('/')`);
    pyodide.unpackArchive(buf, "zip");

    // Allow "import evolve"
    pyodide.runPython(`import sys; sys.path.insert(0, '/')`);

    // Debug
    log("sys.path =", pyodide.runPython("import sys; sys.path"));
    log("root files =", pyodide.runPython("import os; os.listdir('/')"));
    log("evolve exists =", pyodide.runPython("import os; 'evolve' in os.listdir('/')"));
  }

  // --------------------------------------------------
  // Load and execute the generated app.py
  // --------------------------------------------------
  async function loadApp(pyodide, url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("Failed to load app.py");
    const code = await resp.text();
    log("Executing app.py...");
    await pyodide.runPythonAsync(code);
  }

  // --------------------------------------------------
  // MAIN START FUNCTION (correct order)
  // --------------------------------------------------
  E.start = async function start(options = {}) {
    const pyodideBase = options.pyodideBase || DEFAULT_PYODIDE_BASE;
    const appUrl = options.appUrl || DEFAULT_APP_URL;

    log("Starting Evolve…");

    // 1. Wait for kernel.js
    const kernel = await waitForKernel();

    // 2. Initialize Pyodide
    const pyodide = await loadPyodideRuntime(pyodideBase);
    E.pyodide = pyodide;

    // 3. Register kernel as a Python module
    pyodide.registerJsModule("kernel", kernel);

    // Optional debug module
    pyodide.registerJsModule("evolve_js", {
      log: (...a) => console.log("[Python→JS]", ...a),
    });

    // 4. ⚡ Load evolve.zip BEFORE running the app
    await loadEngineZip(pyodide);

    // 5. ⚡ Now load the user code (app.py)
    await loadApp(pyodide, appUrl);

    // 6. If Python defines start(), call it
    const pyStart = pyodide.globals.get("start");
    if (pyStart) {
      log("Calling Python start()");
      pyStart();
    }

    log("Evolve fully started!");
  };

})(window);
