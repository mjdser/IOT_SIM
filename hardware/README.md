# Real ESP32 + USB screenshots

This mode runs `lvgl_ui/generated_ui.cpp` on the **actual ESP32**, compiled with
LVGL 8.3.11. The PC sends the existing test commands and assembles RGB565 strips
into 240×320 PNG screenshots. No native simulator, webcam, or PC-to-board mirror
runs in this mode. The existing generator, validator, test specification and
repair loop are reused.

## Start on your teammate's Windows PC

1. Copy this project to a local folder. Install Python 3.12 and run:
   `python -m pip install platformio pyserial opencv-python`
   (OpenCV remains an import dependency of the original pipeline; no camera opens.)
2. Put your own API configuration in `.env`, using `.env.example`. Do not share keys
   or commit `.env`. Existing Gemini provider settings can be used.
3. Close any simulator server on port 8765 and any serial monitor.
4. Double-click `Start-Hardware.cmd` (also the new default `Start-IOT.cmd`).
   The browser opens `http://127.0.0.1:8765/hardware`. Keep the terminal open.
5. Connect the configured ESP32 DevKit V1 by a **data-capable USB cable**.
6. On first use, expand **First connection / install firmware**, choose its COM
   port, then explicitly confirm **Install capture firmware**. This replaces
   the firmware already on that board with this project's current generated UI.
   Merely plugging in a board does not upload anything.
7. Wait for the `IOT-CAPTURE-1` handshake and real screenshot. If multiple capture
   boards are attached, set `UPLOAD_PORT=COMx` in `.env` and restart.
8. Use the existing chat to request interfaces. Requests now compile/upload to
   the identified board, run `ui_spec.json` there, collect screenshots and repair
   failed UI checks. A missing board blocks the request before generation.

To compile only, without any board: `pio run -e lvgl_ui_capture`.
To upload manually: `pio run -e lvgl_ui_capture -t upload --upload-port COMx`.
The old camera workflow can still be run separately with `lvgl_ui_test` and
`IOT_TARGET` unset. Never use the `mirror` firmware for this new workflow: it
runs UI on the PC, which is the opposite direction.

## What is and isn't tested

- Standard PING, TREE, TAP_ID, TAP, DRAG, WAIT_IDLE and RESET_UI run on the board.
- The saved `generated_ui.cpp` and `ui_spec.json` are used directly; the board
  reports its compiled UI SHA-256, checked before the automated tests.
- Capture files include `shot.png`, raw RGB565, TREE and device metadata.
- UI image judging uses the same cached PNG judge as the simulator, when
  `SIM_VISION_JUDGE=1`. It checks layout, readability and the requested content.
- The selected palette is tested directly; no camera dark-first conversion.
- Registered-widget bounds and applicable task-layout checks are shared.
  Host-only deep label/overlap geometry checks are NOT reported as passing on
  the board. PNG visual review still checks these visually.
- Test commands inject LVGL input. They do not verify physical touch calibration.
- USB screenshots observe rendered pixels, not physical glass/backlight/wiring.
- Wi-Fi, Bluetooth and sensors run on hardware **if the firmware implements
  them**. This does not add such features or lift existing generator restrictions.
  A generated demo with mock data still uses mock data on the board.

## Capture limitations

The board retains the existing 240×10 draw buffer. No additional 153,600-byte
framebuffer is allocated there. FRAME requests trigger a synchronous full redraw;
each strip is sent as little-endian RGB565 with a CRC32. The PC rejects missing,
corrupted or truncated strips rather than treating them as UI failures.

Serial is 921600 baud. A full image alone takes at least about 1.7 seconds on
the wire; the viewer is periodically refreshed, **not real-time video**. USB
capture adds CPU/serial overhead and briefly delays input. Don't use these
captures to claim uninstrumented timing or animation-performance equivalence.
Concurrent application tasks must not write unframed debug text to this serial
port during binary transfers. A transfer fault disconnects and reconnects the
client; it must not trigger an AI layout repair.

One process owns the port. During generation, upload and automatic tests the
manual viewer controls are blocked. The viewer shows actual test screenshots.
On disconnect it clears the image instead of displaying a simulated substitute.

## First physical acceptance test (still required)

1. Confirm correct portrait orientation and colours on the real display and PC.
2. Capture a screenshot, verify it is complete, then compare it with the glass.
3. Tap on the physical screen and confirm the next screenshot reflects the state.
4. Tap/drag from the PC and confirm the physical screen changes accordingly.
5. Generate a small interface; verify board upload, test progress and screenshots.
6. Unplug/replug USB: ensure the PC clears stale pixels and reconnects.
7. Check the actual RAM/heap stability and responsiveness on the board.

Source and offline checks are prepared without a board. Compilation and fake
serial transport tests cannot prove physical operation. No board was flashed
while preparing this handoff.
