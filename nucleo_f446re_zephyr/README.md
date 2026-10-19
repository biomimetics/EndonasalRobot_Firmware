# MLX90393 dual magnetometer firmware (Nucleo-F446RE, Zephyr)

This PlatformIO project builds the Zephyr application in `src` for the
NUCLEO-F446RE and uploads it through the board's onboard ST-Link debugger.

## Build and upload

1. Open this `mlx90393_magnetometer` folder in VS Code with the PlatformIO IDE
   extension installed.
2. Connect the board to the PC through its ST-Link USB connector.
3. Build with **PlatformIO: Build** or run `pio run` in the project folder.
4. Upload with **PlatformIO: Upload** or run `pio run -t upload`.
5. Open the serial monitor at 230400 baud with **PlatformIO: Monitor** or run
   `pio device monitor -b 230400`.

The first build may take longer while PlatformIO installs the STM32 platform
and Zephyr packages. The application sources are selected in
`zephyr/CMakeLists.txt`; add additional C source files under `src` to include
them in the build.

## Using the magnetometers from Python

The firmware uses the same serial interface as `ZephyrEndoCode`
(`python/control-record.py`), at 230400 baud on the ST-Link virtual COM port.

1. Install the Python packages: `pip install pyserial numpy`.
2. Upload the firmware, then run `python python/mag-record.py [PORT]`
   (e.g. `COM3` or `/dev/ttyACM0`; with no port the ST-Link is found
   automatically).
3. Press RESET on the Nucleo (or hold RESET while starting the script, then
   release it). The script waits for `# STM32READY`, then sends `PRNWAIT`.
4. Stop with ctrl-C. Everything received is saved to
   `Data/mag-<date>-<time>.txt`. Lines starting with `#` are comments from the
   STM32 and the other lines are state data.

State line (sent every `PRNWAIT` ms; time in s since boot, field in gauss
with calibration offsets removed, `nan` if a sensor failed to read):

    time, mag1_x, mag1_y, mag1_z, mag2_x, mag2_y, mag2_z

In Python, `StateStruct` gives `state.time`, `state.mag1`, `state.mag2`
(numpy x/y/z arrays) and `state.diff` (MAG2 - MAG1).

Commands, sent with `makeCmd(command, value)`. Several commands can go on one line
using `makeCmdString`:

| Command        | Effect                                                        |
| -------------- | ------------------------------------------------------------- |
| `PRNWAIT ms`   | Time between state lines (default 1000 ms)                    |
| `CALIB`        | Run the six-position hard-iron calibration (see `calibration.h`) |

Both sensors are read one after the other (~60 ms each), so a new state is
available about every 120 ms. A `PRNWAIT` below that repeats no data; it
just prints as fast as the sensors are read. While a calibration runs (~55 s), only `#` lines are
sent. The blue USER button still starts a calibration too.
