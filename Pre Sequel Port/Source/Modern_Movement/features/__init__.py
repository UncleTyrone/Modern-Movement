"""Feature modules for Modern Movement.

Each module exposes the same small interface, and the package __init__ merges them:

    OPTIONS       - option objects, shown together in one collapsible group
    KEYBINDS      - keybind options (only used for keys that belong to one feature)
    HOOKS         - hook functions
    on_enable()   - reset state and register with core (tick / jump handlers)
    on_disable()  - undo everything and unregister from core

Features never import each other. They talk through ../core.py (shared tick,
shared jump key, and a "busy" flag so only one movement action runs at a time).

To remove a feature, delete its file and its line in ../__init__.py.
"""
