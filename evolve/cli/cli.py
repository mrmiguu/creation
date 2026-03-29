"""
Evolve CLI - FastAPI-style route discovery.

Usage:
  evolve init <project>     Create new project with app.py
  evolve build [target]     Build for production
  evolve run [target]       Run development server

Target can be:
  - A Python file (app.py)
  - A directory (src/)
  - Omitted (scans current directory)
"""

import argparse
import os
import shutil
import http.server
import socketserver
import webbrowser
from pathlib import Path
from typing import List, Optional

ROOT = Path.cwd()
EVOLVE_DIR = ROOT / ".evolve"
DIST = EVOLVE_DIR / "dist"

PKG_ROOT = Path(__file__).resolve().parent.parent
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


def ensure_dirs():
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / "pyodide").mkdir(parents=True, exist_ok=True)


def discover_py_files(target: Optional[Path] = None) -> List[Path]:
    """
    Discover Python files from target.
    
    Args:
        target: Can be a file, directory, or None (uses current dir)
    
    Returns:
        List of Python file paths
    """
    if target is None:
        target = ROOT
    
    target = Path(target).resolve()
    
    if target.is_file():
        if target.suffix == ".py":
            return [target]
        return []
    
    if target.is_dir():
        # Find all .py files, excluding __pycache__, .evolve, etc.
        files = []
        for p in target.rglob("*.py"):
            # Skip hidden dirs, __pycache__, .evolve, venv, etc.
            parts = p.relative_to(target).parts
            skip = False
            for part in parts:
                if part.startswith("__") or part.startswith(".") or part in ("venv", "env", ".venv", "node_modules"):
                    skip = True
                    break
            if not skip:
                files.append(p)
        return files
    
    return []


def generate_app_py(target: Optional[Path] = None):
    """
    Generate app.py that imports all discovered Python files.
    Routes are registered via @page decorator when modules are imported.
    """
    py_files = discover_py_files(target)
    
    if not py_files:
        print("[warning] No Python files found to import")
    
    imports = []
    base = target if target and target.is_dir() else ROOT
    
    for f in py_files:
        try:
            rel = f.relative_to(base)
            mod_path = rel.with_suffix("").as_posix().replace("/", ".")
            imports.append(f"import {mod_path}")
        except ValueError:
            # File not relative to base, use absolute import style
            mod_path = f.stem
            imports.append(f"# {f.name}")
    
    content = "\n".join([
        "# Auto-generated app entry for Evolve",
        "# Routes are registered via @page decorator when modules import",
        "",
        *imports,
        "",
        "from evolve.src.app import start",
        "",
        "start()",
    ])
    
    (DIST / "app.py").write_text(content, encoding="utf-8")
    print(f"[build] Generated app.py with {len(py_files)} module(s)")


def copy_engine():
    """Copy the evolve Python package into dist so Pyodide can import it."""
    engine_src = ENGINE_DIR
    engine_dst = DIST / engine_src.name

    if engine_dst.exists():
        shutil.rmtree(engine_dst)

    shutil.copytree(
        engine_src,
        engine_dst,
        ignore=shutil.ignore_patterns("*.pyc", "__pycache__", "dist", "*.egg-info"),
    )
    print(f"[build] Copied engine")


def copy_assets():
    """Copy evolve.js + kernel.js + pyodide folder from evolve package → dist"""
    evolve_js = JS_DIR / "evolve.js"
    kernel_js = JS_DIR / "kernel.js"

    if not evolve_js.exists() or not kernel_js.exists():
        print("[error] Missing evolve.js or kernel.js inside evolve/js/")
        return

    shutil.copy2(evolve_js, DIST / "evolve.js")
    shutil.copy2(kernel_js, DIST / "kernel.js")
    print("[build] Copied evolve.js + kernel.js")

    if PYODIDE_DIR.exists():
        target_dir = DIST / "pyodide"
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(PYODIDE_DIR, target_dir)
        print("[build] Copied pyodide runtime")
    else:
        print("[warning] pyodide/ folder missing inside evolve/assets/")


def copy_user_code(target: Optional[Path] = None):
    """Copy user Python files to dist."""
    py_files = discover_py_files(target)
    base = target if target and target.is_dir() else ROOT
    
    for f in py_files:
        try:
            rel = f.relative_to(base)
            dest = DIST / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        except ValueError:
            # Not relative, copy to root of dist
            shutil.copy2(f, DIST / f.name)
    
    print(f"[build] Copied {len(py_files)} Python file(s)")
    
    # Also copy public/ if it exists
    public_dir = (target if target and target.is_dir() else ROOT) / "public"
    if public_dir.exists():
        for item in public_dir.iterdir():
            dst = DIST / item.name
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
        print("[build] Copied public/")


