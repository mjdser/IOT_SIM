# IOT bench simulator

This is a desktop Electron window around a native LVGL host, not a replacement UI drawn in HTML. Start **`../Start-IOT.cmd`** on this Windows PC. It starts the existing `tools/ui_generator/server.py` chat at **http://127.0.0.1:8765** and the bench together, with **FLASH=0**. Keep its terminal open for compiler/test results. **Open existing UI chat** opens that server in your browser. `npm start` starts only the bench. Python 3 must be on PATH (`IOT_PYTHON` may name its executable). The native host and desktop dependencies are included in this working folder.

## Describe a UI → see it on the glass

Copy the root `.env.example` to `.env` if missing. Put your provider's API key on an **uncommented** line. Never post it in chat or commit `.env`.

For Gemini, set `GENERATOR_PROVIDER=gemini` and `GEMINI_API_KEY=your-key`. For the OpenAI key supplied in this session, the existing `openai_client.py` is selected using `GENERATOR_PROVIDER=openai`, `OPENAI_API_KEY=your-key`, and `OPENAI_MODEL=gpt-4.1`. Use one provider's key with that provider. Keep `FLASH=0` and `TESTS=1`. An inherited environment variable overrides `.env`; restart the server after changing an existing key, provider, or model.

1. Launch `Start-IOT.cmd` and open the existing chat.
2. Ask **“a light switch with a brightness slider”**.
3. The existing generator returns C++ plus a JSON spec. The unchanged `system_prompt.txt`, `validator.py`, and `spec.py` rules apply.
4. `pipeline.py` writes `lvgl_ui/generated_ui.cpp` and `lvgl_ui/ui_spec.json`, builds that exact C++ file for PC LVGL, then runs the spec through `SimulatorDevice` and the unchanged firmware test hooks.
5. Failed static/build/state/layout/image-review checks go back to the selected text generator, up to six attempts per request. If no attempt passes, source, spec and theme are restored. The previous passing preview remains visible.
6. Only a passing executable is published. The running bench detects the accepted manifest and reloads automatically; no restart or manual copying is needed. Click switches/buttons or drag the slider on the glass. The live TREE panel shows the resulting state.

The host path does not look for PlatformIO, a serial port, or a physical camera. With `SIM_VISION_JUDGE=1`, an independent image reviewer evaluates `expect_visual` plus readability/contrast/overlap criteria from the framebuffer PNGs. It uses a separate prompt and no generator code or conversation. Exact state/geometry failures are repaired first; image failures then enter the same repair loop. Every capture saves `shot.png` beside `tree.json` and `geometry.json`.

The existing CLI uses the same path:

```powershell
python tools/ui_generator/generate.py "a light switch with a brightness slider" --sim
```

Run that command from the IOT root. `--sim` is the default when neither `--flash` nor the legacy board `--test` flag is supplied. The desktop launcher forces `FLASH=0`. The server defaults to it as well. Host tests always run even if `TESTS=0` is inherited; that option controls the legacy board path only.

## Same source for partners

When **Ready for real board** appears, the current `generated_ui.cpp`, `generated_ui.h`, `test_hooks.cpp`, `ui_theme.h`, and `lv_conf.h` match the accepted build's recorded hashes. The note disappears if those files change. It means **host-verified source**, not a completed ESP32 cross-compile or hardware test.

Send partners this repository's source files, `lvgl_ui/ui_spec.json`, and `include/` configuration; exclude `.env` and its key. From the IOT root, partners with PlatformIO and their board connected run:

```powershell
pio run -e lvgl_ui_test -t upload
# If needed: add --upload-port COM4 (use the actual port).
```

Do not regenerate or edit `lvgl_ui/generated_ui.cpp` between preview and upload. `platformio.ini` selects that exact file for `lvgl_ui_test`. **The Windows host EXE is not the ESP32 firmware binary**: partners compile the same C++ and configuration for the ESP32 architecture. No board was flashed in this work. Touch injection checks LVGL behaviour, not XPT2046 hardware.

The accepted manifest is `simulator/build/active.json`. It records source and executable SHA-256 values, relative executable paths, selected board theme, and the run directory. Each immutable executable lives inside its attempt folder. `build.json`, C++/spec snapshots, compiler logs, dark/light captures and results remain under `tools/ui_generator/runs/`. `accepted-build.json` preserves the accepted manifest beside the run. Keep these folders if you want the existing live preview to reopen without rebuilding.

