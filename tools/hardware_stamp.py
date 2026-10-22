"""PlatformIO pre-build hook: identify the exact UI compiled for the ESP32."""
Import('env')
from pathlib import Path
import hashlib
root=Path(env.subst('$PROJECT_DIR'))
build=Path(env.subst('$BUILD_DIR'))
build.mkdir(parents=True,exist_ok=True)
digest=hashlib.sha256((root/'lvgl_ui/generated_ui.cpp').read_bytes()).hexdigest()
header=build/'hardware_stamp.h'
text='#pragma once\n#define IOT_UI_SHA "'+digest+'"\n'
if not header.exists() or header.read_text()!=text:header.write_text(text)
env.Append(CPPPATH=[str(build)])
