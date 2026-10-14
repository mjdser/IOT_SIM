"""Exercise host selection, retries and rollback without any API/hardware access."""
import contextlib,json,tempfile,unittest
import os
from pathlib import Path
from unittest import mock
import pipeline,host_sim,spec,server
from test_pipeline_theme import CODE
from test_spec import GOOD_SPEC

class HostPipelineTests(unittest.TestCase):
    def setUp(self):
        p=mock.patch.dict(os.environ,{'SIM_TEST_PALETTES':'both'});p.start();self.addCleanup(p.stop)
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.events=[]
        self.source=self.root/'generated_ui.cpp';self.source.write_bytes(b'previous source\r\n')
        self.theme=self.root/'ui_theme.h';self.theme.write_bytes(b'#define UI_LIGHT_THEME 0\r\n')
        self.specfile=self.root/'ui_spec.json';self.specfile.write_text('previous spec')
        for name,value in {'TARGET':self.source,'THEME_FILE':self.theme,'SPEC_FILE':self.specfile,
                           'RUNS_DIR':self.root/'runs','REJECTED_FILE':self.root/'rejected.cpp'}.items():
            p=mock.patch.object(pipeline,name,value);p.start();self.addCleanup(p.stop)
        for obj,name in [(pipeline,'find_pio'),(pipeline,'flash_ui'),(pipeline,'run_tests'),
                         (pipeline.requirements,'derive'),(pipeline.camera,'settings_from_env')]:
            p=mock.patch.object(obj,name,side_effect=AssertionError('Host used forbidden '+name));p.start();self.addCleanup(p.stop)
        p=mock.patch.object(host_sim,'source_lock',lambda:contextlib.nullcontext());p.start();self.addCleanup(p.stop)
        def compile(directory):
            self.events.append(('compile',int('UI_LIGHT_THEME 1' in self.theme.read_text())))
            return True,'',directory/'lvgl_sim.exe'
        def tests(the_spec,exe,out,log):
            self.events.append(('test',int('UI_LIGHT_THEME 1' in self.theme.read_text())))
            return {'passed':True,'checks_passed':4,'checks_total':4,'photos':0,'failures':[]}
        for name,value in [('compile_host',compile),('run_tests',tests),('equivalent_palettes',lambda *a:True)]:
            p=mock.patch.object(host_sim,name,side_effect=value);p.start();self.addCleanup(p.stop)
        self.publisher=mock.patch.object(host_sim,'publish',return_value={'source_sha256':'fixture-hash'}).start()
        self.addCleanup(mock.patch.stopall)

    def run_with(self,theme='dark',get_code=None):
        reply=spec.join_reply(CODE,json.dumps(dict(GOOD_SPEC,theme=theme)))
        with mock.patch.object(pipeline,'default_generator',return_value=get_code or (lambda s,m:reply)):
            return pipeline.run('a switch',log=lambda *a:None)

    def test_default_no_flash_runs_host_and_never_uses_judge_or_pio(self):
        result=self.run_with()
        self.assertTrue(result.ok);self.assertEqual(result.target,'host')
        self.assertEqual(result.tests,'passed');self.assertFalse(result.flashed)
        self.assertEqual(self.events,[('compile',0),('test',0)])
        self.assertEqual(self.source.read_text(),CODE)
        self.assertEqual(json.loads(self.specfile.read_text())['theme'],'dark')
        self.assertIn('Ready for real board',server.result_message(result))

    def test_light_only_after_dark_passes(self):
        result=self.run_with('light')
        self.assertTrue(result.ok);self.assertEqual(result.theme,'light')
        self.assertEqual(self.events,[('compile',0),('test',0),('compile',1),('test',1)])
        self.assertIn('light',self.publisher.call_args.args[1])

    def test_light_layout_mismatch_requests_repairs_and_preserves_previous(self):
        with mock.patch.object(host_sim,'equivalent_palettes',return_value=False):result=self.run_with('light')
        self.assertFalse(result.ok)
        self.publisher.assert_not_called()
        self.assertEqual(self.source.read_bytes(),b'previous source\r\n')

    def test_failed_checks_retry_then_restore_every_source_without_publish(self):
        previous=[p.read_bytes() for p in (self.source,self.theme,self.specfile)]
        failure={'passed':False,'checks_passed':0,'checks_total':1,'photos':0,
                 'failures':[{'kind':'state','test':'tap','expected':'On','actual':'Off'}]}
        prompts=[]
        def generate(s,m):
            prompts.append(m[-1][1]);return spec.join_reply(CODE,json.dumps(GOOD_SPEC))
        with mock.patch.object(host_sim,'run_tests',return_value=failure):result=self.run_with(get_code=generate)
        self.assertFalse(result.ok);self.assertEqual(result.tests,'failed')
        self.assertEqual(len(prompts),pipeline.MAX_ATTEMPTS);self.assertIn('expected On, got Off',prompts[1])
        self.assertEqual([p.read_bytes() for p in (self.source,self.theme,self.specfile)],previous)
        self.publisher.assert_not_called()

    def test_api_failure_restores_previous_source(self):
        def unavailable(*a):raise pipeline.gemini_client.GeminiError('test unavailable')
        with self.assertRaises(pipeline.gemini_client.GeminiError):self.run_with(get_code=unavailable)
        self.assertEqual(self.source.read_bytes(),b'previous source\r\n');self.publisher.assert_not_called()

    def test_failure_is_sent_back_and_second_attempt_can_succeed(self):
        failure={'passed':False,'checks_passed':0,'checks_total':1,'failures':[
            {'kind':'layout','test':'Purple selection','expected':'no overlapping_text','actual':'Current: Purple overlaps Amber'}]}
        success={'passed':True,'checks_passed':1,'checks_total':1,'failures':[]}
        prompts=[]
        def generate(system,messages):
            prompts.append(messages[-1][1]);return spec.join_reply(CODE,json.dumps(GOOD_SPEC))
        with mock.patch.object(host_sim,'run_tests',side_effect=[failure,success]):result=self.run_with(get_code=generate)
        self.assertTrue(result.ok);self.assertEqual(len(prompts),2)
        self.assertIn('Current: Purple overlaps Amber',prompts[1])
        self.publisher.assert_called_once()

    def test_white_preference_rejects_dark_spec_and_repairs_it(self):
        replies=iter([spec.join_reply(CODE,json.dumps(GOOD_SPEC)),spec.join_reply(CODE,json.dumps(dict(GOOD_SPEC,theme='light')))])
        prompts=[]
        def generate(system,messages):prompts.append(messages[-1][1]);return next(replies)
        result=pipeline.run('white background',get_code=generate,presentation_theme='light',log=lambda *a:None)
        self.assertTrue(result.ok);self.assertEqual(result.theme,'light')
        self.assertIn('requested finished theme is light',prompts[1])

    def test_visual_judge_failures_trigger_code_repair(self):
        failure={'passed':False,'checks_passed':1,'checks_total':2,'failures':[
            {'kind':'visual','test':'image review','expected':'Readable contrast','actual':'Grey text is too faint','label':'initial'}]}
        success={'passed':True,'checks_passed':2,'checks_total':2,'visual':True,'photos':1,'failures':[]}
        prompts=[]
        def generate(system,messages):prompts.append(messages[-1][1]);return spec.join_reply(CODE,json.dumps(GOOD_SPEC))
        with mock.patch.object(host_sim,'run_tests',side_effect=[failure,success]):result=self.run_with(get_code=generate)
        self.assertTrue(result.ok);self.assertTrue(result.visual);self.assertEqual(result.photos,1)
        self.assertIn('Grey text is too faint',prompts[1]);self.assertEqual(len(prompts),2)

    def test_selected_white_palette_is_compiled_and_tested_once(self):
        with mock.patch.dict(os.environ,{'SIM_TEST_PALETTES':'selected'}):result=self.run_with('light')
        self.assertTrue(result.ok);self.assertEqual(result.theme,'light');self.assertEqual(result.palette_mode,'selected')
        self.assertEqual(self.events,[('compile',1),('test',1)])
        self.assertEqual(set(self.publisher.call_args.args[1]),{'light'})

    def test_conflicting_targets_are_rejected(self):
        with self.assertRaises(RuntimeError):pipeline.run('x',simulate=True,flash=True)

if __name__=='__main__':unittest.main()
