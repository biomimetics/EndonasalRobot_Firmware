#include "mlx90393.h"
#include <sys/printk.h>

/* MLX90393 Command Set */
#define CMD_EXIT_MODE           0x80
#define CMD_RESET               0xF0
#define CMD_START_BURST         0x10
#define CMD_WAKE_UP_ON_CHANGE   0x20
#define CMD_START_MEASUREMENT   0x30
#define CMD_READ_MEASUREMENT    0x40
#define CMD_READ_REGISTER       0x50
#define CMD_WRITE_REGISTER      0x60
#define CMD_NOP                 0x00

/* Axis Selection Masks */
#define AXIS_X_FLAG             (1 << 1)
#define AXIS_Y_FLAG             (1 << 2)
#define AXIS_Z_FLAG             (1 << 3)
#define AXIS_XYZ_FLAGS          (AXIS_X_FLAG | AXIS_Y_FLAG | AXIS_Z_FLAG)

static int mlx90393_send_command(const mlx90393_t *dev, uint8_t cmd, uint8_t *status)
{
    int ret = i2c_write(dev->i2c_dev, &cmd, 1, dev->i2c_addr);
    if (ret != 0) {
        return ret;
    }

    if (status != NULL) {
        ret = i2c_read(dev->i2c_dev, status, 1, dev->i2c_addr);
    }
    return ret;
}

int mlx90393_init(const mlx90393_t *dev)
{
    if (!device_is_ready(dev->i2c_dev)) {
        printk("[%s] I2C bus driver not ready\n", dev->label);
        return -ENODEV;
    }

    uint8_t status = 0;

    /* Issue software reset */
    if (mlx90393_send_command(dev, CMD_RESET, &status) != 0) {
        return -EIO;
    }
    k_msleep(20);

    /* Force exit to standby */
    mlx90393_send_command(dev, CMD_EXIT_MODE, &status);
    k_msleep(5);

    return 0;
}

int mlx90393_read_axes(const mlx90393_t *dev, mlx90393_data_t *data)
{
    if (data == NULL) {
        return -EINVAL;
    }

    uint8_t buffer[7]; // 1 byte status + 6 bytes data (2 bytes per axis)

    /* Trigger single measurement on X, Y, and Z */
    uint8_t start_cmd = CMD_START_MEASUREMENT | AXIS_XYZ_FLAGS;
    if (i2c_write(dev->i2c_dev, &start_cmd, 1, dev->i2c_addr) != 0) {
        return -EIO;
    }

    /* Wait for conversion cycle */
    k_msleep(30);

    /* Read back measurement registers */
    uint8_t read_cmd = CMD_READ_MEASUREMENT | AXIS_XYZ_FLAGS;
    int ret = i2c_write_read(dev->i2c_dev, dev->i2c_addr, &read_cmd, 1, buffer, sizeof(buffer));
    if (ret != 0) {
        return ret;
    }

    /* Big-endian 16-bit signed conversion */
    data->x = (int16_t)((buffer[1] << 8) | buffer[2]);
    data->y = (int16_t)((buffer[3] << 8) | buffer[4]);
    data->z = (int16_t)((buffer[5] << 8) | buffer[6]);

    return 0;
}