from js import document, console
import asyncio, sys
import sys
sys.path.insert(0, "/")

# Evolve import
from evolve.dom.dom import div, button, h1, mount
# OR if you export inside __init__.py:
# from evolve.dom import div, button, h1, mount


# -----------------------
# Test System
# -----------------------

results = []
status_box = document.getElementById("status")

def check(name, condition):
    results.append((name, condition))

def render_results():
    status_box.innerHTML = ""
    for name, passed in results:
        div = document.createElement("div")
        div.className = "status-item " + ("pass" if passed else "fail")
        div.innerHTML = f"{'✅' if passed else '❌'} {name}"
        status_box.appendChild(div)

# -----------------------
# Tests
# -----------------------

def test_basic_mount():
    el = div("Hello from Evolve")
    mount(el, "#app")

    found = document.querySelector("#app").innerText.strip() == "Hello from Evolve"
    check("Basic Mount", found)

def test_text_update():
    el = div("Before")
    mount(el, "#app")
    el.set_text("After")

    found = document.querySelector("#app").innerText.strip() == "After"
    check("Text Update", found)

def test_many_nodes():
    parent = div()
    for i in range(300):
        parent.add_child(div(f"Item {i}"))

    mount(parent, "#app")

    items = document.querySelectorAll("#app div")
    check("300 Nodes Rendered", len(items) >= 300)

def test_events():
    triggered = {"value": False}

    def on_click(e=None):
        triggered["value"] = True

    btn = button("Click Me", onClick=on_click)
    mount(btn, "#app")

    btn_node = document.querySelector("button")
    btn_node.click()

    check("Click Event Fired", triggered["value"])

async def stress_test():
    parent = div()
    mount(parent, "#app")

    for i in range(500):
        parent.add_child(div(f"Stress {i}"))
        await asyncio.sleep(0.005)

    check("Stress Render (500 nodes)", True)

# -----------------------
# RUN EVERYTHING
# -----------------------

test_basic_mount()
test_text_update()
test_many_nodes()
test_events()

asyncio.ensure_future(stress_test())

render_results()
