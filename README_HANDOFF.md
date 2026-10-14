# IOT bench — handoff for fixing the program

Give this file to whoever has to make the project work again, including another coding assistant. It describes the goal, the hardware, how the simulator and the physical screen stay together, and where to look when something breaks.

The project folder is the directory that contains this file, `Start-IOT.cmd`, `platformio.ini`, `simulator/`, `lvgl_ui/`, `mirror/`, and `tools/ui_generator/`.

## Do this first

Set up the software and the API key first. Plug in the display and open the app before asking for a UI. The API key is not a file you paste into the chat.

1. Install Python 3 and Node.js. In a terminal, from this folder:

```powershell
python -m pip install -r tools/ui_generator/requirements.txt
python -m pip install platformio
```

2. Put the API key in a file named `.env` in this same folder (next to `Start-IOT.cmd`). Copy `.env.example` to `.env`, then edit `.env`. Leave `FLASH=0`. Set the key on a line with no `#` in front of it:

```
GENERATOR_PROVIDER=gemini
GEMINI_API_KEY=the-key-from-https://aistudio.google.com/apikey
GEMINI_MODEL=gemini-3.8-flash
```

Use an OpenAI key only if you switch the provider to `openai` and set `OPENAI_API_KEY` and `OPENAI_MODEL=gpt-4.1`. Do not commit `.env` and do not send the key in chat.

3. Build the desktop app once. LVGL and the Zig compiler are not in git. Download LVGL tag `v8.3.11` into `simulator/vendor/lvgl`, and Zig Windows x86_64 0.13.0 into `simulator/vendor/zig-windows-x86_64-0.13.0` (the file `zig.exe` must be directly inside that folder). Then:

```powershell
cd simulator
npm install
python build.py
cd ..
```

4. Wire the ILI9341 to the ESP32 using the pin table below, if it is not already wired. Plug the ESP32 into the laptop with USB. Close any serial monitor first.

5. Open the app with `Start-IOT.cmd` and leave that terminal open. Wait until the window says **Tap the physical screen or the simulator window**. The first connection uploads the mirror program, which can take a few minutes. The panel should already be showing the same picture as the simulator before anyone asks for a new UI.

6. Then ask for the UI in the chat at http://127.0.0.1:8765. The tests run on that picture, so both screens show them. Do not touch the panel while the tests are running.

7. When the tests pass, click the simulator glass or tap the physical panel. Both change the same interface.

## What this is

The user describes a small screen interface in a chat (“a light switch with a brightness slider”). An AI writes LVGL C++ for a 2.8 inch, 240×320 display. The PC compiles that exact file, runs the tests the AI wrote, and repairs the code if the tests fail. When a version passes, it appears on a desktop view of the bench.

If the ESP32 and its real display are plugged into the laptop, that physical panel shows the same interface. After the automatic tests finish, a click on the simulator window and a tap on the physical panel do the same thing. Both views then update from that one result.

## Goal

One interface, checked on the PC, then visible and usable on the real ILI9341 while the board is plugged in.

- The user asks for a UI in the chat.
- The generator writes `lvgl_ui/generated_ui.cpp` and `lvgl_ui/ui_spec.json`.
- The PC builds that C++ with LVGL 8.3.11 and runs the spec: taps, drags, widget state, layout, and optional PNG review of the framebuffer.
- Failed checks go back to the generator. Up to six attempts. If all fail, the last passing UI stays on screen.
- The passing picture is what the desktop glass shows.
- The same picture is copied to the physical panel over USB.
- After testing finishes, either the mouse or a finger can drive it.

`FLASH=0` is required for this workflow. The chat must not flash the generated UI onto the board by itself. The board, when used, runs a separate mirror program that only paints pixels and reports touch.

## The old camera path, and why it is not the current path

The original tool was a hardware rig:

1. Flash `lvgl_ui_test` onto the ESP32.
2. The firmware runs LVGL and answers serial commands (`PING`, `TREE`, `TAP`, `DRAG`, `WAIT_IDLE`, `RESET_UI`). Replies start with `@@`.
3. A USB webcam, aimed at the panel, takes photos. Settings that belonged to that rig: 1600×1200, exposure −6, white balance 6500 K, a burst of 3, keep the sharpest frame.
4. Those photos were compared with what LVGL drew, and a model judged whether the screen looked right.

That code is still in the repo (`tools/ui_generator/camera.py`, `judge.py`, `device_runner.py`, the `lvgl_ui_test` PlatformIO environment). It is the board path. `Start-IOT.cmd` does not use it.

