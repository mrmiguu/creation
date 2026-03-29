"""
Creation Framework Showcase - Complex Demo Page

Demonstrates all framework features:
- Reactive signals
- Components with props
- Event handling  
- Dynamic styling
- Lists and iteration
- Conditional rendering
"""

from creation.src.html import div, span, button, h1, h2, h3, p, header, main, input, a, section, nav, footer, ul, li, article
from creation.reactive.reactive import signal, computed
from creation.components.component import component
from creation.router.router import page


# ============================================================================
# Reusable Components
# ============================================================================

@component
def Card(*children, title="", icon="📦", **props):
    """A styled card component with glassmorphism effect."""
    return div(
        div(
            span(icon, style={"fontSize": "1.5rem"}),
            h3(title, style={"margin": "0", "marginLeft": "0.75rem", "fontWeight": "600"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "1rem"}
        ),
        div(*children),
        style={
            "background": "rgba(255,255,255,0.05)",
            "backdropFilter": "blur(10px)",
            "borderRadius": "1rem",
            "border": "1px solid rgba(255,255,255,0.1)",
            "padding": "1.5rem",
            "boxShadow": "0 8px 32px rgba(0,0,0,0.2)",
            **props.get("style", {})
        }
    )


@component  
def Badge(*children, variant="default", **props):
    """A small badge/tag component."""
    colors = {
        "default": {"bg": "rgba(99, 102, 241, 0.2)", "border": "rgba(99, 102, 241, 0.4)"},
        "success": {"bg": "rgba(16, 185, 129, 0.2)", "border": "rgba(16, 185, 129, 0.4)"},
        "warning": {"bg": "rgba(245, 158, 11, 0.2)", "border": "rgba(245, 158, 11, 0.4)"},
        "danger": {"bg": "rgba(239, 68, 68, 0.2)", "border": "rgba(239, 68, 68, 0.4)"},
    }
    color = colors.get(variant, colors["default"])
    
    return span(
        *children,
        style={
            "padding": "0.25rem 0.75rem",
            "borderRadius": "9999px",
            "fontSize": "0.75rem",
            "fontWeight": "500",
            "background": color["bg"],
            "border": f"1px solid {color['border']}",
        }
    )


@component
def ProgressBar(value=0, max_value=100, color="#6366f1"):
    """Animated progress bar component."""
    percentage = min(100, max(0, (value / max_value) * 100)) if max_value > 0 else 0
    
    return div(
        div(
            style={
                "width": f"{percentage}%",
                "height": "100%",
                "background": f"linear-gradient(90deg, {color}, {color}dd)",
                "borderRadius": "9999px",
                "transition": "width 0.3s ease"
            }
        ),
        style={
            "width": "100%",
            "height": "0.5rem",
            "background": "rgba(255,255,255,0.1)",
            "borderRadius": "9999px",
            "overflow": "hidden"
        }
    )


# ============================================================================
# Main Page
# ============================================================================

@page("/")
def Home():
    # ========== State ==========
    count = signal(0)
    active_tab = signal("overview")
    todos = signal([
        {"id": 1, "text": "Build a reactive UI framework", "done": True},
        {"id": 2, "text": "Add signal-based state", "done": True},
        {"id": 3, "text": "Create component system", "done": True},
        {"id": 4, "text": "Write documentation", "done": False},
        {"id": 5, "text": "Deploy to production", "done": False},
    ])
    new_todo_text = signal("")
    notifications = signal(3)
    
    # ========== Computed Values ==========
    def get_completed():
        return sum(1 for t in todos() if t["done"])
    
    def get_total():
        return len(todos())
    
    def get_progress():
        total = get_total()
        return (get_completed() / total * 100) if total > 0 else 0
    
    # ========== Event Handlers ==========
    def increment(ev=None):
        count(count() + 1)

    def decrement(ev=None):
        if count() > 0:
            count(count() - 1)

    def reset_count(ev=None):
        count(0)

    def set_tab(tab_name):
        def handler(ev=None):
            active_tab(tab_name)
        return handler
    
    def add_todo(ev=None):
        text = new_todo_text()
        if text.strip():
            current = todos()
            new_id = max(t["id"] for t in current) + 1 if current else 1
            todos([*current, {"id": new_id, "text": text, "done": False}])
            new_todo_text("")
            
    def toggle_todo(todo_id):
        def handler(ev=None):
            current = todos()
            updated = [
                {**t, "done": not t["done"]} if t["id"] == todo_id else t
                for t in current
            ]
            todos(updated)
        return handler

    def delete_todo(todo_id):
        def handler(ev=None):
            todos([t for t in todos() if t["id"] != todo_id])
        return handler

    def clear_notifications(ev=None):
        notifications(0)

    def on_todo_input(ev):
        try:
            val = ev.get("target", {}).get("value", "")
            new_todo_text(val)
        except Exception:
            pass
    
    # ========== Tab Contents ==========
    def render_overview():
        return div(
            # Stats Grid
            div(
                # Counter Card
                Card(
                    div(
                        h2(
                            lambda: str(count()),
                            style={
                                "fontSize": "4rem",
                                "fontWeight": "800",
                                "textAlign": "center",
                                "margin": "1rem 0",
                                "background": "linear-gradient(135deg, #6366f1, #06b6d4)",
                                "WebkitBackgroundClip": "text",
                                "WebkitTextFillColor": "transparent"
                            }
                        ),
                        div(
                            button("−", on_click=decrement, style={
                                "width": "3rem", "height": "3rem", "borderRadius": "50%",
                                "border": "none", "background": "linear-gradient(135deg, #ef4444, #f97316)",
                                "color": "white", "fontSize": "1.5rem", "cursor": "pointer"
                            }),
                            button("Reset", on_click=reset_count, style={
                                "padding": "0.75rem 1.5rem", "borderRadius": "2rem",
                                "border": "1px solid rgba(255,255,255,0.3)", "background": "transparent",
                                "color": "white", "cursor": "pointer"
                            }),
                            button("+", on_click=increment, style={
                                "width": "3rem", "height": "3rem", "borderRadius": "50%",
                                "border": "none", "background": "linear-gradient(135deg, #10b981, #06b6d4)",
                                "color": "white", "fontSize": "1.5rem", "cursor": "pointer"
                            }),
                            style={"display": "flex", "justifyContent": "center", "gap": "1rem"}
                        )
                    ),
                    title="Interactive Counter",
                    icon="🔢"
                ),
                
                # Quick Stats
                Card(
                    div(
                        div(
                            span("Counter Value", style={"color": "rgba(255,255,255,0.5)", "fontSize": "0.875rem"}),
                            h3(lambda: str(count()), style={"margin": "0.25rem 0 0", "fontSize": "1.5rem"}),
                            style={"marginBottom": "1rem"}
                        ),
                        div(
                            span("Tasks Completed", style={"color": "rgba(255,255,255,0.5)", "fontSize": "0.875rem"}),
                            h3(lambda: f"{get_completed()}/{get_total()}", style={"margin": "0.25rem 0 0", "fontSize": "1.5rem"}),
                            style={"marginBottom": "1rem"}
                        ),
                        div(
                            span("Progress", style={"color": "rgba(255,255,255,0.5)", "fontSize": "0.875rem"}),
                            ProgressBar(value=get_progress(), max_value=100, color="#10b981"),
                            style={"marginTop": "0.5rem"}
                        )
                    ),
                    title="Quick Stats",
                    icon="📊"
                ),
                
                style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))", "gap": "1.5rem"}
            ),
            
            # Features Section
            div(
                h2("✨ Framework Features", style={"marginBottom": "1.5rem", "fontSize": "1.5rem"}),
                div(
                    div(
                        Badge("Reactive", variant="success"),
                        p("Fine-grained reactivity with Signals", style={"margin": "0.5rem 0 0", "fontSize": "0.875rem", "color": "rgba(255,255,255,0.6)"}),
                        style={"padding": "1rem", "background": "rgba(255,255,255,0.03)", "borderRadius": "0.75rem"}
                    ),
                    div(
                        Badge("Components", variant="default"),
                        p("Composable function components", style={"margin": "0.5rem 0 0", "fontSize": "0.875rem", "color": "rgba(255,255,255,0.6)"}),
                        style={"padding": "1rem", "background": "rgba(255,255,255,0.03)", "borderRadius": "0.75rem"}
                    ),
                    div(
                        Badge("Fast", variant="warning"),
                        p("Minimal DOM operations", style={"margin": "0.5rem 0 0", "fontSize": "0.875rem", "color": "rgba(255,255,255,0.6)"}),
                        style={"padding": "1rem", "background": "rgba(255,255,255,0.03)", "borderRadius": "0.75rem"}
                    ),
                    div(
                        Badge("Python", variant="danger"),
                        p("100% Python, runs in browser", style={"margin": "0.5rem 0 0", "fontSize": "0.875rem", "color": "rgba(255,255,255,0.6)"}),
                        style={"padding": "1rem", "background": "rgba(255,255,255,0.03)", "borderRadius": "0.75rem"}
                    ),
                    style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))", "gap": "1rem"}
                ),
                style={"marginTop": "2rem"}
            )
        )
    
    def render_tasks():
        todo_list = todos()
        return div(
            Card(
                div(
                    # Add todo form
                    div(
                        input(
                            type="text",
                            placeholder="Add a new task...",
                            value=new_todo_text(),
                            on_input=on_todo_input,
                            style={
                                "flex": "1",
                                "padding": "0.75rem 1rem",
                                "borderRadius": "0.5rem",
                                "border": "1px solid rgba(255,255,255,0.2)",
                                "background": "rgba(255,255,255,0.05)",
                                "color": "white",
                                "fontSize": "1rem"
                            }
                        ),
                        button(
                            "Add Task",
                            on_click=add_todo,
                            style={
                                "padding": "0.75rem 1.5rem",
                                "borderRadius": "0.5rem",
                                "border": "none",
                                "background": "linear-gradient(135deg, #6366f1, #8b5cf6)",
                                "color": "white",
                                "cursor": "pointer",
                                "fontWeight": "600"
                            }
                        ),
                        style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem"}
                    ),
                    
                    # Progress
                    div(
                        span(f"{get_completed()} of {get_total()} completed", style={"fontSize": "0.875rem", "color": "rgba(255,255,255,0.6)"}),
                        ProgressBar(value=get_progress(), max_value=100, color="#10b981"),
                        style={"marginBottom": "1.5rem"}
                    ),
                    
                    # Todo list
                    div(
                        *[
                            div(
                                button(
                                    "✓" if todo["done"] else " ",
                                    on_click=toggle_todo(todo["id"]),
                                    style={
                                        "width": "1.5rem", "height": "1.5rem", "borderRadius": "0.25rem",
                                        "border": f"2px solid {'#10b981' if todo['done'] else 'rgba(255,255,255,0.3)'}",
                                        "background": "#10b981" if todo["done"] else "transparent",
                                        "color": "white", "cursor": "pointer", "fontSize": "0.75rem"
                                    }
                                ),
                                span(
                                    todo["text"],
                                    style={
                                        "flex": "1", "marginLeft": "1rem",
                                        "textDecoration": "line-through" if todo["done"] else "none",
                                        "color": "rgba(255,255,255,0.5)" if todo["done"] else "white"
                                    }
                                ),
                                button(
                                    "×",
                                    on_click=delete_todo(todo["id"]),
                                    style={
                                        "width": "1.5rem", "height": "1.5rem", "borderRadius": "0.25rem",
                                        "border": "none", "background": "rgba(239, 68, 68, 0.2)",
                                        "color": "#ef4444", "cursor": "pointer"
                                    }
                                ),
                                style={
                                    "display": "flex", "alignItems": "center",
                                    "padding": "1rem",
                                    "background": "rgba(255,255,255,0.03)",
                                    "borderRadius": "0.5rem",
                                    "marginBottom": "0.5rem"
                                },
                                key=str(todo["id"])
                            )
                            for todo in todo_list
                        ]
                    )
                ),
                title="Task Manager",
                icon="✅"
            )
        )
    
    def render_settings():
        return div(
            Card(
                div(
                    # Notifications
                    div(
                        div(
                            h3("Notifications", style={"margin": "0", "fontSize": "1rem"}),
                            p(lambda: f"{notifications()} unread", style={"margin": "0.25rem 0 0", "fontSize": "0.875rem", "color": "rgba(255,255,255,0.5)"}),
                        ),
                        button(
                            "Clear All",
                            on_click=clear_notifications,
                            style={
                                "padding": "0.5rem 1rem",
                                "borderRadius": "0.5rem",
                                "border": "none",
                                "background": "rgba(239, 68, 68, 0.2)",
                                "color": "#ef4444",
                                "cursor": "pointer"
                            }
                        ),
                        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "padding": "1rem 0", "borderBottom": "1px solid rgba(255,255,255,0.1)"}
                    ),
                    
                    # About
                    div(
                        h3("About", style={"marginBottom": "0.5rem"}),
                        p("Creation Framework v0.1.0", style={"margin": "0", "color": "rgba(255,255,255,0.6)"}),
                        p("A Python-native reactive UI framework for the browser.", style={"margin": "0.5rem 0 0", "fontSize": "0.875rem", "color": "rgba(255,255,255,0.4)"}),
                        div(
                            Badge("MIT License", variant="success"),
                            Badge("Python 3.11+", variant="warning"),
                            Badge("WebAssembly", variant="default"),
                            style={"display": "flex", "gap": "0.5rem", "marginTop": "1rem"}
                        ),
                        style={"padding": "1rem 0"}
                    )
                ),
                title="Settings",
                icon="⚙️"
            )
        )
    
    # ========== Render ==========
    current_tab = active_tab()
    
    return div(
        # Navigation
        header(
            div(
                # Logo
                div(
                    span("⚡", style={"fontSize": "1.75rem"}),
                    span("Creation", style={
                        "fontSize": "1.5rem", "fontWeight": "700", "marginLeft": "0.5rem",
                        "background": "linear-gradient(135deg, #6366f1, #06b6d4)",
                        "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent"
                    }),
                    style={"display": "flex", "alignItems": "center"}
                ),
                
                # Nav tabs
                nav(
                    button("Overview", on_click=set_tab("overview"), style={
                        "padding": "0.5rem 1rem", "borderRadius": "0.5rem", "border": "none",
                        "background": "rgba(99, 102, 241, 0.2)" if current_tab == "overview" else "transparent",
                        "color": "white", "cursor": "pointer"
                    }),
                    button("Tasks", on_click=set_tab("tasks"), style={
                        "padding": "0.5rem 1rem", "borderRadius": "0.5rem", "border": "none",
                        "background": "rgba(99, 102, 241, 0.2)" if current_tab == "tasks" else "transparent",
                        "color": "white", "cursor": "pointer"
                    }),
                    button("Settings", on_click=set_tab("settings"), style={
                        "padding": "0.5rem 1rem", "borderRadius": "0.5rem", "border": "none",
                        "background": "rgba(99, 102, 241, 0.2)" if current_tab == "settings" else "transparent",
                        "color": "white", "cursor": "pointer"
                    }),
                    style={"display": "flex", "gap": "0.5rem"}
                ),
                
                # Notification bell
                div(
                    button(
                        div(
                            span("🔔", style={"fontSize": "1.25rem"}),
                            span(
                                lambda: str(notifications()) if notifications() > 0 else "",
                                style={
                                    "position": "absolute", "top": "-4px", "right": "-4px",
                                    "background": "#ef4444", "color": "white", "fontSize": "0.7rem",
                                    "width": "1rem", "height": "1rem", "borderRadius": "50%",
                                    "display": "flex" if notifications() > 0 else "none",
                                    "alignItems": "center", "justifyContent": "center"
                                }
                            ),
                            style={"position": "relative"}
                        ),
                        on_click=clear_notifications,
                        style={"background": "transparent", "border": "none", "cursor": "pointer", "padding": "0.5rem"}
                    ),
                    style={"display": "flex", "alignItems": "center"}
                ),
                
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "maxWidth": "1200px", "margin": "0 auto"}
            ),
            style={
                "padding": "1rem 2rem",
                "background": "rgba(255,255,255,0.03)",
                "borderBottom": "1px solid rgba(255,255,255,0.1)",
                "backdropFilter": "blur(10px)"
            }
        ),
        
        # Main Content
        main(
            # Page Title
            div(
                h1(
                    "Framework Showcase",
                    style={
                        "fontSize": "2.5rem", "fontWeight": "800", "marginBottom": "0.5rem",
                        "background": "linear-gradient(135deg, #6366f1, #8b5cf6, #06b6d4)",
                        "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent"
                    }
                ),
                p(
                    "A comprehensive demonstration of Creation's capabilities",
                    style={"color": "rgba(255,255,255,0.6)", "fontSize": "1.125rem"}
                ),
                style={"textAlign": "center", "marginBottom": "2rem"}
            ),
            
            # Tab Content
            render_overview() if current_tab == "overview" else (
                render_tasks() if current_tab == "tasks" else render_settings()
            ),
            
            style={"padding": "2rem", "maxWidth": "1200px", "margin": "0 auto"}
        ),
        
        # Footer
        footer(
            p(
                "Built with ⚡ Creation • Python-Native Browser Framework",
                style={"textAlign": "center", "color": "rgba(255,255,255,0.4)", "fontSize": "0.875rem"}
            ),
            style={"padding": "2rem", "borderTop": "1px solid rgba(255,255,255,0.1)"}
        ),
        
        # Global Styles
        style={
            "minHeight": "100vh",
            "background": "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f3460 100%)",
            "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
            "color": "white"
        }
    )
