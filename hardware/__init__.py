"""Real-device viewer and capture adapter for the UI project."""
from pathlib import Path
import sys
_tools=str(Path(__file__).resolve().parents[1]/'tools/ui_generator')
if _tools not in sys.path:sys.path.insert(0,_tools)