The current path keeps the same UI source and the same 240×320 RGB565 pixels, and runs the tests on a PC build of LVGL (`simulator/host/sim_main.cpp`). Captures are framebuffer PNGs, not photographs. `SIM_VISION_JUDGE=1` sends those PNGs to the image judge. There is no webcam in this loop.

The desktop window still has a “Look through the camera” control. That is a 3D illustration of the old webcam seat. Focus blur and glare in that view are drawings. They are not applied to the physical panel, and they are not what the tests score.

Do not “fix” a simulator failure by turning the camera back on or by setting `FLASH=1`, unless the user explicitly asks to return to the old board-and-camera rig.

## What is the same on both screens

After the tests pass there is one LVGL program, on the PC. The simulator window and the physical panel are two views of it.

- The panel is painted from the PC framebuffer: 240×320, rotation 0, RGB565, little-endian, the same bytes LVGL flushed.
- A click on the glass in the simulator sends `TAP x y` or `DRAG id value` into that program.
- A finger on the panel is read by the XPT2046, converted with the calibration below, and sent into that same program as the same kind of tap or slider drag.
- The new picture is then copied back to the panel.

During automatic tests the tests own the glass. The window says so. Touches on the physical panel are ignored until `simulator/build/testing.json` expires. After that, both sides work.

Practical limits, so nobody claims more than the rig does:

- The panel can lag. A small change is a fraction of a second. A full-screen change is slower because the whole frame goes over USB serial at 921600 baud.
- The panel backlight does not match the laptop’s colors exactly. The pixel values are the same numbers.
- A finger can land a few pixels away from a precise mouse click. The calibration is the one measured for this board.
- The table, clamps, walk-around camera, blur, and glare exist only in the desktop window. The physical panel shows only the 240×320 interface.
- The ESP32 is not executing `generated_ui.cpp` in this mode. It executes `mirror/main.cpp`, which paints the PC’s pixels and reports touch. The phrase “Ready for real board” means the PC-tested source matches the files on disk. It does not mean the mirror program was replaced with the standalone UI firmware.

## Hardware

ESP32 DevKit V1, CP2102 USB-serial, PlatformIO board `esp32doit-devkit-v1`. Red 2.8 inch ILI9341, 240×320 portrait, XPT2046 touch on the same SPI bus with its own chip select. Power the display from 3.3 V. Do not put 5 V on the SPI pins. The backlight LED is tied to 3.3 V and has no GPIO.

| Signal | GPIO |
| --- | --- |
| TFT_MISO | 19 |
| TFT_MOSI | 23 |
| TFT_SCLK | 18 |
| TFT_CS | 5 |
| TFT_DC | 15 |
| TFT_RST | 4 |
| TOUCH_CS | 21 |
| VCC | 3.3 V |
| GND | GND |

Pin definitions live in `include/User_Setup.h`. The mirror firmware and the real UI firmware both use that file. Touch calibration at rotation 0 is `{418, 3255, 338, 3334, 2}` (`x0`, x span, `y0`, y span, flags). Flag 2 inverts X. The copy the mirror uses is the array `touchCal` in `mirror/main.cpp`. If the real calibration in `include/touch_calibration.h` changes, change `touchCal` to the same five numbers.

`HARDWARE.md` is the longer hardware note. Header positions in the 3D model are schematic. Trust the table above for wiring.

## How to start it

On Windows, double-click `Start-IOT.cmd`. Leave the terminal open. It starts:

1. `tools/ui_generator/server.py` at http://127.0.0.1:8765 with `FLASH=0`.
2. The Electron bench in `simulator/`, with `IOT_MIRROR=1`.

In the bench window, open the chat and describe a UI. When the tests pass, the glass updates by itself. Plug the ESP32 in before or after launch. The header line changes as the link comes up:

- “Plug in the ESP32 screen…” means no board was found.
- “Flashing the screen…” means the mirror program is being uploaded. The first time can take a few minutes.
- “Tap the physical screen or the simulator window” means the panel is following and touch is live.
- A busy-port or flash error is shown in that same line and in the terminal as `[bench] …`.

Close any serial monitor, Arduino IDE, or other program that has the COM port open. The simulator needs that port.

The first successful mirror upload replaces whatever firmware was on the ESP32. To put a standalone UI back on the board later, from this folder:

```powershell
python -m platformio run -e lvgl_ui -t upload
```

