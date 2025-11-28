from .router import Router


def start(host="0.0.0.0", port=3000, dev=True, reload=True):
    """
    Starts evolve application.
    For now: just intialize the router
    Next steps:
    build, dev server, logs
    """
    Router.instance()
