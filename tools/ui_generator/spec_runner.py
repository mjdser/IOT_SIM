"""Runs a ui_spec.json on the real board and collects the evidence.

Order of checks, cheapest and most exact first:
1. Every widget id the tests use is registered on the board (TREE).
2. Every visible registered widget lies fully inside the screen.
3. Per test: RESET_UI, then the steps. "expect" steps compare the board's widget
   state exactly; the first failing step ends that test. "capture" steps wait for
   the screen to settle and take a photo.
4. Per test with photos: one vision-judge call with all of that test's photos.
Plus an implicit "initial render" photo, judged against the intent and rubric.

Results are written under out_dir. DeviceError / CameraError propagate: they mean
the setup is broken, not the UI.
"""

import json
import re
import time
from pathlib import Path

import judge as judge_module
import spec as spec_module


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "x"


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in data.items() if k != "by_id"} if isinstance(data, dict) else data
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def check_expect(expect: dict, tree: dict, test: str, step: int):
    """Returns (failures, number_of_checks)."""
    failures, checks = [], 0
    for wid, props in expect.items():
        widget = tree["by_id"].get(wid)
        for prop, wanted in props.items():
            checks += 1
            if widget is None:
                actual, ok = "widget not found", False
            elif prop == "text_contains":
                actual = widget.get("text")
                ok = isinstance(actual, str) and wanted in actual
            else:
                actual = widget.get(prop, f"{widget['type']} has no {prop}")
                ok = actual == wanted
            if not ok:
                failures.append({"kind": "state", "test": test, "step": step, "id": wid,
                                 "expected": f"{prop}={wanted!r}", "actual": repr(actual)})
    return failures, checks


def check_layout(tree: dict):
    """Returns (failures, number_of_checks) for widgets sticking out of the screen."""
    sw, sh = tree.get("screen", [240, 320])
    failures, checks = [], 0
    for w in tree.get("widgets", []):
        if not w.get("visible"):
            continue
        checks += 1
        if w["x"] < 0 or w["y"] < 0 or w["x"] + w["w"] > sw or w["y"] + w["h"] > sh:
            failures.append({"kind": "layout", "test": "layout", "id": w["id"],
                             "expected": f"inside the {sw}x{sh} screen",
                             "actual": f"x={w['x']} y={w['y']} w={w['w']} h={w['h']}"})
    return failures, checks

