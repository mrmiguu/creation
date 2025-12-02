#!/usr/bin/env python3
"""
Evolve CLI - minimal MVP for `evolve run`, `evolve build`, `evolve init`.

Usage:
  python tools/cli.py init <project_dir>
  python tools/cli.py build
  python tools/cli.py run [--host HOST] [--port PORT]
"""

import argparse
import os
import shutil
import http.server
import socketserver
import webbrowser
from pathlib import Path
from typing import List

ROOT = Path.cwd()
EOLVE_DIR = ROOT / ".evolve"
DIST = EOLVE_DIR / "dist"
PAGES = ROOT / "pages"
COMPONENTS = ROOT / "components"
PUBLIC = ROOT / "public"

# Path to the project tooling root (one level above tools/)
PKG_ROOT = Path(__file__).resolve().parent.parent

# If your engine package lives in a subfolder `evolve/`, prefer that.
ENGINE_DIR = (PKG_ROOT / "evolve") if (PKG_ROOT / "evolve").exists() else PKG_ROOT

JS_DIR = PKG_ROOT / "js"
PYODIDE_DIR = PKG_ROOT / "assets" / "pyodide"


INDEX_HTML = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Evolve App</title>
  </head>
  <body>
    <div id="app"></div>

    <script src="/pyodide/pyodide.js"></script>
    <script src="/kernel.js"></script>
    <script src="/evolve.js"></script>

    <script>
      // Start the full Evolve engine (loads evolve.zip, app.py, kernel, etc.)
      Evolve.start();
    </script>

  </body>