Add `--upload-port COM4` with the real port if it guesses wrong. That build runs the UI on the ESP32 and does not follow the simulator. Use the mirror workflow again afterwards and the simulator will upload `mirror/main.cpp` once more.

## Desktop controls

- Drag to orbit, right-drag to pan, scroll to dolly. Click the view, then WASD walks around the table.
- Click the glass for a tap. Drag a slider on the glass to change its value.
- Inspect glass / Whole bench change the camera. They do not change the UI.
- Show the light theme works only when both palettes were built and tested. The default is the requested palette, usually light (`UI_PRESENTATION_THEME=light`, `SIM_TEST_PALETTES=selected`).
- Save capture writes `simulator/captures/<timestamp>/` with `shot.png`, `frame.rgb565`, `tree.json`, and `geometry.json`.
- Reset UI restores the generated screen.

## Software pieces

| Piece | Role |
| --- | --- |
| `Start-IOT.cmd` | Checks that `simulator/build/lvgl_sim.exe` and Electron exist, then runs `simulator/launch.py`. |
| `simulator/launch.py` | Starts the chat server with `FLASH=0` and the bench with `IOT_MIRROR=1`. |
| `tools/ui_generator/server.py` | Chat at port 8765. Calls the generator, compiler, and host tests. |
| `tools/ui_generator/pipeline.py`, `host_sim.py`, `spec_runner.py` | Write the UI, build the PC executable, run the spec, optional PNG judge. |
| `simulator/build/active.json` | Last accepted build. The bench reloads when this file changes. |
| `simulator/build/testing.json` | Present while automatic tests own the glass. Physical touch is ignored until `expires`. |
| `simulator/desktop.cjs`, `bench.js` | Electron window and the 3D glass. Polls the framebuffer about 5 times a second. |
| `simulator/bridge.py` | Talks to the PC LVGL process. Forwards physical taps and slider drags. Serves frames to the window. |
| `simulator/mirror_link.py` | Finds the ESP32, flashes the mirror if needed, sends changed rows, reads `@@TOUCH` lines. |
| `simulator/host/sim_main.cpp` | PC LVGL. Same `generated_ui.cpp`, 240×320, RGB565. Commands match the board protocol, plus `FRAME`, `GEOMETRY`, `RANGES`. |
| `mirror/main.cpp` | ESP32 program. Paints strips and reports touch. No LVGL. |
| `lvgl_ui/generated_ui.cpp` | The current interface. Shared source for the PC build and for a future real-board build. |
| `lvgl_ui/main.cpp` | Real-board LVGL firmware (display flush and touch). Not what the mirror runs. |
| `platformio.ini` environment `mirror` | Builds and uploads `mirror/main.cpp`. |
| `platformio.ini` environment `lvgl_ui` | Standalone UI on the ESP32. |
| `platformio.ini` environment `lvgl_ui_test` | Standalone UI plus the serial test hooks. Old camera/board path. Do not use it while the mirror link is running. |

Python 3 must be on `PATH`. This machine uses the `python` launcher. PlatformIO is installed as `python -m platformio` (the `pio` command may be absent). pyserial is required. UI-generator extras are listed in `tools/ui_generator/requirements.txt`.

Copy `.env.example` to `.env` and set a real API key. Never commit `.env` or paste the key into chat.

Important `.env` values for this workflow:

```
FLASH=0
TESTS=1
GENERATOR_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.8-flash
UI_PRESENTATION_THEME=light
SIM_VISION_JUDGE=1
SIM_JUDGE_PROVIDER=gemini
SIM_TEST_PALETTES=selected
```

`UPLOAD_PORT=COM4` is optional. Set it when more than one USB-serial device is plugged in. The mirror looks for USB VID `10C4` (CP210x), `1A86` (CH340), or `0403` (FTDI).

`IOT_MIRROR=1` is set by `launch.py` and by `simulator/desktop.cjs`. Set `IOT_MIRROR=0` only to debug the window with no serial port. Smoke-test launches force it off.

## Mirror protocol

Baud 921600, 8N1. The ESP32 prints `@@MIRROR 2 240 320` until the PC says hello. Version 2 is required because version 1 painted pixels and did not report touch. A board still on version 1 is reflashed.

| Direction | Message |
| --- | --- |
| Device, until linked | `@@MIRROR 2 240 320` |
| PC | `HELLO` then the device replies `@@OK` |
| PC | `VER` then the device replies `@@MIRROR 2 240 320` |
| PC | `PIX <y> <rowCount> <crc32>` plus raw bytes, then the device replies `@@OK` or `@@ERR` |
| Device, any time after link | `@@TOUCH <x> <y> <1 or 0>` |

