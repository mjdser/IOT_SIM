"""Offline contract tests, not evidence of operation on a physical board."""
import io,json,struct,tempfile,unittest,zlib,contextlib,os
from pathlib import Path
from unittest import mock
from hardware.device import read_frame,png_bytes,CaptureDevice,SIZE
from device_runner import DeviceError,BoardCrash
from hardware import target as hardware_target

def wire(rows=320,corrupt=False,wrong_id=False):
    data=bytearray(b'@@FRAME_BEGIN 1 240 320\r\n')
    for y in range(0,rows,10):
        raw=(b'\x00\xf8' if y<160 else b'\x1f\x00')*240*10
        crc=zlib.crc32(raw)^(1 if corrupt else 0)
        data.extend(f'@@STRIP {2 if wrong_id else 1} 0 {y} 240 10 4800 {crc}\r\n'.encode()+raw+b'\r\n')
    data.extend(f'@@FRAME_END 1 {rows//10}\r\n'.encode())
    return bytes(data)

class ProtocolTests(unittest.TestCase):
    def test_exact_red_blue_frame(self):
        raw=read_frame(io.BytesIO(wire()))
        self.assertEqual(len(raw),SIZE)
        self.assertEqual(raw[:2],b'\0\xf8');self.assertEqual(raw[-2:],b'\x1f\0')
    def test_crc_rejects_corruption(self):
        with self.assertRaisesRegex(DeviceError,'CRC'):read_frame(io.BytesIO(wire(corrupt=True)))
    def test_missing_rows_rejected(self):
        with self.assertRaisesRegex(DeviceError,'coverage'):read_frame(io.BytesIO(wire(rows=310)))
    def test_wrong_frame_id_rejected(self):
        with self.assertRaises(DeviceError):read_frame(io.BytesIO(wire(wrong_id=True)))
    def test_bounds_rejected_before_payload(self):
        with self.assertRaises(DeviceError):read_frame(io.BytesIO(b'@@FRAME_BEGIN 1 240 320\n@@STRIP 1 239 0 2 1 4 0\n'))
    def test_truncation_rejected(self):
        with self.assertRaises(DeviceError):read_frame(io.BytesIO(wire()[:100]),timeout=.01)
    def test_restart_rejected(self):
        with self.assertRaises(BoardCrash):read_frame(io.BytesIO(b'@@READY\n'))
    def test_wrong_dimensions_rejected(self):
        with self.assertRaises(DeviceError):read_frame(io.BytesIO(b'@@FRAME_BEGIN 1 320 240\n'))
    def test_png_has_exact_dimensions_and_colour(self):
        png=png_bytes(b'\0\xf8'*76800)
        self.assertEqual(struct.unpack('>II',png[16:24]),(240,320))
        offset=8;pixels=b''
        while offset<len(png):
            n=struct.unpack('>I',png[offset:offset+4])[0];kind=png[offset+4:offset+8]
            if kind==b'IDAT':pixels+=png[offset+8:offset+8+n]
            offset+=n+12
        self.assertEqual(zlib.decompress(pixels)[:4],b'\0\xff\0\0')
    def test_transport_failure_closes_device(self):
        d=CaptureDevice('COM9');d.ser=mock.Mock();d.ser.readline.return_value=b'@@ERR unsupported\n'
        serial=d.ser
        with self.assertRaises(DeviceError):d.framebuffer()
        serial.close.assert_called_once();self.assertIsNone(d.ser)
    def test_no_host_geometry_claim(self):
        self.assertFalse(hasattr(CaptureDevice,'geometry'))

class SafetyTests(unittest.TestCase):
    def test_no_device_blocks_generation_before_yield(self):
        r=hardware_target.Runtime()
        with mock.patch.dict(os.environ,{'IOT_ALLOW_UPLOAD':'1'}),mock.patch.object(r,'connect',side_effect=DeviceError('No device')):
            with self.assertRaises(RuntimeError):
                with r.generation():self.fail('Should not generate or upload without a board')
        self.assertFalse(r.status()['busy']);self.assertFalse(r.job.locked())
    def test_generation_releases_serial_and_blocks_viewer(self):
        r=hardware_target.Runtime();d=mock.Mock();d.port='COM9';d.command.return_value='OK';r.device=d
        with mock.patch.dict(os.environ,{'IOT_ALLOW_UPLOAD':'1'}):
            with r.generation() as p:
                self.assertEqual(p,'COM9');d.close.assert_called_once()
                self.assertTrue(r.status()['busy']);self.assertIsNone(r.device)
                with self.assertRaises(RuntimeError):r.action({'action':'tap','x':1,'y':1})
        self.assertFalse(r.job.locked())
    def test_initial_install_requires_confirmation(self):
        r=hardware_target.Runtime()
        with mock.patch.dict(os.environ,{'IOT_ALLOW_UPLOAD':'1'}):
            with self.assertRaises(RuntimeError):r.action({'action':'install','port':'COM9'})
    def test_multiple_boards_not_selected_arbitrarily(self):
        r=hardware_target.Runtime()
        with mock.patch.dict(os.environ,{},clear=True),mock.patch.object(hardware_target,'ports',return_value=[{'port':'COM1'},{'port':'COM2'}]),mock.patch.object(hardware_target,'CaptureDevice') as cls:
            with self.assertRaisesRegex(DeviceError,'Multiple'):r.connect()
            self.assertIsNone(r.device)

