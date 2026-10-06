#ifndef MLX90393_H_
#define MLX90393_H_

#include <zephyr.h>
#include <device.h>
#include <drivers/i2c.h>
#include <errno.h>

#define MLX90393_DEFAULT_ADDR   0x0C

/* Measurement data container */
typedef struct {
    int16_t x;
    int16_t y;
    int16_t z;
} mlx90393_data_t;

/* Sensor instance descriptor */
typedef struct {
    const struct device *i2c_dev;
    uint8_t i2c_addr;
    const char *label;
} mlx90393_t;

/**
 * @brief Initialize the MLX90393 sensor.
 * @param dev Pointer to sensor descriptor structure.
 * @return 0 on success, negative errno on failure.
 */
int mlx90393_init(const mlx90393_t *dev);

/**
 * @brief Read X, Y, and Z raw 16-bit counts from the sensor.
 * @param dev Pointer to sensor descriptor structure.
 * @param data Pointer to output struct where axes will be stored.
 * @return 0 on success, negative errno on failure.
 */
int mlx90393_read_axes(const mlx90393_t *dev, mlx90393_data_t *data);

#endif /* MLX90393_H_ */