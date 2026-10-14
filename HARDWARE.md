# Hardware facts / حقائق العتاد

Source: the user's supplied hardware brief and all four attached photos, read before simulator code was written. Firmware source of truth: https://github.com/aseelFraira/IOT_-AGENTIC_UI at `289abb62b1030e40195e213dfd1479dacc0e746e`, especially `include/User_Setup.h`, `lvgl_ui/main.cpp`, `include/touch_calibration.h`, `tools/ui_generator/camera.py`, and `platformio.ini`.

## Boards and stand

ESP32 DevKit V1, CP2102, PlatformIO board `esp32doit-devkit-v1`. Red 2.8-inch ILI9341 TFT module, SparkFun/PJRC style, XPT2046 touch on the shared SPI bus. Module product title says 320×240; firmware orientation is portrait. Both boards have male headers. Use female–female Dupont wires; other types in the catalogue image are not used on this bench.

One USB webcam connected to the PC through OpenCV, not wired to the ESP32. Grey printed clamp on a horizontal aluminium tube; a cross clamp joins a vertical tube anchored in a cardboard box. Black camera cable goes down toward the PC. White table. Photos contain other background equipment, which is not part of the simulator rig.

## Electrical nets — no inferred GPIOs

- GPIO 19 → TFT_MISO
- GPIO 23 → TFT_MOSI
- GPIO 18 → TFT_SCLK
- GPIO 5 → TFT_CS
- GPIO 15 → TFT_DC
- GPIO 4 → TFT_RST
- GPIO 21 → TOUCH_CS
- VCC → DevKit 3V3 (3.3 V)
- GND → GND
- LED → 3.3 V, always on. `TFT_BL` is not defined; no backlight GPIO.

Display and touch share MOSI/MISO/SCK; chip-select differs. Do not apply 5 V to SPI pins. Physical header order in the model is schematic, not an asserted pinout. Use the wiring sheet and board markings for assembly.

TFT_eSPI requirement ^2.5.43; LVGL ~8.3.11; Arduino-ESP32. Display SPI 27 MHz, touch SPI 2.5 MHz. Touch calibration at rotation 0 is `{418,3255,338,3334,2}`: x0, x-span, y0, y-span, flags, invert-X set.

## Pixels

`tft.setRotation(0)`, `SCREEN_W=240`, `SCREEN_H=320`. RGB565, LVGL depth 16, no 16-bit byte swap. Active glass about 43.2×57.6 mm (0.18 mm pitch) within a larger PCB. Firmware draw buffer is `240*10`; the host retains that draw buffer and copies flushes into a full framebuffer.

The real test pipeline always uses dark colours with background `#101418`; `pipeline.py switch_to_light` and `UI_LIGHT_THEME` choose light colours only after checks when requested. The current alphabet demo hard-codes its dark palette. Host light mapping is documented in `simulator/README.md` and changes no UI layout.

## Camera

Resolution 1600×1200, aspect 4:3. Exposure −6 manual (DirectShow), white balance 6500 K manual. Burst of 3, keep maximum Laplacian variance. Warmup 2 seconds, discard 4 stale frames. Judge upload longest side 1024, JPEG quality 88. Private `.env` values `CAMERA_CROP=x,y,w,h` and `CAMERA_ROTATE` are not available here; camera mount must stay fixed. Focus hunting is known. Simulated focus/glare are illustration, not measurement.

## Protocol and limits

Board serial 115200, replies start `@@`: PING, TREE, TAP_ID, TAP, DRAG, WAIT_IDLE, RESET_UI. Injected touch does not test XPT2046; physical touch has separate Unity tests. The host uses these exact hooks over stdin/stdout. No board SHOT, flash or Gemini calls are part of the simulator.

## References

- `reference/photos/bench-wiring.png` — supplied wiring sheet and board image
- `reference/photos/camera-stand.png` — supplied table and stand image
- `reference/photos/camera-closeup.png` — supplied camera/clamp image
- `reference/photos/dupont-cables.png` — supplied connector catalogue
- `reference/photos/features.pdf`, `Agentic_UI_Roadmap.pdf` — copied from the user's Downloads/Uni/IOT as requested; background documents, not overrides to this brief

The photos were supplied as PNG, so they retain PNG filenames rather than being renamed to JPEG. All model dimensions except active glass are visual estimates. Camera field of view is illustrative, not a recovered optical calibration.
