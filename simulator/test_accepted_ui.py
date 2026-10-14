"""Compiled-palette, reload and rollback integration using a saved accepted reply.

No AI calls. The production source/theme/spec and accepted manifest are preserved.
"""
from pathlib import Path
import sys,json,copy
from unittest import mock
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'tools/ui_generator'))
import pipeline,host_sim,spec
import bridge

def run_locked():
    originals={p:p.read_bytes() if p.exists() else None for p in
               (pipeline.TARGET,pipeline.THEME_FILE,pipeline.SPEC_FILE)}
    manifest_original=host_sim.ACTIVE.read_bytes()
    original=json.loads(manifest_original)
    code=pipeline.TARGET.read_text(encoding='utf-8')
    current_spec=json.loads(pipeline.SPEC_FILE.read_text(encoding='utf-8'))
    current_spec['theme']='light'
    report={}
    output=ROOT/'test-results/compiled-theme-active.json'
    preview=bridge.Preview()
    original_pid=preview.device.process.pid
    def no_network(*a,**kw):raise AssertionError('No API call allowed during saved-reply tests')
    try:
        with mock.patch.object(host_sim,'ACTIVE',output),mock.patch.object(pipeline.gemini_client,'generate',no_network),mock.patch.object(pipeline.openai_client,'generate',no_network):
            reply=spec.join_reply(code,json.dumps(current_spec))
            result=pipeline._run('Saved-reply integration test: compile both palettes',get_code=lambda *a:reply)
            assert result.ok and result.theme=='light' and result.tests=='passed'
            report['both_palettes_tested']=True
            with mock.patch.object(bridge,'ACTIVE',output):
                data=preview.execute({'action':'frame'})
                report['live_reload']=preview.device.process.pid!=original_pid and data['build']['revision']!=original['revision']
                sw=next(w for w in data['tree']['widgets'] if w['type']=='switch')
                slider=next(w for w in data['tree']['widgets'] if w['type']=='slider')
                preview.execute({'action':'tap_id','id':sw['id']})
                light=preview.execute({'action':'drag','id':slider['id'],'value':75})
                dark=preview.execute({'action':'theme','light':False})
                report['theme_preserves_tree']=light['tree']==dark['tree']
                report['compiled_palette_changes_pixels']=light['frame']!=dark['frame']
                roundtrip=preview.execute({'action':'theme','light':True})
                report['roundtrip_pixels']=light['frame']==roundtrip['frame']
                report['source_unchanged']=host_sim.digest(pipeline.TARGET)==original['source_sha256']
                accepted=output.read_bytes()
                with mock.patch.object(pipeline,'MAX_ATTEMPTS',1):
                    failed=pipeline._run('Reject malformed response',get_code=lambda *a:'not C++')
                report['failed_attempt_preserves_manifest']=not failed.ok and output.read_bytes()==accepted
                report['failed_attempt_preserves_live_state']=preview.execute({'action':'frame'})['tree']==roundtrip['tree']
            report['production_manifest_unchanged']=host_sim.ACTIVE!=bridge.ACTIVE and bridge.ACTIVE.read_bytes()==manifest_original
    finally:
        preview.close()
        for path,data in originals.items():
            if data is None:path.unlink(missing_ok=True)
            else:path.write_bytes(data)
    report['production_source_restored']=host_sim.digest(pipeline.TARGET)==original['source_sha256']
    assert all(report.values()),report
    (ROOT/'test-results/compiled-theme.json').write_text(json.dumps({'passed':True,'checks':report},indent=2))
    print(f'{len(report)} compiled-theme/reload checks passed')

if __name__=='__main__':
    with host_sim.source_lock():run_locked()