def write_index_html():
    (DIST / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    print("[build] Wrote index.html")


def pack_engine():
    """Pack engine + project python files into evolve.zip."""
    import zipfile

    target_zip = DIST / "evolve.zip"
    if target_zip.exists():
        target_zip.unlink()

    with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # Pack the engine (evolve package)
        engine_path = DIST / ENGINE_DIR.name
        if engine_path.exists():
            for file in engine_path.rglob("*"):
                if file.is_file() and "__pycache__" not in str(file):
                    arcname = file.relative_to(DIST)
                    zf.write(file, arcname)
        
        # Pack user files (everything in dist that's .py except app.py in engine)
        for file in DIST.rglob("*.py"):
            if ENGINE_DIR.name not in file.parts or file == DIST / "app.py":
                arcname = file.relative_to(DIST)
                if str(arcname) not in [str(a) for a in zf.namelist()]:
                    zf.write(file, arcname)

    print(f"[build] Packed evolve.zip")


def build_all(target: Optional[Path] = None):
    """Build the complete dist folder."""
    print(f"[build] Building from {target or ROOT}")
    ensure_dirs()
    copy_engine()
    copy_assets()
    copy_user_code(target)
    generate_app_py(target)
    write_index_html()
    pack_engine()
    print("[build] Done!")


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    """Handler that serves index.html for SPA routes."""
    
    def do_GET(self):
        path = self.path.split("?")[0]
        file_path = DIST / path.lstrip("/")
        
        if not file_path.exists() and not "." in path.split("/")[-1]:
            self.path = "/index.html"
        
        try:
            return super().do_GET()
        except BrokenPipeError:
            pass  # Client disconnected, ignore
    
    def log_message(self, format, *args):
        # Suppress noisy 404s for source maps, favicons, DevTools files
        path = args[0] if args else ""
        status = args[1] if len(args) > 1 else ""
        
        # Files we don't care about 404s for
        ignored = (".map", "favicon.ico", ".well-known", "chrome-devtools")
        if status == "404" and any(x in path for x in ignored):
            return
        
        # Only log non-200 status
        if status != "200":
            print(f"[server] {path} {status}")
    
    def handle(self):
        try:
            super().handle()
        except BrokenPipeError:
            pass  # Suppress broken pipe errors


def serve_dist(host: str = "127.0.0.1", port: int = 3000):
    os.chdir(str(DIST))
    handler = SPAHandler
    httpd = socketserver.TCPServer((host, port), handler)
    url = f"http://{host}:{port}"
    print(f"[server] Dev server running at {url}")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Stopped")
    finally:
        httpd.server_close()


# ============================================================================
# Commands
# ============================================================================

def cmd_init(project_name: str):
    """Create a new Evolve project with minimal structure."""
    target_dir = Path(project_name)
    
    if target_dir.exists():
        print(f"[init] {project_name} already exists")
        return
    
    target_dir.mkdir(parents=True)
    
    # Create simple app.py (FastAPI style)
    app_content = '''"""
My Evolve App
"""
from evolve.router.router import page
from evolve.src.html import div, h1, h2, button, p
from evolve.reactive.reactive import signal


@page("/")
def Home():
    """Home page with a simple counter."""
    count = signal(0)
    
    def increment(ev=None):
        count(count() + 1)
    
    return div(
        h1("🚀 Welcome to Evolve!"),
        p("A Python-native reactive UI framework"),
        
        div(
            h2(lambda: f"Count: {count()}"),
            button("+1", on_click=increment, style={
                "padding": "0.5rem 1rem",
                "fontSize": "1rem",
                "cursor": "pointer"
            }),
            style={"marginTop": "2rem"}
        ),
        
        style={
            "fontFamily": "system-ui, sans-serif",
            "padding": "2rem",
            "maxWidth": "600px",
            "margin": "0 auto"
        }
    )


@page("/about")
def About():
    """About page."""
    return div(
        h1("About"),
        p("Built with Evolve - 100% Python in the browser!"),
        style={
            "fontFamily": "system-ui, sans-serif",
            "padding": "2rem"
        }
    )
'''
    
    (target_dir / "app.py").write_text(app_content, encoding="utf-8")
    
    # Create public directory for static files
    (target_dir / "public").mkdir()
    
    print(f"[init] Created project: {project_name}/")
    print(f"       └── app.py")
    print(f"       └── public/")
    print(f"\nNext steps:")
    print(f"  cd {project_name}")
    print(f"  evolve run")


def cmd_build(target: Optional[str] = None):
    """Build project for production."""
    target_path = Path(target).resolve() if target else None
    build_all(target_path)


def cmd_run(target: Optional[str] = None, host: str = "127.0.0.1", port: int = 3000):
    """Build and run development server."""
    target_path = Path(target).resolve() if target else None
    build_all(target_path)
    serve_dist(host, port)


def main():
    parser = argparse.ArgumentParser(
        prog="evolve",
        description="Evolve - Python-native web framework"
    )
    sub = parser.add_subparsers(dest="cmd")

    # init command
    p_init = sub.add_parser("init", help="Create new project")
    p_init.add_argument("project", help="Project name")

    # build command
    p_build = sub.add_parser("build", help="Build for production")
    p_build.add_argument("target", nargs="?", help="File or directory to build (default: current dir)")

    # run command
    p_run = sub.add_parser("run", help="Run development server")
    p_run.add_argument("target", nargs="?", help="File or directory to run (default: current dir)")
    p_run.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    p_run.add_argument("--port", default=3000, type=int, help="Port to bind (default: 3000)")

    args = parser.parse_args()
    
    if args.cmd == "init":
        cmd_init(args.project)
    elif args.cmd == "build":
        cmd_build(args.target)
    elif args.cmd == "run":
        cmd_run(args.target, args.host, args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
