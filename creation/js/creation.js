// Creation loader - FINAL DEBUG BUILD
(function (global) {

  // ------------------------------
  // PREVENT MULTIPLE BOOTS
  // ------------------------------
  if (global.__creation_booted__) {
    console.log("[Creation] Duplicate creation.js load ignored");
    return;
  }
  global.__creation_booted__ = true;

  const E = (global.Creation = global.Creation || {});
  E.debug = true;

  const DEFAULT_PYODIDE_BASE = "/pyodide/";
  const DEFAULT_APP_URL = "/app.py";
  const ENGINE_ZIP = "/creation.zip";

  const log = (...msg) => {
    if (E.debug) console.log("[Creation]", ...msg);
  };
  const fail = (...msg) => console.error("[Creation ERROR]", ...msg);

  // ------------------------------------------------------------
  // Wait until window.CreationKernel is available
  // ------------------------------------------------------------
  async function waitForKernel() {
    log("Waiting for kernel...");
    while (!global.CreationKernel) {
      await new Promise(r => setTimeout(r, 10));
    }
    log("Kernel detected");
    return global.CreationKernel;
  }

  // ------------------------------------------------------------
  // Load Pyodide
  // ------------------------------------------------------------
  async function loadPyodideRuntime(base) {
    log("Loading Pyodide runtime...");

    if (typeof global.loadPyodide !== "function") {
      const script = document.createElement("script");
      script.src = base + "pyodide.js";
      log("Injecting pyodide.js:", script.src);

      await new Promise((resolve, reject) => {
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
    }

    try {
      log("Calling loadPyodide()...");
      const py = await global.loadPyodide({ indexURL: base });
      log("Pyodide loaded successfully");

      global.pyodide = py;
      E.pyodide = py;

      return py;
    } catch (err) {
      fail("Pyodide FAILED to initialize:", err);
      throw err;
    }
  }

  // ------------------------------------------------------------
  // Load creation.zip into Pyodide FS
  // ------------------------------------------------------------
  async function loadEngineZip(pyodide) {
    log("Fetching creation.zip...");

    const r = await fetch(ENGINE_ZIP);
    if (!r.ok) throw new Error("Failed to fetch creation.zip");

    const buf = await r.arrayBuffer();

    log("Unpacking creation.zip...");
    pyodide.runPython(`import os; os.chdir('/')`);
    pyodide.unpackArchive(buf, "zip");

    pyodide.runPython(`import sys; sys.path.insert(0, '/')`);

    log("sys.path =", pyodide.runPython("import sys; sys.path"));
    log("root files =", pyodide.runPython("import os; os.listdir('/')"));
    log("creation exists =", pyodide.runPython("import os; 'creation' in os.listdir('/')"));
  }

  // ------------------------------------------------------------
  // Load and run app.py
  // ------------------------------------------------------------
  async function loadApp(pyodide, url) {
    log("Fetching app.py...");
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("Failed to fetch app.py");

    const code = await resp.text();
    log("Executing app.py...");

    try {
      await pyodide.runPythonAsync(code);
      log("app.py executed");
    } catch (err) {
      fail("Error while executing app.py:", err);
      throw err;
    }
  }

  // ------------------------------------------------------------
  // MAIN ENTRYPOINT
  // ------------------------------------------------------------
  E.start = async function start(options = {}) {

    // extra safety
    if (global.__creation_started__) {
      console.log("[Creation] start() already executed — skipping");
      return;
    }
    global.__creation_started__ = true;

    log("Starting Creation…");

    const pyodideBase = options.pyodideBase || DEFAULT_PYODIDE_BASE;
    const appUrl = options.appUrl || DEFAULT_APP_URL;

    const kernel = await waitForKernel();
    const pyodide = await loadPyodideRuntime(pyodideBase);

    try {
      if (typeof pyodide.setDebug === "function") {
        pyodide.setDebug(true);
        log("Pyodide debug mode ON");
      }
    } catch (err) {
      console.warn("pyodide.setDebug failed:", err);
    }

    log("Registering JS kernel module inside Python");
    pyodide.registerJsModule("kernel", kernel);
    pyodide.registerJsModule("creation_js", {
      log: (...a) => console.log("[Python→JS]", ...a),
    });

    await loadEngineZip(pyodide);
    await loadApp(pyodide, appUrl);

    const pyStart = pyodide.globals.get("start");
    if (!pyStart) {
      fail("Python start() not found! Router will NOT initialize.");
    } else {
      log("Calling Python start()");
      try {
        pyStart();
      } catch (err) {
        fail("Error in Python start():", err);
      }
    }

    log("Creation fully started!");
  };

})(window);
