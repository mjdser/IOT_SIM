"""Replay the accepted tests with live evidence; no provider or camera calls."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/ui_generator'))
import host_sim
with host_sim.source_lock():
    manifest = json.loads(host_sim.ACTIVE.read_text())
    executable = ROOT / manifest['builds'][manifest['theme']]['executable']
    report = host_sim.run_tests(json.loads((ROOT / 'lvgl_ui/ui_spec.json').read_text()), executable,
                                ROOT / 'simulator/test-results/live-tests', log=lambda message: None)
raise SystemExit(0 if report['passed'] else 1)
