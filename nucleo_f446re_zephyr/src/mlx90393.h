#ifndef MLX90393_H_
#define MLX90393_H_

#include <zephyr.h>
#include <device.h>
#include <drivers/i2c.h>
#include <errno.h>

#define MLX90393_DEFAULT_ADDR   0x0C

/* On-chip noise filtering written to register 0x02 at init.
 * OSR = ADC oversampling (0-3), DIG_FILT = digital filter depth (0-7).
 * Higher values average more samples: less noise, longer conversion.
 * OSR=3, DIG_FILT=5 gives ~53 ms per XYZ measurement. */
#define MLX90393_OSR            3
#define MLX90393_DIG_FILT       5

/* Measurement data container */
typedef struct {
    int16_t x;
    int16_t y;
    int16_t z;
} mlx90393_data_t;

/* Measurement converted to gauss */
typedef struct {
    float x;
    float y;
    float z;
} mlx90393_gauss_t;

/* Sensor instance descriptor */
typedef struct {
    const struct device *i2c_dev;
    uint8_t i2c_addr;
    const char *label;

    /* Filled in by mlx90393_init() from the sensor's registers */
    uint8_t gain_sel;   /* GAIN_SEL[2:0], register 0x00 */
    uint8_t hallconf;   /* HALLCONF[3:0], register 0x00 */
    uint8_t res_x;      /* RES_X[1:0],    register 0x02 */
    uint8_t res_y;      /* RES_Y[1:0],    register 0x02 */
    uint8_t res_z;      /* RES_Z[1:0],    register 0x02 */
    uint8_t osr;        /* OSR[1:0],      register 0x02 */
    uint8_t dig_filt;   /* DIG_FILT[2:0], register 0x02 */
    uint16_t conv_ms;   /* Wait time for one XYZ measurement */
} mlx90393_t;

/**
 * @brief Initialize the MLX90393 sensor and read its gain/resolution config.
 * @param dev Pointer to sensor descriptor structure.
 * @return 0 on success, negative errno on failure.
 */
int mlx90393_init(mlx90393_t *dev);

/**
 * @brief Read X, Y, and Z raw 16-bit counts from the sensor.
 * @param dev Pointer to sensor descriptor structure.
 * @param data Pointer to output struct where axes will be stored.
 * @return 0 on success, negative errno on failure.
 */
int mlx90393_read_axes(const mlx90393_t *dev, mlx90393_data_t *data);

/**
 * @brief Convert raw counts to gauss using the sensor's gain/resolution.
 * @param dev Pointer to an initialized sensor descriptor.
 * @param raw Raw counts from mlx90393_read_axes().
 * @param out Pointer to output struct in gauss.
 */
void mlx90393_to_gauss(const mlx90393_t *dev, const mlx90393_data_t *raw,
                       mlx90393_gauss_t *out);

/**
 * @brief Take a measurement and return it in gauss (no offset correction).
 * @param dev Pointer to an initialized sensor descriptor.
 * @param out Pointer to output struct in gauss.
 * @return 0 on success, negative errno on failure.
 */
int mlx90393_read_gauss(const mlx90393_t *dev, mlx90393_gauss_t *out);

#endif /* MLX90393_H_ */
