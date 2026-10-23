# Agentic UI — ESP32 project and hardware viewer

Describe an interface in the existing chat. The project generates and validates
`lvgl_ui/generated_ui.cpp` and `ui_spec.json`, compiles/uploads them to the ESP32,
executes the test steps there, and reviews screenshots received over USB. Failed
UI checks return to the generator for repair.

## Run

1. Install Python 3.12, then run `python -m pip install platformio pyserial opencv-python`.
2. Copy `.env.example` to `.env` and add your own API key.
3. Run `Start-IOT.cmd` or `Start-Hardware.cmd`.
4. Connect the configured ESP32. On first use, choose its port and explicitly
   install capture firmware from the viewer, then use the chat.

`Start-Simulator.cmd` remains a compatibility launcher for this same hardware
viewer. There is one viewer and one execution path behind these launchers.
The page is `http://127.0.0.1:8765/hardware`; the existing chat remains at `/`.
No npm, Electron or native PC LVGL build is needed.

## Code layout

- **`hardware/` — current viewer and USB capture integration.** Browser page,
  launcher, serial client, connection/upload coordination, and `firmware/`
  capture extension. See [hardware/README.md](hardware/README.md).
- **`lvgl_ui/` — application firmware.** Generated UI, the actual ESP32 main loop,
  shared serial test hooks and test specification.
- **`tools/ui_generator/` — project workflow.** Chat, AI clients, validator,
  spec parser, compile/upload/repair loop, test runner and image judge.
- **`include/`, `src/`, `lib/`, `test/`, `platformio.ini` — board configuration,
  supporting firmware and physical hardware tests. Build paths stay unchanged.
- **`reference/` and the other original project/documentation folders** retain
  the hardware references and original project material.
- **`runtime/`, `hardware/captures/`, `tools/ui_generator/runs/`** are ignored local
  state, screenshot caches and run evidence.

The old PC simulator, 3D bench, PC-to-board mirror firmware and their generated
test/build artifacts have been removed from the current tree.

## Build and test

Compile only: `pio run -e lvgl_ui_capture`.

Explicit upload: `pio run -e lvgl_ui_capture -t upload --upload-port COM4`.

Offline software tests: `python -m unittest discover -s tools/ui_generator -p "test_*.py"`.

The original camera-based workflow is retained as part of the project:
`python tools/ui_generator/generate.py "your request" --test`.
USB screenshots use `--hardware` instead. With neither flag the CLI compiles
ESP32 code only. See [the generator guide](tools/ui_generator/README.md).

## Verification limits

The ESP32 runs the UI and uses its own memory and peripherals. The PC manages
generation, build/upload, test commands and screenshot review. A screenshot
copies rendered RGB565 pixels and does not verify the display's wiring or
backlight. Injected test actions do not test physical touch calibration.
Capture adds overhead and updates periodically rather than providing live video.

Compilation and offline checks have passed; physical operation still requires
verification with the team's board. API keys are never included in the repo.

Arabic quick start: [hardware/README_AR.md](hardware/README_AR.md).
