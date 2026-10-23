# UI generator and test workflow

This directory contains the application workflow: AI clients, code/spec
validation, compile/upload, functional tests, visual review and repair.
The real-device viewer is separate in [hardware/](../../hardware/README.md).

Default interactive entry point: `Start-IOT.cmd` or `Start-Hardware.cmd`.
Configure `.env` in the project root. No API keys belong in source control.

## CLI

USB screenshot workflow on a connected capture board:

`python tools/ui_generator/generate.py "your interface" --hardware`

`--sim` is retained as an alias for this same hardware mode. It does not run a
PC UI. First install capture firmware explicitly through the viewer.

Compile ESP32 firmware without uploading:

`python tools/ui_generator/generate.py "your interface"`

The original project hardware/camera commands also remain available:

- `--flash`: compile and upload without automatic tests.
- `--test`: compile/upload and test using the serial protocol and optional camera.
- `--port COM4`: select the upload/serial port.
- `--code-file reply.txt`: use a saved reply; add `--spec-file ui_spec.json`
  when pairing a bare C++ source with its saved tests. No code-generation call.

Configure `CAMERA_INDEX` only for the camera workflow. Without it, that workflow
runs functional state checks without camera photos. USB mode never opens it.
Use `camera_check.py` or `camera_preview.py` for the existing camera setup tools.

Offline tests:
`python -m unittest discover -s tools/ui_generator -p "test_*.py"`.

Run evidence remains in `tools/ui_generator/runs/`. Chat cache, source lock and
PNG-review cache live in the ignored project-root `runtime/` directory.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the current execution path.
