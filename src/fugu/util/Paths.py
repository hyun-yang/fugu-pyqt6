"""App resource / user-data path resolution utilities.

- resource_base():  Base directory for bundled resources (icons, splash
  images, etc.).
- user_data_base(): Base directory for user-writable data (settings.ini, *.db).

In development mode (running from source) both resolve to the directory
containing main.py (= the fugu package root).
For a PyInstaller-frozen executable:
  * resource_base  = sys._MEIPASS (the temporary directory where PyInstaller
                     unpacks bundled resources)
  * user_data_base = the directory containing the executable
"""

import sys
from pathlib import Path


def _frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_base() -> Path:
    if _frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent  # fugu/util/Paths.py -> fugu/


def user_data_base() -> Path:
    if _frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
