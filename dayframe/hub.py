"""Stable launch path for the private sync hub: ``python -m dayframe.hub``.

Installed services (packaging/dayframe-hub.service) use this module name, so it
stays here while the implementation lives in dayframe/sync/hub.py.
"""
from .sync.hub import Hub, main

__all__ = ["Hub", "main"]

if __name__ == "__main__":
    main()