class SharedRunnerTests(unittest.TestCase):
    def test_capture_device_uses_same_functional_spec_without_geometry(self):
        from test_spec_runner import FakeDevice
        from test_spec import GOOD_SPEC
        import spec_runner
        class DeviceWithCapture(FakeDevice):
            def capture(self,directory):
                p=Path(directory)/'shot.png';p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(png_bytes(b'\xff\xff'*76800));return p
        with tempfile.TemporaryDirectory() as tmp:
            result=spec_runner.run_spec(GOOD_SPEC,DeviceWithCapture(),None,Path(tmp),log=lambda _:None)
        self.assertTrue(result['passed'],result['failures'])

class PipelineTests(unittest.TestCase):
    def setUp(self):
        import pipeline,spec
        from test_pipeline_theme import CODE
        from test_spec import GOOD_SPEC
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.pipeline=pipeline
        self.source=self.root/'generated_ui.cpp';self.source.write_text('original')
        self.theme=self.root/'ui_theme.h';self.theme.write_text('#define UI_LIGHT_THEME 0')
        self.specfile=self.root/'ui_spec.json';self.specfile.write_text('{}')
        self.reply=spec.join_reply(CODE,json.dumps(dict(GOOD_SPEC,theme='light')))
        self.calls=[]
        def patch(obj,name,value):
            p=mock.patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
        for name,value in {'TARGET':self.source,'THEME_FILE':self.theme,'SPEC_FILE':self.specfile,
                           'RUNS_DIR':self.root/'runs','REJECTED_FILE':self.root/'rejected.cpp'}.items():patch(pipeline,name,value)
        patch(pipeline.project_state,'source_lock',lambda:contextlib.nullcontext())
        patch(hardware_target.runtime,'generation',lambda:contextlib.nullcontext('COM9'))
        patch(pipeline,'find_pio',lambda:'pio')
        patch(pipeline,'compile_ui',lambda p,e:(self.calls.append(('compile',e,'UI_LIGHT_THEME 1' in self.theme.read_text())) or (True,'')))
        patch(pipeline,'flash_ui',lambda p,port,e,log:(self.calls.append(('upload',e,port)) or (True,'')))
        patch(pipeline.camera,'settings_from_env',mock.Mock(side_effect=AssertionError('Camera must not open')))
        patch(pipeline,'switch_to_light',mock.Mock(side_effect=AssertionError('Must not reflash palette after tests')))
        self.test_result={'passed':True,'checks_passed':2,'checks_total':2,'photos':1,'visual':True,'failures':[]}
        self.runner=mock.Mock(side_effect=lambda *args:self.test_result)
        patch(hardware_target,'run_tests',self.runner)
        p=mock.patch.dict(os.environ,{'IOT_TARGET':'hardware_capture'});p.start();self.addCleanup(p.stop)
    def run_pipeline(self):
        return self.pipeline.run('light switch',flash=True,test=True,get_code=lambda *a:self.reply,log=lambda _:None)
    def test_real_target_selected_palette_and_shared_spec(self):
        result=self.run_pipeline()
        self.assertTrue(result.ok);self.assertEqual(result.target,'hardware_capture')
        self.assertEqual(self.calls,[('compile','lvgl_ui_capture',True),('upload','lvgl_ui_capture','COM9')])
        self.assertEqual(self.runner.call_args.args[0]['theme'],'light')
        self.assertEqual(result.theme,'light')
    def test_transport_failure_not_ai_repair_or_success(self):
        self.runner.side_effect=DeviceError('CRC mismatch')
        result=self.run_pipeline()
        self.assertFalse(result.ok);self.assertEqual(result.tests,'not_run')
        self.assertEqual(self.runner.call_count,1)
    def test_failed_ui_checks_are_retried(self):
        self.runner.side_effect=[dict(self.test_result,passed=False,failures=[{'kind':'state','test':'toggle','expected':'on','actual':'off'}]),self.test_result]
        result=self.run_pipeline()
        self.assertTrue(result.ok);self.assertEqual(self.runner.call_count,2)
    def test_compile_only_never_uploads_or_tests(self):
        with mock.patch.dict(os.environ, {'IOT_TARGET':''}):
            result=self.pipeline.run('light switch',get_code=lambda *a:self.reply,log=lambda _:None)
        self.assertTrue(result.ok)
        self.assertEqual(self.calls,[('compile','lvgl_ui',True)])
        self.runner.assert_not_called()

    def test_no_upload_permission_path(self):
        with self.assertRaises(RuntimeError):self.pipeline.run('request',flash=False,test=True)

if __name__=='__main__':unittest.main()
