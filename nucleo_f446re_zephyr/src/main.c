#include <zephyr.h>
#include <sys/printk.h>
#include "mlx90393.h"

/* Define both sensor instances pointing to their respective I2C controllers */
static const mlx90393_t mag1 = {
    .i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c1)),
    .i2c_addr = MLX90393_DEFAULT_ADDR,
    .label = "MAG1 (I2C1 - Distal)"
};

static const mlx90393_t mag2 = {
    .i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c2)),
    .i2c_addr = MLX90393_DEFAULT_ADDR,
    .label = "MAG2 (I2C2 - Proximal)"
};

/* Array of pointers for clean iteration */
static const mlx90393_t *sensors[] = { &mag1, &mag2 };
#define NUM_SENSORS (sizeof(sensors) / sizeof(sensors[0]))

void main(void)
{
    printk("\n=== Initializing Multi-Magnetometer Subsystem ===\n");

    /* Initialize all configured sensors */
    for (size_t i = 0; i < NUM_SENSORS; i++) {
        while (mlx90393_init(sensors[i]) != 0) {
            printk("[%s] Init failed! Retrying in 2s (check wiring)...\n", sensors[i]->label);
            k_msleep(2000);
        }
        printk("[%s] Successfully initialized.\n", sensors[i]->label);
    }

    printk("=== All Magnetometers Online. Streaming Data ===\n");

    mlx90393_data_t reading;

    while (1) {
        for (size_t i = 0; i < NUM_SENSORS; i++) {
            if (mlx90393_read_axes(sensors[i], &reading) == 0) {
                printk("[%s] X: %6d | Y: %6d | Z: %6d\n",
                       sensors[i]->label, reading.x, reading.y, reading.z);
            } else {
                printk("[%s] Read Error!\n", sensors[i]->label);
            }
        }
        printk("--------------------------------------------------\n");
        k_msleep(250);
    }
}