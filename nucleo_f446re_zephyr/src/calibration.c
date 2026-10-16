#include "calibration.h"
#include <sys/printk.h>

/* Maximum sensors supported in one calibration run */
#define CALIB_MAX_SENSORS 4

/* The six positions, in the order the user is asked for them */
enum {
    POS_Z_UP, POS_Z_DOWN,
    POS_X_UP, POS_X_DOWN,
    POS_Y_UP, POS_Y_DOWN,
    NUM_POSITIONS
};

static const char *const instructions[NUM_POSITIONS] = {
    [POS_Z_UP] =
        "Lay the board FLAT on the table, sensor chips facing UP.",
    [POS_Z_DOWN] =
        "FLIP the board over about its X axis (rotate 180 deg around the X arrow),\n"
        "    so it is upside down with the sensor chips facing DOWN.",
    [POS_X_UP] =
        "Turn it right side up, then stand it on its edge so the X arrow points\n"
        "    straight UP (board vertical).",
    [POS_X_DOWN] =
        "Turn it over so the X arrow points straight DOWN (board still vertical).",
    [POS_Y_UP] =
        "Stand it on another edge so the Y arrow points straight UP (board vertical).",
    [POS_Y_DOWN] =
        "Turn it over so the Y arrow points straight DOWN (board still vertical).",
};

/* Countdown in whole seconds, printed once per second */
static void countdown(const char *what, int32_t ms)
{
    for (int32_t s = ms / 1000; s > 0; s--) {
        printk("    %s %d...\n", what, s);
        k_msleep(1000);
    }
}

/* Average all readings over CALIB_HOLD_MS. Returns false if a sensor gave none. */
static bool collect_position(mlx90393_t *const sensors[], size_t num_sensors,
                             mlx90393_gauss_t mean[])
{
    mlx90393_gauss_t sum[CALIB_MAX_SENSORS] = { 0 };
    uint32_t count[CALIB_MAX_SENSORS] = { 0 };
    mlx90393_gauss_t b;
    bool all_ok = true;

    int64_t start = k_uptime_get();
    int64_t next_dot = start + 1000;

    while (k_uptime_get() - start < CALIB_HOLD_MS) {
        for (size_t i = 0; i < num_sensors; i++) {
            if (mlx90393_read_gauss(sensors[i], &b) == 0) {
                sum[i].x += b.x;
                sum[i].y += b.y;
                sum[i].z += b.z;
                count[i]++;
            }
        }
        if (k_uptime_get() >= next_dot) {
            printk("    holding... %lld s left\n",
                   (CALIB_HOLD_MS - (k_uptime_get() - start) + 999) / 1000);
            next_dot += 1000;
        }
    }

    for (size_t i = 0; i < num_sensors; i++) {
        if (count[i] == 0) {
            printk("    [%s] no valid readings in this position\n", sensors[i]->label);
            all_ok = false;
            continue;
        }
        mean[i].x = sum[i].x / count[i];
        mean[i].y = sum[i].y / count[i];
        mean[i].z = sum[i].z / count[i];
        printk("    [%s] avg of %u: X %7.4f  Y %7.4f  Z %7.4f G\n", sensors[i]->label,
               count[i], mean[i].x, mean[i].y, mean[i].z);
    }
    return all_ok;
}

static float abs_f(float v)
{
    return v < 0.0f ? -v : v;
}

void calibration_run(mlx90393_t *const sensors[], mlx90393_gauss_t offsets[],
                     size_t num_sensors)
{
    /* mean[position][sensor]; static to keep it off the small main stack */
    static mlx90393_gauss_t mean[NUM_POSITIONS][CALIB_MAX_SENSORS];
    bool valid = true;

    if (num_sensors > CALIB_MAX_SENSORS) {
        printk("Calibration supports at most %d sensors\n", CALIB_MAX_SENSORS);
        return;
    }

    printk("\n================ CALIBRATION ================\n");
    printk("Move magnets at least 30 cm away. Rotate the WHOLE board (Nucleo,\n");
    printk("breadboard and sensors together). X and Y are the arrows printed on\n");
    printk("the sensor boards. Each position: %d s to move, then hold STILL %d s.\n",
           CALIB_MOVE_MS / 1000, CALIB_HOLD_MS / 1000);

    /* Steps 1-6: guide the user through each position and average the readings */
    for (int p = 0; p < NUM_POSITIONS; p++) {
        printk("\n--- Step %d of %d ---\n", p + 1, NUM_POSITIONS);
        printk("    %s\n", instructions[p]);
        countdown("move into position:", CALIB_MOVE_MS);
        printk("    HOLD STILL now\n");
        if (!collect_position(sensors, num_sensors, mean[p])) {
            valid = false;
        }
    }

    printk("\n============ CALIBRATION RESULT ============\n");
    if (!valid) {
        printk("Some readings failed - keeping previous offsets. Try again.\n\n");
        return;
    }

    for (size_t i = 0; i < num_sensors; i++) {
        /* Offset = midpoint of each up/down pair (Earth's field cancels) */
        offsets[i].x = (mean[POS_X_UP][i].x + mean[POS_X_DOWN][i].x) / 2.0f;
        offsets[i].y = (mean[POS_Y_UP][i].y + mean[POS_Y_DOWN][i].y) / 2.0f;
        offsets[i].z = (mean[POS_Z_UP][i].z + mean[POS_Z_DOWN][i].z) / 2.0f;

        /* Span = 2 x Earth's vertical field; small means the pair was not turned over */
        float span_x = abs_f(mean[POS_X_DOWN][i].x - mean[POS_X_UP][i].x);
        float span_y = abs_f(mean[POS_Y_DOWN][i].y - mean[POS_Y_UP][i].y);
        float span_z = abs_f(mean[POS_Z_DOWN][i].z - mean[POS_Z_UP][i].z);

        printk("[%s] Offset X: %7.4f G | Y: %7.4f G | Z: %7.4f G\n",
               sensors[i]->label, offsets[i].x, offsets[i].y, offsets[i].z);
        printk("[%s] Span   X: %7.4f G | Y: %7.4f G | Z: %7.4f G\n",
               sensors[i]->label, span_x, span_y, span_z);
        if (span_x < CALIB_MIN_SPAN_G) {
            printk("[%s] Warning: X span small - check steps 3/4 (X arrow up, then down)\n",
                   sensors[i]->label);
        }
        if (span_y < CALIB_MIN_SPAN_G) {
            printk("[%s] Warning: Y span small - check steps 5/6 (Y arrow up, then down)\n",
                   sensors[i]->label);
        }
        if (span_z < CALIB_MIN_SPAN_G) {
            printk("[%s] Warning: Z span small - check steps 1/2 (flat, then flipped)\n",
                   sensors[i]->label);
        }
    }
    printk("Offsets applied. Lay the board flat again.\n\n");
}

/* Remove the offset from each reading */
void calibration_apply(const mlx90393_gauss_t *offset, mlx90393_gauss_t *b)
{
    b->x -= offset->x;
    b->y -= offset->y;
    b->z -= offset->z;
}