## Resume without spending another API call

The current handoff checkpoint is `../work/SESSION_CHECKPOINT.md`. All provider responses are retained as separate C++/JSON attempt files, and the compiler cache is retained. To rebuild/retest a saved attempt from the IOT root without calling an API:

```powershell
python tools/ui_generator/generate.py "Replay saved UI" --sim --code-file tools/ui_generator/runs/RUN/attempt_N/generated_ui.cpp --spec-file tools/ui_generator/runs/RUN/attempt_N/ui_spec.json
```

Replace RUN/attempt_N with a real saved attempt. This intentionally makes that attempt the current source only if it passes. Chat conversation sessions themselves are in server memory; refreshing preserves them, but restarting the server starts a new chat. The accepted source, captures, binaries, and checkpoints survive restarts.

## What matches the hardware

- Same UI code, same 240×320 RGB565, same test commands as the board.
- The current `../lvgl_ui/generated_ui.cpp` is compiled directly for both targets; there is no separate simulator UI implementation. `../lvgl_ui/test_hooks.cpp` remains unchanged. Both use LVGL **8.3.11** and the firmware's `../include/lv_conf.h`. The original 10-row draw buffer flushes into a full 240×320 host framebuffer. Rotation is 0.
- When the real camera is sharp and exposure is locked, a photo matches this glass closely. This is the intended visual comparison, not a measured claim of optical or colour calibration. Panel colour response, lighting and camera optics can differ.
- Focus and glare in the 3D view are an illustration. The label reads **“camera illustration, not a measurement”**. These effects apply to the camera viewport only. Captures and glass texture data stay sharp.
- The active glass is 43.2×57.6 mm, inside a larger red PCB. All other model dimensions and the camera's 14° illustrative framing are estimates from the supplied photos, not measured CAD or calibrated optics.
- The black DevKit, female–female jumper sockets, white table, box base, aluminium tubes, grey clamps and single downward webcam follow the references. Header slot positions and cable paths are schematic. They are not a physical pin-placement guide; consult `../HARDWARE.md` for the authoritative electrical nets.
- The webcam is USB to the PC, never ESP32 wiring. Settings shown are the real pipeline's 1600×1200, exposure −6, 6500 K, burst of 3, keep sharpest. The simulator does not open or emulate a physical camera.

## Controls

Drag to orbit, right-drag to pan, scroll to dolly. Click the viewport, then use WASD to walk in a horizontal plane 23 cm above the tabletop; orbit remains available. Click the active glass to send `TAP x y` through the firmware virtual input device. **Inspect glass** gives a useful close view; **Whole bench** restores the overview.

**Look through the camera** moves the eye to the single modelled webcam lens, looking down at the glass in a 4:3 viewport. **Step back** restores the previous view. Focus starts sharp and glare starts off; controls appear only in the camera seat. Camera framing is illustrative because real mount dimensions, intrinsics and the private crop are unavailable.

Dark is the default in both views and every generated UI is first compiled/tested with `UI_LIGHT_THEME=0`. If a light theme is requested in the chat, the same source is rebuilt with `UI_LIGHT_THEME=1` only after dark checks pass; light checks must pass and captured TREE layouts/states must match the dark build. Otherwise the tested dark version stays active. No colour remapping is used for generated screens.

**Show the light theme** is available only when both compiled palettes passed. Switching creates the other compiled UI and replays your input journal; the switch is accepted only if its TREE exactly matches the current state/layout. That preserves text, switch states and slider values. It does not rewrite the board's `ui_theme.h`; the readiness note names the board's selected theme. For dark-only accepted builds the toggle is disabled; ask the chat for a light theme to build both. The legacy bundled alphabet demonstration alone retains its original host-only palette mapping.

**Save capture** creates `captures/<timestamp>/shot.png`, `tree.json`, `frame.rgb565`, and `geometry.json`. PNG uses bit-replicated RGB565 channels, no blur, resizing or tone mapping. It captures the LVGL buffer, not a photograph of the 3D bench.

## Native host and protocol

`build/lvgl_sim.exe [frame-output-path]` reads newline-terminated stdin and writes the board's `@@` replies to stdout. It supports `PING`, `TREE`, `TAP_ID`, `TAP`, `DRAG`, `WAIT_IDLE`, and `RESET_UI` through the unchanged test hooks. `@@READY` announces startup. Real LVGL timers run continuously. EOF shuts the host down.

