# Current execution architecture

The application executes on the real ESP32 with LVGL 8.3.11. The PC supplies the
existing generation, validation, compilation, upload and test workflow.

1. `server.py` receives the request and invokes `pipeline.run`.
2. `gemini_client.py` or `openai_client.py` returns UI C++ plus the JSON test spec.
3. `spec.py` validates the specification and `validator.py` checks code rules.
4. `pipeline.py` writes the same `lvgl_ui/generated_ui.cpp` used by PlatformIO,
   compiles the selected ESP32 environment and explicitly uploads when enabled.
5. `spec_runner.py` executes the saved JSON test actions and expectations using
   the board protocol. UI failures feed the repair loop; setup/serial failures
   are reported separately.
6. In USB mode, `hardware.target` connects a `hardware.device.CaptureDevice`.
   FRAME invalidates and redraws the real LVGL screen. The capture firmware
   streams the same draw-buffer pixels sent to the TFT. The PC validates strip
   bounds, CRC and complete coverage, then saves PNG/raw pixels/TREE/metadata.
7. `framebuffer_judge.py` reviews screenshot batches after functional checks and
   caches identical reviews. `project_state.py` owns source locking/fingerprints.

The `hardware/` feature contains viewer/capture code only. Application code,
generator, validation and test logic remain in their established project paths.
The original camera capture/judge path also remains available; it executes the
same board test protocol with camera photos as its visual evidence.

See `../../hardware/README.md` for transfer limitations and first physical tests.
