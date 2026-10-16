#include <zephyr.h>
#include <device.h>
#include <devicetree.h>
#include <drivers/gpio.h>
#include <sys/printk.h>
#include "mlx90393.h"
#include "calibration.h"

/* Time between readings */
#define READ_INTERVAL_MS 1000

/* Blue USER button (B1) on the Nucleo starts a calibration */
static const struct gpio_dt_spec button = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);

/* Define both sensor instances pointing to their respective I2C controllers */
static mlx90393_t mag1 = {
    .i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c1)),
    .i2c_addr = MLX90393_DEFAULT_ADDR,
    .label = "MAG1"
};

static mlx90393_t mag2 = {
    .i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c2)),
    .i2c_addr = MLX90393_DEFAULT_ADDR,
    .label = "MAG2"
};

/* Array of pointers for clean iteration */
static mlx90393_t *sensors[] = { &mag1, &mag2 };
#define NUM_SENSORS (sizeof(sensors) / sizeof(sensors[0]))

/* Hard-iron offsets subtracted from every reading (zero until calibrated).
 * See calibration.h for how they are measured. */
static mlx90393_gauss_t offsets[NUM_SENSORS];

static float magnitude(const mlx90393_gauss_t *b)
{
    /* Minimal libc has no sqrtf(), so use the Cortex-M4 FPU instruction directly */
    float sum = b->x * b->x + b->y * b->y + b->z * b->z;
    float result;
    __asm__("vsqrt.f32 %0, %1" : "=t"(result) : "t"(sum));
    return result;
}

static bool button_pressed(void)
{
    return device_is_ready(button.port) && gpio_pin_get_dt(&button) > 0;
}

void main(void)
{
    printk("\n=== Initializing Multi-Magnetometer Subsystem ===\n");

    if (device_is_ready(button.port)) {
        gpio_pin_configure_dt(&button, GPIO_INPUT);
    } else {
        printk("USER button not available, calibration disabled\n");
    }

    /* Initialize all configured sensors */
    for (size_t i = 0; i < NUM_SENSORS; i++) {
        while (mlx90393_init(sensors[i]) != 0) {
            printk("[%s] Init failed! Retrying in 2s (check wiring)...\n", sensors[i]->label);
            k_msleep(2000);
        }
        printk("[%s] Successfully initialized.\n", sensors[i]->label);
    }

    printk("=== All Magnetometers Online. Streaming Data (gauss) ===\n");
    printk("Press the blue USER button to run hard-iron calibration.\n");

    mlx90393_gauss_t gauss[NUM_SENSORS];
    bool ok[NUM_SENSORS];

    while (1) {
        for (size_t i = 0; i < NUM_SENSORS; i++) {
            ok[i] = (mlx90393_read_gauss(sensors[i], &gauss[i]) == 0);
            if (ok[i]) {
                calibration_apply(&offsets[i], &gauss[i]);
                printk("[%s] X: %8.4f G | Y: %8.4f G | Z: %8.4f G | |B|: %8.4f G\n",
                       sensors[i]->label, gauss[i].x, gauss[i].y, gauss[i].z,
                       magnitude(&gauss[i]));
            } else {
                printk("[%s] Read Error!\n", sensors[i]->label);
            }
        }

        /* Field difference between the two sensors (MAG2 - MAG1) */
        if (ok[0] && ok[1]) {
            mlx90393_gauss_t diff = {
                .x = gauss[1].x - gauss[0].x,
                .y = gauss[1].y - gauss[0].y,
                .z = gauss[1].z - gauss[0].z,
            };
            printk("[DIFF] X: %8.4f G | Y: %8.4f G | Z: %8.4f G | |dB|: %8.4f G\n",
                   diff.x, diff.y, diff.z, magnitude(&diff));
        }
        printk("--------------------------------------------------\n");

        /* Wait for the next reading, checking the button so a press is not missed */
        for (int t = 0; t < READ_INTERVAL_MS; t += 50) {
            if (button_pressed()) {
                while (button_pressed()) {
                    k_msleep(20);
                }
                calibration_run(sensors, offsets, NUM_SENSORS);
                printk("Press USER button to recalibrate.\n\n");
                break;
            }
            k_msleep(50);
        }
    }
}