Host-only extensions: `FRAME` refreshes the little-endian RGB565 file; `GEOMETRY` reports label clipping; `RANGES` reports slider bounds/min/max; `THEME DARK` / `THEME LIGHT` support the legacy alphabet palette only. Generated palettes are selected by the bridge using separately compiled executables. None of these extensions are added to the ESP32. **No SHOT implementation, automatic flashing or camera access is used.** The existing chat uses the configured generator and a separate PNG image-review call when enabled. Injected input bypasses XPT2046, just like the board's hooks.

`SimulatorDevice` in `../tools/ui_generator/device_runner.py` provides the same client methods over a subprocess. `Device` retains the serial implementation. Capture support was added to the existing `spec_runner.py`; simulator runs pass `camera=None`; PNG review uses `framebuffer_judge.py` and never opens the camera.

```powershell
python run_spec.py demo-spec.json --out captures/demo
python test_host.py
python test_accepted_ui.py
```

For automation, import `SimulatorDevice` and use it as a context manager. Calls must be serialized per process. Each instance has a private framebuffer file. The desktop loopback bridge is bound to 127.0.0.1 with a random per-launch token and serializes requests; renderer code has no Node access. Closing the window closes the bridge and host stdin.

Geometry checks cover visible registered widgets outside the screen, overlap between registered interactive widgets, and all LVGL labels' text extents and ancestor bounds. They are conservative checks, not a general pixel-occlusion solver. Every capture contributes geometry checks and diagnostics include clipped text and bounds. The original alphabet fixture clips a sufficiently long note; that fixture behaviour was preserved. The currently generated switch/slider is a separate accepted UI produced by the existing chat.

## Rebuild

`python build.py` uses the included portable Zig 0.13.0 compiler and pinned LVGL source in `vendor/`. It builds the actual C/C++ firmware files, no generated facsimile. `provenance.json` records the firmware and LVGL commit IDs and source hashes. Alternatively, use a normal C/C++ compiler with `cmake -S . -B build-cmake` and `cmake --build build-cmake --config Release`, then place the executable at `build/lvgl_sim.exe` for the desktop bridge. CMake configuration is provided; this delivered Windows build was tested with Zig.

For a fresh checkout obtain LVGL tag `v8.3.11` in `vendor/lvgl`, Zig Windows x86_64 0.13.0 in `vendor/zig-windows-x86_64-0.13.0`, then run `npm ci` and `python build.py`. Dependencies need network only during installation, not use. The supplied application targets Windows; the host CMake source is portable but other platforms have not been tested.

`test-results/host.json` and `desktop.json` preserve the original alphabet verification. `live-chat.json`, `accepted-host.json`, `pipeline-desktop.json`, and `compiled-theme.json` cover the connected pipeline. `IOT_PIPELINE_SMOKE=1` exercises actual mouse taps/drags against the accepted switch/slider and compares a glass tap's TREE with TAP_ID. `IOT_SMOKE=1` is the older alphabet-specific desktop check. Test captures are screenshots of the actual application.

The OpenAI option uses the repository's existing Chat Completions client. Official references: [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [GPT-4.1](https://developers.openai.com/api/docs/models/gpt-4.1). Model availability still depends on the configured API account.


## Watching tests and recovering failed attempts

The 3D glass now displays RGB565 frames from the actual candidate test process during automatic tests, with the current test and action shown on screen. Each step is held for 0.4 seconds so it is visible; manual input is blocked while tests control the glass. This is a view of real test states, not an animation of guessed interactions. The last accepted interactive process remains available and returns after a failed attempt; only passing builds replace it. A 30-second expiry prevents an interrupted test from leaving a stale candidate on the glass. `IOT_LIVE_TESTS=0` disables publishing/delays for unattended tests.

The existing chat polls progress during generation, validation, compilation, and tests. Failures show their checks or validation/build errors, rather than asking for a simpler request without explaining why. Invalid key IDs explicitly explain the lowercase protocol requirement, including IDs constructed in C++. The generator rules and firmware protocol are unchanged.

Chat history is cached locally in `simulator/build/chat-sessions.json` at the start/end of each generation. Accepted binaries and attempt evidence remain cached separately. After a server interruption, the chat reports the interrupted run and keeps the last accepted UI. API keys remain in `.env` and are not stored in the chat cache. History from a server that ran before this caching change cannot be recovered from memory after restart.

