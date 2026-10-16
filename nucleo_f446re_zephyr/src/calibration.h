#ifndef CALIBRATION_H_
#define CALIBRATION_H_

#include <stddef.h>
#include "mlx90393.h"

/*
 * Guided six-position hard-iron calibration for MLX90393 magnetometers.
 *
 * What it corrects
 * ----------------
 * Every reading is the sum of two parts:
 *
 *     reading = hard-iron bias + external field
 *
 *   - Hard-iron bias: a constant offset from magnetized material that is fixed
 *     relative to the sensor (steel breadboard clips, nickel-plated header pins,
 *     screws on the same mount) plus the sensor chip's own zero-field offset.
 *     It rotates WITH the sensor, so it reads the same in every orientation.
 *   - External field: Earth's field (~0.25-0.65 G) and any magnets. It stays
 *     fixed in the room, so its X/Y/Z components change as the sensor rotates.
 *
 * Axes
 * ----
 * X and Y are the arrows printed on the sensor breakout boards; +Z points out
 * of the face with the chip. Both sensors are mounted the same way, so the
 * whole board (Nucleo + breadboard + sensors) is rotated as one piece.
 *
 * How it is done
 * --------------
 * The user is prompted through six positions. Each position has a
 * CALIB_MOVE_MS countdown to get into place, then the board is held still for
 * CALIB_HOLD_MS while every reading is averaged (averaging removes noise):
 *
 *     1. Flat, chip side UP              -> +Z points up
 *     2. Flipped over about the X axis   -> +Z points down
 *     3. On its edge, X arrow UP         -> +X points up
 *     4. On its edge, X arrow DOWN       -> +X points down
 *     5. On its edge, Y arrow UP         -> +Y points up
 *     6. On its edge, Y arrow DOWN       -> +Y points down
 *
 * How the offset is calculated
 * ----------------------------
 * For each axis, compare the two positions where that axis points up and
 * down. Earth's vertical field V is the same in both, but reverses sign
 * relative to the sensor, while the bias does not change:
 *
 *     axis up:    mean_up   = bias - V
 *     axis down:  mean_down = bias + V
 *
 *     offset = (mean_up + mean_down) / 2     (V cancels out)
 *     span   = |mean_down - mean_up| = 2V    (quality check)
 *
 * The positions do not need to be perfect: any tilt is the same in both
 * halves of a pair, so it still cancels as long as the second position is
 * the first one turned over. The span should be ~0.5-0.9 G (2 x Earth's
 * vertical field). A span below CALIB_MIN_SPAN_G means that pair was not
 * turned over properly and a warning is printed.
 *
 * The offsets are then subtracted from every later reading
 * (calibration_apply). After a good calibration, with no magnets near,
 * |B| should read ~0.3-0.6 G in any orientation and both sensors should agree
 * to within a few hundredths of a gauss.
 *
 * Limitations
 * -----------
 *   - Soft-iron effects are NOT corrected: nearby unmagnetized steel also bends
 *     and scales external fields (direction-dependent error). That needs an
 *     ellipsoid fit, not just an offset.
 *   - Offsets are only valid while nothing magnetic moves relative to the
 *     sensors. A strong magnet brought close can re-magnetize nearby steel and
 *     shift the bias - recalibrate if that happens.
 *   - Offsets live in RAM only and are lost on reset/power-off.
 */

/* Time given to move the board into each position */
#define CALIB_MOVE_MS 4000

/* Time the board is held still while readings are averaged */
#define CALIB_HOLD_MS 5000

/* Minimum expected up/down difference per axis, in gauss */
#define CALIB_MIN_SPAN_G 0.4f

/**
 * @brief Run the guided six-position calibration on all sensors.
 *
 * Blocks for about 6 x (CALIB_MOVE_MS + CALIB_HOLD_MS) while printing
 * instructions, then writes the new offsets and prints the results. If a
 * sensor misses readings in any position its previous offset is kept.
 *
 * @param sensors     Array of initialized sensors.
 * @param offsets     Array of offsets (same length), updated on success.
 * @param num_sensors Number of sensors.
 */
void calibration_run(mlx90393_t *const sensors[], mlx90393_gauss_t offsets[],
                     size_t num_sensors);

/**
 * @brief Subtract a sensor's hard-iron offset from a reading in place.
 * @param offset Offset from calibration_run() (all zero if not calibrated).
 * @param b      Reading in gauss, corrected in place.
 */
void calibration_apply(const mlx90393_gauss_t *offset, mlx90393_gauss_t *b);

#endif /* CALIBRATION_H_ */