def check_task_layout(tree,intent):
    """Exact compact-game checks; other layouts use request-aware image review."""
    if not re.search(r'tic[ -]?tac[ -]?toe|noughts.*crosses',intent,re.I):return [],0
    cells={}
    for w in tree.get('widgets',[]):
        match=re.fullmatch(r'(?:btn|cell|tile)_([0-2])_?([0-2])',w['id'])
        if match and w.get('visible'):cells[(int(match[1]),int(match[2]))]=w
    if len(cells)!=9:
        squares=[w for w in tree.get('widgets',[]) if w.get('visible') and w.get('type')=='btn' and w.get('w')==w.get('h') and w.get('w',0)>0]
        if len(squares)==9:
            ordered=sorted(squares,key=lambda w:(w['y'],w['x']))
            cells={(i//3,i%3):w for i,w in enumerate(ordered)}
    if not cells:return [],0  # Unknown structure: the image judge checks the board.
    failures=[];checks=1
    def fail(expected,actual):failures.append({'kind':'layout','test':'tic tac toe composition','expected':expected,'actual':actual})
    if len(cells)!=9:fail('all nine visible cells of the 3x3 board',str(len(cells)));return failures,checks
    sizes={(w['w'],w['h']) for w in cells.values()};checks+=1
    if len(sizes)!=1 or any(a!=b for a,b in sizes):fail('nine equally sized square cells',str(sorted(sizes)))
    checks+=1
    xs=[cells[(0,c)]['x'] for c in range(3)];ys=[cells[(r,0)]['y'] for r in range(3)]
    if any(cells[(r,c)]['x']!=xs[c] or cells[(r,c)]['y']!=ys[r] for r in range(3) for c in range(3)) or xs[1]-xs[0]!=xs[2]-xs[1] or ys[1]-ys[0]!=ys[2]-ys[1]:fail('aligned rows/columns and consistent spacing','uneven grid coordinates')
    # Respect explicitly positioned boards; only the compact default is centred.
    if not re.search(r'(?:align|place|position|side).{0,25}(?:left|right)|(?:left|right).{0,12}(?:side|align)',intent,re.I):
        checks+=1
        left=min(w['x'] for w in cells.values());right=max(w['x']+w['w'] for w in cells.values());centre=(left+right)/2
        if abs(centre-tree.get('screen',[240,320])[0]/2)>4:fail('the whole compact game board centred horizontally',f'board spans x={left}..{right}, centre={centre}; screen centre={tree.get("screen",[240,320])[0]/2}. These actual coordinates include parent padding; calculate from usable content width or set explicit padding before centring.')
    return failures,checks

def geometry_keys(intent):
    keys=('clipped_labels','overlapping_interactive','overlapping_text')
    requested_scroll=bool(re.search(r'scrollable|scrolling|long list|feed|log viewer',intent,re.I))
    no_scroll=bool(re.search(r'(?:no|without|avoid).{0,12}scroll',intent,re.I))
    return keys if requested_scroll and not no_scroll else keys+('clipped_controls',)


class Report:
    def __init__(self):
        self.failures, self.tests = [], []
        self.checks_total = self.checks_passed = 0
        self.photos = 0

    def add(self, failures, checks):
        self.failures += failures
        self.checks_total += checks
        self.checks_passed += checks - len(failures)

    def as_dict(self, visual: bool):
        return {"passed": not self.failures, "checks_total": self.checks_total,
                "checks_passed": self.checks_passed, "visual": visual, "photos": self.photos,
                "failures": self.failures, "tests": self.tests}


def run_spec(spec: dict, device, camera, out_dir: Path, log=print, judge=None, must_see=None, observe=None, initial_theme=None, framebuffer_judge=None) -> dict:
    """camera may be None: host captures save framebuffers, serial-only captures skip.
    must_see: independent requirements (requirements.py) the first photo must meet,
    on top of the builder's own description."""
    judge = judge or judge_module.judge_test
    intent = spec["intent"]
    report = Report()
    visual_enabled=camera is not None or framebuffer_judge is not None
    framebuffer_captures=[]
    observe = observe or (lambda message: None)

    device.reset_ui()
    device.wait_idle()
    tree = device.tree()
    observe('Initial render')
    _save_json(out_dir / "initial" / "tree.json", tree)
    if hasattr(device, "capture"):
        initial_png=device.capture(out_dir / "initial")
        if framebuffer_judge:
            import framebuffer_judge as image_review
            criteria=[f'The layout and content show the requested interface: {intent}, excluding palette preference.']+image_review.initial_criteria(spec.get('visual_rubric',[]),initial_theme)+image_review.RUBRIC
            framebuffer_captures.append({'label':'initial','test':'initial render','photo':initial_png,'after':f'Initial render, {initial_theme} palette. Ignore opposite colour words in initial intent/rubric, but check actual contrast.','expect_visual':criteria})
    if initial_theme and hasattr(device,'framebuffer'):
        raw=device.framebuffer();pixel=raw[0]|raw[1]<<8
        r=((pixel>>11)&31)*255/31;g=((pixel>>5)&63)*255/63;b=(pixel&31)*255/31
        bright=(.2126*r+.7152*g+.0722*b)>=128
        correct=bright==(initial_theme=='light')
        report.add([] if correct else [{'kind':'palette','test':'initial background','expected':initial_theme+' initial background',
                    'actual':f'RGB({int(r)},{int(g)},{int(b)}). Use UI_LIGHT_THEME for initial colours; do not override it with runtime theme state during creation.'}],1)

    if tree.get("overflow"):
        report.add([{"kind": "spec", "test": "setup", "expected": "at most 128 registered widgets",
                     "actual": "ui_register was called for too many widgets"}], 1)
    missing = sorted(spec_module.ids_used(spec) - set(tree["by_id"]))
    report.add([{"kind": "spec", "test": "setup", "id": wid,
                 "expected": f"a widget registered with ui_register(obj, \"{wid}\")",
                 "actual": "no widget has this id"} for wid in missing], len(spec_module.ids_used(spec)))
    if missing:
        log(f"Tests use unregistered widget ids: {', '.join(missing)}; not running the tests.")
        result = report.as_dict(visual_enabled)
        _save_json(out_dir / "result.json", result)
        return result
    report.add(*check_layout(tree))
    report.add(*check_task_layout(tree,intent))
    if hasattr(device, "geometry"):
        geometry = device.geometry()
        _save_json(out_dir / "initial" / "geometry.json", geometry)
        for key in geometry_keys(intent):
            value=geometry.get(key,0)
            report.add(([{"kind":"layout", "test":"host geometry", "expected":f"no {key}",
                          "actual":json.dumps(geometry.get('clipped_label_details',value) if key=='clipped_labels' else value)}] if value else []), 1)

    if camera is None and hasattr(device,'geometry') and report.failures:
        log('Initial layout failed; repairing before running interactions or image review.')
        result=report.as_dict(visual_enabled)
        _save_json(out_dir/'result.json',result)
        return result

    if camera is not None:
        photo = camera.capture(out_dir / "initial" / "photo.jpg")
        report.photos += 1
        shows = f"The display shows: {intent}"
        if spec.get("theme") == "light":
            # The photos are of the dark test version; the light colours come later.
            shows += " (this photo is its dark-colour test version, so ignore colour words such as white or light)"
        criteria = ([shows] + list(must_see or []) + list(spec.get("visual_rubric", []))
                    + judge_module.DEFAULT_RUBRIC)
        caps = [{"label": "initial", "photo": photo, "after": "the UI was started", "expect_visual": criteria}]
        # The first photo also checks the camera framing: a cut-off or rotated view
        # raises CameraError (setup problem) instead of failing the UI.
        failures, verdict = judge("initial render", intent, caps, check_framing=True)
        _save_json(out_dir / "initial" / "verdict.json", verdict)
        report.add(failures, len(criteria))
        log(f"Initial render: {len(criteria) - len(failures)}/{len(criteria)} visual checks passed.")

    for test in spec["tests"]:
        name = test["name"]
        test_dir = out_dir / _slug(name)
        before = len(report.failures)
        device.reset_ui()
        device.wait_idle()
        observe(f'Test: {name} · reset')
        after = "the UI was started"
        captures = []
        stopped = False

        for n, step in enumerate(test["steps"], 1):
            kind, arg = next(iter(step.items()))
            if kind == "tap":
                reason = device.tap(arg)
                if reason:
                    report.add([{"kind": "state", "test": name, "step": n, "id": arg,
                                 "expected": f"{arg} can be tapped", "actual": reason}], 1)
                    stopped = True
                after = f"tapping {arg}"
            elif kind == "drag":
                wid, value = arg
                reached, reason = device.drag(wid, value)
                if reason:
                    report.add([{"kind": "state", "test": name, "step": n, "id": wid,
                                 "expected": f"{wid} can be dragged to {value}", "actual": reason}], 1)
                    stopped = True
                after = f"dragging {wid} to {value}"
            elif kind == "wait_ms":
                time.sleep(arg / 1000)
            elif kind == "expect":
                device.wait_idle()
                failures, checks = check_expect(arg, device.tree(), name, n)
                report.add(failures, checks)
                stopped = bool(failures)
            elif kind == "capture" and hasattr(device, "capture"):
                cap_dir = test_dir / f"{n:02d}_{_slug(arg['label'])}"
                png=device.capture(cap_dir)
                if framebuffer_judge:
                    criteria=(image_review.initial_criteria(arg['expect_visual'],initial_theme) if after=='the UI was started' else list(arg['expect_visual']))+image_review.RUBRIC
                    framebuffer_captures.append({'label':f'{len(framebuffer_captures):02d}_{_slug(name)}_{n}_{_slug(arg["label"])}',
                        'test':name,'photo':png,'after':f'Test {name}: {after}','expect_visual':criteria})
                failures, checks = check_layout(device.tree())
                for failure in failures:
                    failure.update(test=name,step=n,label=arg['label'])
                report.add(failures,checks)
                report.add(*check_task_layout(device.tree(),intent))
                geometry=device.geometry() if hasattr(device, "geometry") else {}
                for key in geometry_keys(intent) if hasattr(device, "geometry") else ():
                    value=geometry.get(key,0)
                    details=geometry.get('clipped_label_details',value) if key=='clipped_labels' else value
                    report.add(([{'kind':'layout','test':name,'step':n,'label':arg['label'],
                                 'expected':f'no {key}','actual':json.dumps(details)}] if value else []),1)
            elif kind == "capture" and camera is not None:
                if not device.wait_idle():
                    log(f"  {name}: screen still changing before photo {arg['label']!r}")
                cap_dir = test_dir / f"{n:02d}_{_slug(arg['label'])}"
                _save_json(cap_dir / "tree.json", device.tree())
                photo = camera.capture(cap_dir / "photo.jpg")
                report.photos += 1
                captures.append({"label": arg["label"], "photo": photo, "after": after,
                                 "expect_visual": arg["expect_visual"]})
            if kind in ('tap','drag','expect') and hasattr(device,'geometry'):
                geometry=device.geometry()
                report.add(*check_task_layout(device.tree(),intent))
                for key in geometry_keys(intent):
                    value=geometry.get(key,0)
                    details=geometry.get('clipped_label_details',value) if key=='clipped_labels' else value
                    report.add(([{'kind':'layout','test':name,'step':n,'expected':f'no {key}',
                                  'actual':json.dumps(details)}] if value else []),1)
            if stopped:
                observe(f'Test: {name} · step {n}: {kind} · FAILED')
                log(f"  {name}: stopped at step {n} ({kind})")
                break
            observe(f'Test: {name} · step {n}: {kind}' + (f' {arg}' if kind in ('tap', 'drag') else ''))

        if captures and not stopped:
            failures, verdict = judge(name, intent, captures)
            _save_json(test_dir / "verdict.json", verdict)
            report.add(failures, sum(len(c["expect_visual"]) for c in captures))

        passed = len(report.failures) == before
        observe(f'Test: {name} · ' + ('passed' if passed else 'FAILED'))
        report.tests.append({"name": name, "passed": passed, "photos": len(captures)})
        log(f"Test {name!r}: {'passed' if passed else 'FAILED'}"
            + (f" ({len(captures)} photos)" if captures else ""))

    if framebuffer_judge and not report.failures:
        log(f'Image judge: reviewing {len(framebuffer_captures)} framebuffer PNGs for readability, contrast and visual criteria...')
        _save_json(out_dir/'visual'/'inputs.json',{'intent':intent,'captures':[dict(c,photo=str(c['photo'])) for c in framebuffer_captures]})
        failures,verdict=framebuffer_judge('framebuffer review',intent,framebuffer_captures)
        _save_json(out_dir/'visual'/'verdict.json',verdict)
        report.photos=len(framebuffer_captures)
        report.add(failures,sum(len(c['expect_visual']) for c in framebuffer_captures))
        log(f'Image judge: {"passed" if not failures else "FAILED"}'+(' (cached)' if verdict.get('cached') else '')+f' · {len(failures)} visual failures.')
    elif framebuffer_judge:
        log('Image judge: deferred until functional and layout checks pass; no review credits used.')
    result = report.as_dict(visual_enabled)
    _save_json(out_dir / "result.json", result)
    return result


def describe_failures(failures, limit: int = 12) -> str:
    """Plain text for Gemini's retry prompt."""
    lines = []
    unique=[];seen=set()
    for failure in failures:
        signature=(failure['kind'],failure.get('id'),failure['expected'],failure['actual'])
        if signature not in seen:seen.add(signature);unique.append(failure)
    for f in unique[:limit]:
        where = f"test {f['test']!r}"
        if "step" in f:
            where += f", step {f['step']}"
        if "label" in f:
            where += f", photo {f['label']!r}"
        subject = f" widget {f['id']}:" if f.get("id") else ""
        if f["kind"] == "visual":
            lines.append(f"- [{where}] visual check failed: expected \"{f['expected']}\"; the judge saw: {f['actual']}")
        else:
            lines.append(f"- [{where}]{subject} expected {f['expected']}, got {f['actual']}")
    if len(unique) > limit:
        lines.append(f"- ... and {len(unique) - limit} more distinct failures")
    if len(failures)>len(unique):lines.append(f'- {len(failures)-len(unique)} repeated occurrences omitted; fix the shared cause.')
    return "\n".join(lines)
