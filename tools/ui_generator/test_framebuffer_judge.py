import json,os,tempfile,unittest
from pathlib import Path
from unittest import mock
import framebuffer_judge as j
import gemini_client

class FramebufferJudgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.png=self.root/'shot.png';self.png.write_bytes(b'\x89PNG\r\n\x1a\nunit fixture')
        self.caps=[{'label':'initial','photo':self.png,'after':'initial dark palette','expect_visual':['Readable contrast']}]
        p=mock.patch.dict(os.environ,{'SIM_JUDGE_PROVIDER':'openai','OPENAI_JUDGE_MODEL':'m'});p.start();self.addCleanup(p.stop)
    def reply(self,passed=True):return json.dumps({'captures':[{'label':'initial','criteria':[{'criterion':'Readable contrast','pass':passed,'reason':'Visible text has insufficient contrast' if not passed else 'Clear text'}]}]})
    def call(self,fn):return j.judge_captures('review','A keyboard',self.caps,generate=fn,cache_dir=self.root/'cache')
    def test_image_is_sent_and_identical_reviews_are_cached(self):
        client=mock.Mock(return_value=self.reply())
        failures,verdict=self.call(client);self.assertEqual(failures,[]);self.assertFalse(verdict['cached'])
        prompt,messages=client.call_args.args
        self.assertIn('independently',prompt);self.assertEqual(len(messages),1)
        self.assertTrue(any(p.get('type')=='image_url' for p in messages[0][1]))
        self.assertNotIn('generated_ui.cpp',json.dumps(messages))
        _,cached=self.call(client);self.assertTrue(cached['cached']);self.assertEqual(client.call_count,1)
        self.png.write_bytes(self.png.read_bytes()+b'changed');self.call(client);self.assertEqual(client.call_count,2)
    def test_failed_visual_result_enters_repair_failure_format(self):
        failures,_=self.call(mock.Mock(return_value=self.reply(False)))
        self.assertEqual(failures[0]['kind'],'visual');self.assertIn('insufficient contrast',failures[0]['actual'])
    def test_incomplete_verdict_is_retried_and_never_cached_as_success(self):
        client=mock.Mock(return_value='{"captures":[]}')
        with self.assertRaises(gemini_client.GeminiError):self.call(client)
        self.assertEqual(client.call_count,2);self.assertFalse((self.root/'cache').exists())
    def test_criteria_changes_invalidate_cache(self):
        client=mock.Mock(return_value=self.reply());self.call(client)
        self.caps[0]['after']='after clicking';self.call(client);self.assertEqual(client.call_count,2)
    def test_only_initial_root_palette_criteria_are_normalised(self):
        criteria=['The screen background is dark.','White text has clear contrast','The button background is red.','Background is pure white #FFFFFF']
        fixed=j.initial_criteria(criteria,'light')
        self.assertIn('light compile-time',fixed[0]);self.assertEqual(fixed[1:],criteria[1:])

if __name__=='__main__':unittest.main()