The saved English keyboard attempt from `2026-10-13_165035` was repaired locally: lowercase IDs in code/spec, explicit keyboard/button padding, centered key labels, and a separate Backspace position. Its original test expectations were retained. Run `2026-10-13_165707` passed 240/240 checks, with no API call. This is a repaired saved model output; it does not mean the model repaired those layout defects itself. `test-results/live-desktop.json` verifies actual live test states (including HELLO and HELLO WORLD) in Electron and equality of a mouse glass click and TAP_ID. `live-testing.png` captures the live test view.

Arabic remains unsupported by the current shared font/shaping configuration and ASCII-only generation rules. A language label alone is not Arabic support. The simulator does not use system fonts to bypass firmware restrictions.


## Repairs, layout coverage, and finished colours

Automatic generation now allows up to six attempts per request. Validation, compiler, state and geometry failures are sent back to the configured generator; each repair feedback file is retained beside its attempt. The chat shows the attempt/test stages. If the budget is exhausted, Continue repairing resumes the failed draft with its diagnostics and original requirements; the last accepted interactive build stays available. This button survives chat reloads through the cached session. A failed requested light build also triggers repairs instead of silently accepting dark.

Geometry now checks all visible labels against other labels and interactive controls, excluding ancestor/descendant pairs such as a button's own label. It runs after tap/drag/expect steps as well as captures, so Purple selection is checked even if the generated test omitted a screenshot there. These are conservative bounding-box checks, not a vision judge or a general occlusion/contrast solver.

UI_PRESENTATION_THEME=light is saved for this user's white finished view. Chat requests require a light spec; an explicit request for dark overrides that preference. SIM_TEST_PALETTES=selected now tests only the requested palette. The former dark-first workflow is available explicitly with SIM_TEST_PALETTES=both. Each build's initial top-left background pixel is checked for dark/light luminance; this catches runtime creation code that overrides the compile-time palette. Text, layout and widget state are compared across dark/light builds.

The reported Themes & Preset Colors defect was reproduced by the new overlap check. The first repair run (2026-10-13_172331) exhausted six attempts: compiler errors and layout errors were corrected, but the old toggle test contradicted the newly requested initially checked Light state. The subsequent run 2026-10-13_172945 used tests for Light -> Dark -> Light and all six presets. Its saved draft failed the actual dark background pixel check; the configured OpenAI client repaired it on the next attempt. Both palettes passed 193/193 checks. The screen switch now changes actual background pixels and text contrast, rather than only its label. theme-desktop.json checks actual Electron mouse input against TAP_ID and the dark/white pixels; theme-repair.png shows Purple selected without text overlap. 87 Python unit tests pass.

That earlier repair verification used no image judge or hardware. PNG image review was enabled afterward as described below. Both Gemini and OpenAI remain supported by the existing generator; changing providers does not replace the validation/repair loop.


## Independent framebuffer image judge

`SIM_VISION_JUDGE=1` enables review; `SIM_JUDGE_PROVIDER=openai` and `OPENAI_JUDGE_MODEL=gpt-4.1` use the existing OPENAI_API_KEY. An optional OPENAI_JUDGE_API_KEY can separate the account. Gemini is also supported using SIM_JUDGE_PROVIDER=gemini and its existing key/model settings. Restart the server when changing these settings. Set SIM_VISION_JUDGE=0 for an explicitly offline functional-only run; successful offline checks do not mean image review passed.

The judge receives raw 240x320 lossless PNGs, test actions, intent and criteria. It never receives the C++ source, the generator conversation, camera-seat screenshots, focus or glare. Functional and geometry failures skip the paid review. Otherwise all captures are batched into one request per tested palette (including the initial capture). Missing/malformed verdicts get one format retry and never count as success. API errors preserve the last accepted UI and do not masquerade as UI failures.

Initial background-only criteria are mapped to the compile-time palette being tested. Initial Dark/Light switch criteria explicitly refer to the visible adjacent label and knob, because compile-time palettes must preserve widget states. Subsequent runtime theme changes are checked normally. Near-white/near-black palettes are acceptable unless an exact hex colour is required. This avoids repairing valid UI code merely because the reviewer confused a dark test palette with a logical theme selection.

