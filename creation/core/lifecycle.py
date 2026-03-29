_CURRENT_COMPONENT_STACK = []


def push_component(comp):
    _CURRENT_COMPONENT_STACK.append(comp)


def pop_component():
    if _CURRENT_COMPONENT_STACK:
        _CURRENT_COMPONENT_STACK.pop()


def current_component():
    if not _CURRENT_COMPONENT_STACK:
        raise RuntimeError("Lifecycle hook used outside component")
    return _CURRENT_COMPONENT_STACK[-1]


def on_mount(fn):
    current_component()._mount_callbacks.append(fn)


def on_cleanup(fn):
    current_component()._cleanup_callbacks.append(fn)