</html>
"""


# -------------- helpers -----------------

def ensure_dirs():
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / "pages").mkdir(parents=True, exist_ok=True)
    (DIST / "components").mkdir(parents=True, exist_ok=True)
    (DIST / "public").mkdir(parents=True, exist_ok=True)
    (DIST / "pyodide").mkdir(parents=True, exist_ok=True)
    return


def list_py_files(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*.py") if p.is_file() and not p.name.startswith("__")]


def module_name_for(root: Path, file: Path) -> str:
    # convert pages/foo/bar.py -> pages.foo.bar
    rel = file.relative_to(root.parent)  # if root is project/pages, parent is project
    parts = rel.with_suffix("").parts
    return ".".join(parts)


def copy_engine():
    """Copy the evolve Python package into dist so Pyodide can import it."""
    engine_src = ENGINE_DIR  # use resolved engine directory
    engine_dst = DIST / engine_src.name  # ensures dist/<engine_src.name>/...

    if engine_dst.exists():
        shutil.rmtree(engine_dst)

    shutil.copytree(
        engine_src,
        engine_dst,
        ignore=shutil.ignore_patterns("*.pyc", "__pycache__", "dist", "*.egg-info"),
    )

    print(f"[build] copied engine from {engine_src} -> {engine_dst}")


def copy_tree(src: Path, dst: Path):
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


# -------------- build logic -----------------

def generate_app_py():
    """
    Generate app.py that:
    - imports every Python file inside pages/ and components/
    - imports evolve.src.app.start
    - calls start()
    """
    pages_files = list_py_files(PAGES)
    components_files = list_py_files(COMPONENTS)

    imports = []

    # Convert all project Python paths → module imports (pages.* / components.*)
    for f in pages_files + components_files:
        rel = f.relative_to(ROOT)
        mod_path = rel.with_suffix("").as_posix().replace("/", ".")
        imports.append(f"import {mod_path}")

    content = "\n".join(
        [
            "# Auto-generated app entry for Evolve",
            *imports,
            "",
            "from evolve.src.app import start",
            "",
            "start()",
        ]
    )

    (DIST / "app.py").write_text(content, encoding="utf-8")
    print(f"[build] wrote {DIST / 'app.py'}")


def copy_assets():
    """
    Copy evolve.js + kernel.js + pyodide folder from evolve package → dist
    """
    # JS engine files
    evolve_js = JS_DIR / "evolve.js"
    kernel_js = JS_DIR / "kernel.js"

    if not evolve_js.exists() or not kernel_js.exists():
        print("[error] Missing evolve.js or kernel.js inside evolve/js/")
        return

    shutil.copy2(evolve_js, DIST / "evolve.js")
    shutil.copy2(kernel_js, DIST / "kernel.js")
    print("[build] copied evolve.js + kernel.js")

    # Pyodide runtime
    if PYODIDE_DIR.exists():
        target = DIST / "pyodide"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(PYODIDE_DIR, target)
        print("[build] copied pyodide runtime")
    else:
        print("[warning] pyodide/ folder missing inside evolve/assets/")


def copy_user_code():
    # copy pages and components as packages (so imports in app.py work)
    if PAGES.exists():
        dest = DIST / "pages"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(PAGES, dest)
        print("[build] copied pages/")
    if COMPONENTS.exists():
        dest = DIST / "components"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(COMPONENTS, dest)
        print("[build] copied components/")
    # copy public (static) files to / (served at root)
    if PUBLIC.exists():
        for item in PUBLIC.iterdir():
            dst = DIST / item.name
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
        print("[build] copied public/ -> dist/")


def write_index_html():
    (DIST / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    print("[build] wrote index.html")


def pack_engine():
    """
    Pack engine + project python files into evolve.zip with correct top-level paths.
    Ensures the zip contains a top-level folder named same as engine_src.name (usually 'evolve').
    """
    import zipfile

    target = DIST / "evolve.zip"
    if target.exists():
        target.unlink()

    engine_src = ENGINE_DIR

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        # Pack engine/ (preserve top-level folder name)
        for item in engine_src.rglob("*"):
            if item.is_file():
                # Make arcname include the top-level engine folder, e.g. evolve/...
                arc = item.relative_to(engine_src.parent)
                z.write(item, arcname=str(arc))

        # Pack pages/ into top-level pages/
        if PAGES.exists():
            for item in PAGES.rglob("*.py"):
                arc = item.relative_to(ROOT)
                z.write(item, arcname=str(arc))

        # Pack components/ into top-level components/
        if COMPONENTS.exists():
            for item in COMPONENTS.rglob("*.py"):
                arc = item.relative_to(ROOT)
                z.write(item, arcname=str(arc))

        # Pack any top-level python modules in project root (if desired)
        for item in ROOT.glob("*.py"):
            if item.name not in ["app.py"]:
                z.write(item, arcname=item.name)

    print("[build] packed evolve.zip with engine + project code")


def build_all():
    print("[build] starting build...")

    ensure_dirs()
    copy_assets()
    copy_engine()
    copy_user_code()
    write_index_html()
    generate_app_py()
    pack_engine()
    print("[build] finished. dist at:", DIST)


# ---------------- serve/run ----------------

class SilentHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def serve_dist(host: str = "127.0.0.1", port: int = 3000):
    os.chdir(str(DIST))
    handler = SilentHandler
    httpd = socketserver.TCPServer((host, port), handler)
    url = f"http://{host}:{port}"
    print(f"[server] serving {DIST} at {url}")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[server] stopped")
    finally:
        httpd.server_close()


# ---------------- CLI ----------------

def cmd_init(target: str):
    target_dir = Path(target)
    if target_dir.exists():
        print(f"[init] {target} exists, aborting.")
        return
    # create simple starter project
    target_dir.mkdir(parents=True)
    (target_dir / "pages").mkdir()
    (target_dir / "components").mkdir()
    (target_dir / "public").mkdir()
    (target_dir / "pages" / "home.py").write_text(
    'from evolve.router.router import page\n'
    'from evolve.src.html import *\n'
    'from evolve.reactive.reactive import signal\n\n'
    '@page("/")\n'
    'def Home():\n'
    '    count = signal(0)\n'
    '    return div(\n'
    '        h1(f"Count: {count()}"),\n'
    '        button("Inc", on_click=lambda: count.set(count()+1))\n'
    '    )\n',
    encoding="utf-8",
    )


    print(f"[init] created project at {target}")


def cmd_build():
    build_all()


def cmd_run(host: str = "127.0.0.1", port: int = 3000):
    build_all()
    serve_dist(host, port)


def main():
    parser = argparse.ArgumentParser(prog="evolve")
    sub = parser.add_subparsers(dest="cmd")

    p_init = sub.add_parser("init")
    p_init.add_argument("target")

    p_build = sub.add_parser("build")

    p_run = sub.add_parser("run")
    p_run.add_argument("--host", default="127.0.0.1")
    p_run.add_argument("--port", default=3000, type=int)

    args = parser.parse_args()
    if args.cmd == "init":
        cmd_init(args.target)
    elif args.cmd == "build":
        cmd_build()
    elif args.cmd == "run":
        cmd_run(args.host, args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