`visual/inputs.json` and `visual/verdict.json` live beside each attempt's test evidence. Reviews are cached under simulator/build/vision-cache by prompt version, provider/model, criteria/actions and PNG hashes. Identical cached verdicts need no new API request; changing a pixel or criterion invalidates the cache. Cache files contain review answers, not API keys. A heartbeat keeps the actual candidate frame visible while review is pending. The chat says Image judge and shows pass/fail; visual failures are sent to the generator for repair.

Run 2026-10-13_175539 passed 238/238 checks in each palette, with 10 PNGs reviewed per palette and the original generated C++ source unchanged. `test_vision_contrast.py` creates a temporary real LVGL low-contrast fixture, captures its framebuffer and restores the shared source; the live reviewer rejects the faint message and an exact repeat uses cached results without another API call. Results are under test-results/contrast-fixture/verdict.json. Earlier diagnostic review attempts exposed and corrected over-literal palette criteria; those logs remain cached.

The image reviewer adds coverage for visible defects; it is an AI assessment, not proof of every possible interface state. Exact protocol/state/geometry checks remain authoritative for their measured properties. The transport follows the official [OpenAI image input documentation](https://developers.openai.com/api/docs/guides/images-vision?api-mode=chat).


## Current default: requested palette and task-aware placement

SIM_TEST_PALETTES=selected is now the default. White/light is the saved presentation preference, so the host compiles, runs tests and reviews PNGs only in white for a normal request. There is no automatic dark pass. Set SIM_TEST_PALETTES=both explicitly to retain the previous dark-first/light-second comparison. Original system_prompt.txt remains unchanged; a host execution-context instruction scopes its legacy camera testing guidance to the board workflow. Same generated C++ and theme header remain the source for a future board build.

A single-palette accepted manifest contains only that executable. The desktop's palette toggle is disabled when there is no alternate tested build. UI controls that intentionally change colours at runtime are still exercised normally by their tests.

The image judge checks placement and grouping according to the request. Compact single-board games should be balanced and centred as a complete composition, while labels, lists, forms or explicitly positioned layouts are not universally centred. Equal-role grid cells should align and use consistent sizes/gaps. Scrolling is legitimate for requested scrollable content; it should not hide a misplaced compact game that fits the panel.

Native GEOMETRY additionally reports interactive controls clipped by ancestor bounds, catching empty grid cells whose labels do not reveal the clipping. Explicitly requested scrollable content is exempt from this additional control-clipping gate. For tic-tac-toe, exact TREE checks verify nine equal square cells, aligned rows/columns, consistent gaps and horizontal centring within 4 pixels unless another placement is requested. Known row/column IDs or nine square buttons are recognised; unfamiliar layouts are reviewed visually rather than forcing this game-specific rule on everything.

If initial host layout is already wrong, it returns a repair failure before running interactions or paid image review. Repair feedback deduplicates repeated causes and explains that coordinates already include inherited LVGL padding. Generator host context also explains usable content width and explicit padding. Follow-up chat edits synchronise their code context with the actual accepted source after a CLI repair, so the accepted fix is retained.

The user's tic-tac-toe screenshot reproduced a board centre of x=140 instead of x=120 and rightmost cells clipped by their parent. Diagnostic run182740 exhausted its old verbose-feedback attempts. After improving feedback and early exit, run183610 repaired the actual layout on attempt3 and passed549/549 functional/layout/image checks in WHITE ONLY. Nine cells and New Game now fit without scrollbars; original turns, X/O wins, draw and reset tests remain. centred-game.json records centre121 (1px from screen centre), actual mouse click == TAP_ID, and New Game. centred-game.png shows the corrected desktop glass. Use IOT_GAME_SMOKE=1 for this current UI, not earlier keyboard/slider-specific smokes.

### Temporary Gemini free-tier setup
The current local `.env` selects Gemini 3.8 Flash for both generation and framebuffer image review. Add a Gemini key from https://aistudio.google.com/apikey to `GEMINI_API_KEY` in the root `.env`, then restart `Start-IOT.cmd`. The OpenAI key is preserved but is not selected. Use a Google project on the Free tier; choosing a model does not change the project's billing tier. Free-tier quotas still apply. No live Gemini request has been verified until a key is supplied.

Local functional and geometry checks cost no API credits. Generation, repair and batched PNG review use API quota. Caches, early local failure gates and selected-palette testing remain enabled.
