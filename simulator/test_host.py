"""Integration test of real LVGL pixels/events; no board, camera, or AI calls."""
from pathlib import Path
import sys, json, hashlib, struct, zlib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'tools/ui_generator'))
from device_runner import SimulatorDevice
from spec_runner import run_spec
from host_sim import ACTIVE, digest
out=ROOT/'test-results'
out.mkdir(exist_ok=True)
if ACTIVE.exists():
    manifest=json.loads(ACTIVE.read_text())
    assert digest(ROOT.parent/'lvgl_ui/generated_ui.cpp')==manifest['source_sha256'], 'Source differs from the tested build'
    executable=ROOT.parent/manifest['builds'][manifest['theme']]['executable']
    assert digest(executable)==manifest['builds'][manifest['theme']]['executable_sha256']
    for name,sha in manifest['builds'][manifest['theme']]['sources'].items():
        assert digest(ROOT.parent/name)==sha, f'{name} differs from the accepted build'
    def no_ai(*a,**kw):raise AssertionError('No vision judge in host tests')
    with SimulatorDevice(executable) as device:
        assert device.command('PING')=='OK'
        assert device.tree()['screen']==[240,320]
        assert len(device.framebuffer())==153600
        current=json.loads((ROOT.parent/'lvgl_ui/ui_spec.json').read_text())
        result=run_spec(current,device,None,out/'accepted-spec',judge=no_ai)
    (out/'accepted-host.json').write_text(json.dumps(result,indent=2))
    print(f"Accepted UI: {result['checks_passed']}/{result['checks_total']} checks passed")
    raise SystemExit(0 if result['passed'] else 1)
checks={}
def check(name, condition):
    checks[name]=bool(condition)
    assert condition, name
def no_judge(*a,**kw): raise AssertionError('A host test must never call a vision judge')
with SimulatorDevice(ROOT/'build/lvgl_sim.exe') as d:
    check('ping',d.command('PING')=='OK')
    initial=d.tree()
    check('portrait',initial['screen']==[240,320])
    check('exact_ids',set(initial['by_id'])=={'lbl_note'}|{f'key_{c}' for c in 'abcdefghijklmnopqrstuvwxyz'})
    raw=d.framebuffer();check('rgb565_size',len(raw)==153600)
    check('dark_background',struct.unpack_from('<H',raw,2*(319*240+239))[0]==0x10A3)
    for c in 'abcdefghijklmnopqrstuvwxyz':check('tap_'+c,d.tap('key_'+c) is None)
    check('alphabet_state',d.tree()['by_id']['lbl_note']['text']=='ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    dark=d.framebuffer();dark_tree=d.tree();d.set_theme(True);light=d.framebuffer()
    check('light_pixels_change',dark!=light)
    check('light_state_preserved',d.tree()==dark_tree)
    d.capture(out/'light')
    d.set_theme(False);check('dark_roundtrip_pixels_identical',dark==d.framebuffer())
    d.capture(out/'dark')
    check('unknown_id_rejected',d.tap('unknown')=='unknown widget id')
    check('drag_non_slider_rejected',d.drag('key_a',50)[1]=='only sliders and arcs can be dragged')
    check('no_board_shot_command',d.command('SHOT')=='ERR unknown command')
    d.reset_ui();check('reset_clears_note',d.tree()['by_id']['lbl_note']['text']=='')
    w=d.tree()['by_id']['key_z'];check('coordinate_tap',d.command(f"TAP {w['x']+w['w']//2} {w['y']+w['h']//2}")=='OK')
    check('coordinate_note',d.tree()['by_id']['lbl_note']['text']=='Z')
    check('idle',d.wait_idle())
    geo=d.geometry();check('labels_checked',geo['labels_checked']==29)
    check('initial_geometry',not geo['clipped_labels'] and not geo['outside_screen'] and not geo['overlapping_interactive'])
    d.reset_ui()
    for _ in range(82):d.tap('key_w')
    check('firmware_note_limit',len(d.tree()['by_id']['lbl_note']['text'])==79)
    check('detects_clipped_long_note',d.geometry()['clipped_labels']>0)
    d.capture(out/'long-note')
    spec={'intent':'Alphabet keyboard','widgets':[{'id':'lbl_note'},{'id':'key_a'},{'id':'key_b'}],
          'tests':[{'name':'Type AB','steps':[{'tap':'key_a'},{'tap':'key_b'},
             {'expect':{'lbl_note':{'text':'AB'}}},{'capture':{'label':'AB','expect_visual':['note reads AB']}}]},
             {'name':'Independent reset','steps':[{'expect':{'lbl_note':{'text':''}}},{'capture':{'label':'empty','expect_visual':[]}}]}]}
    report=run_spec(spec,d,None,out/'spec',judge=no_judge)
    check('same_spec_runner',report['passed'])
    for p in ['initial','Type_AB/04_AB','Independent_reset/02_empty']:
        target=out/'spec'/p
        check('capture_'+p,(target/'shot.png').exists() and (target/'tree.json').exists())
    check('firmware_unmodified',hashlib.sha256((ROOT.parent/'lvgl_ui/generated_ui.cpp').read_bytes()).hexdigest()==
          json.loads((ROOT/'provenance.json').read_text())['generated_ui_sha256'])
(out/'host.json').write_text(json.dumps({'passed':all(checks.values()),'checks':checks},indent=2))
print(f'{len(checks)} integration checks passed')