`PIX` rows are little-endian RGB565, 240 pixels wide, at most 8 rows. The CRC is `zlib.crc32` of those bytes, which matches `esp_crc32_le(0, …)` on the ESP32. The device draws with `pushColors(..., swap=true)`, the same swap the real firmware uses in `lvgl_ui/main.cpp`.

Touch `1` means pressed, `0` means released. The PC ignores touches while tests are running. A short press becomes `TAP x y`. A press on a slider becomes `DRAG <id> <value>`, using the same hit testing as `simulator/bench.js`. The PC then reads the new framebuffer and queues it for the panel.

`simulator/test_mirror.py` checks row packing and touch-line parsing. It does not need a board:

```powershell
python simulator/test_mirror.py
```

Rebuild the mirror firmware, from the project folder, with:

```powershell
python -m platformio run -e mirror
```

The simulator uploads it itself when the plugged-in board does not answer as version 2.

## If it does not work

Work down this list. Read the `Start-IOT.cmd` terminal and any `[bench]` lines before changing code.

**The window never opens.** `simulator/build/lvgl_sim.exe` missing: from `simulator/`, run `python build.py` (needs the pinned Zig toolchain and LVGL under `simulator/vendor/`). Electron missing: from `simulator/`, run `npm install`. Python missing from `PATH`: install Python 3 and retry.

**Port 8765 is already in use, or the terminal says the server belongs to another project or to board mode.** Close the old terminal that is running `server.py`. Board mode means that process was started with `FLASH` not equal to 0. This workflow must stay on `FLASH=0`.

**The chat fails before any UI appears.** The API key, provider, or model in `.env` is wrong or empty. Restart `Start-IOT.cmd` after changing `.env`. An inherited environment variable overrides `.env`.

**Tests fail and the glass never changes.** That is the generator/repair loop, not the screen cable. Read the terminal and `tools/ui_generator/runs/`. The last accepted UI stays in `simulator/build/active.json`. Do not delete that file to “reset” unless a new passing build exists.

**The physical panel stays blank or keeps its old UI.** Confirm the wiring table, 3.3 V, and a common ground. Confirm the COM port is free. The status line should pass through “Flashing the screen” once, then “Tap the physical screen…”. If it says the port is busy, close the other program. If flashing fails, run `python -m platformio run -e mirror -t upload` from the project folder and read the last error. If PlatformIO is missing: `python -m pip install platformio`.

**The panel shows the UI but touch does nothing.** The board is probably still on mirror version 1, or `VER` is not answered. Opening the simulator again should reflash version 2. Touch and display share SPI; `TOUCH_CS` must be GPIO 21. A tap is acted on at finger-up, same as a mouse click. Drag only sliders. Touches during the automatic tests are dropped on purpose.

**The panel and the window disagree.** They only agree while the mirror link is up and the tests are finished. A full-screen update can take a couple of seconds. If the link drops, the window keeps working and the panel freezes on the last strips it received.

**Colors are swapped or the image is mirrored.** Do not invent a new pinout. Compare `mirror/main.cpp` `pushColors(..., true)` with `lvgl_ui/main.cpp`, and compare `touchCal` with `include/touch_calibration.h`. Both already match this board.

**Someone asks to flash `lvgl_ui_test` while the simulator is open.** That fights the mirror for the serial port and replaces the mirror program. Stop the simulator first.

## What to leave alone unless the task says otherwise

- `tools/ui_generator/system_prompt.txt` rules, `validator.py`, and `spec.py`.
- The `@@` command set in `lvgl_ui/test_hooks.cpp`.
- `include/lv_conf.h` and the LVGL 8.3.11 pin.
- `.env` secrets. Do not copy them into a reply.
- Do not regenerate `lvgl_ui/generated_ui.cpp` by hand between a passing preview and a deliberate board upload. The bench and a later `lvgl_ui` build are meant to share that file.

## Short check that the current design is intact

1. `Start-IOT.cmd` prints `FLASH=0` and the mirror sentence.
2. The chat can produce a UI, the tests run without a camera, and the desktop glass updates only after a pass.
3. With the ESP32 plugged in, the status becomes “Tap the physical screen or the simulator window”.
4. After the tests finish, a mouse click and a finger tap change the same widget, and both screens show the result.
