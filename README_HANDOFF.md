# Current hardware handoff

Start with [hardware/README.md](hardware/README.md) or the
[Arabic quick start](hardware/README_AR.md).

Run `Start-IOT.cmd` or `Start-Hardware.cmd`. `Start-Simulator.cmd` opens the same
current hardware viewer for compatibility with existing instructions.

The application firmware and AI workflow live in `lvgl_ui/` and
`tools/ui_generator/`. The complete viewer/capture adapter lives in `hardware/`.
The ESP32 executes the interface; screenshots and test results return over USB.

The previous PC simulator and PC-to-board mirror have been removed. Installation
still requires explicit confirmation before replacing the board firmware. No
physical board was flashed during development here; complete the physical
acceptance steps documented in the hardware guide.
