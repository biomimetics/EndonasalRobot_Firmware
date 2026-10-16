# Nucleo-F446RE Zephyr firmware

This PlatformIO project builds the Zephyr application in `src` for the
NUCLEO-F446RE and uploads it through the board's onboard ST-Link debugger.

## Build and upload

1. Open this `nucleo_f446re_zephyr` folder in VS Code with the PlatformIO IDE
   extension installed.
2. Connect the board to the PC through its ST-Link USB connector.
3. Build with **PlatformIO: Build** or run `pio run` in the project folder.
4. Upload with **PlatformIO: Upload** or run `pio run -t upload`.
5. Open the serial monitor at 115200 baud with **PlatformIO: Monitor** or run
   `pio device monitor -b 115200`.

The first build may take longer while PlatformIO installs the STM32 platform
and Zephyr packages. The application sources are selected in
`zephyr/CMakeLists.txt`; add additional C source files under `src` to include
them in the build.
