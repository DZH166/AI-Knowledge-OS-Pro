from __future__ import annotations

from pathlib import Path
import runpy
import sys

_TARGET = Path(__file__).resolve().parent / "maintenance" / "self_check" / Path(__file__).name
if __name__ == "__main__":
    print(f"Deprecated compatibility wrapper: {Path(__file__).as_posix()} delegates to {_TARGET.as_posix()}", file=sys.stderr)
globals().update(runpy.run_path(str(_TARGET), run_name=__name__))
