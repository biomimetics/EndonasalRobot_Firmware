cmake_minimum_required(VERSION 3.13.1)
set(DTC_OVERLAY_FILE ${CMAKE_CURRENT_LIST_DIR}/app.overlay)
include($ENV{ZEPHYR_BASE}/cmake/app/boilerplate.cmake NO_POLICY_SCOPE)
project(mlx90393_magnetometer)

FILE(GLOB app_sources ../src/*.c*)
target_sources(app PRIVATE ${app_sources})
