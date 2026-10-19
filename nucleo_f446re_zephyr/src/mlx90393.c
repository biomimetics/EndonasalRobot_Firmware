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

/* Status byte flags */
#define STATUS_ERROR            (1 << 4)

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

/* Sensitivity in uT/LSB at RES=0, HALLCONF=0xC, indexed by GAIN_SEL
 * (MLX90393 datasheet, Table 17). Each RES step doubles the value. */
static const float sens_xy_ut[8] = { 0.751f, 0.601f, 0.451f, 0.376f, 0.300f, 0.250f, 0.200f, 0.150f };
static const float sens_z_ut[8]  = { 1.210f, 0.968f, 0.726f, 0.605f, 0.484f, 0.403f, 0.323f, 0.242f };

static int mlx90393_read_register(const mlx90393_t *dev, uint8_t reg, uint16_t *value)
{
    uint8_t tx[2] = { CMD_READ_REGISTER, (uint8_t)(reg << 2) };
    uint8_t rx[3]; // 1 byte status + 2 bytes register value

    int ret = i2c_write_read(dev->i2c_dev, dev->i2c_addr, tx, sizeof(tx), rx, sizeof(rx));
    if (ret != 0) {
        return ret;
    }
    *value = (uint16_t)((rx[1] << 8) | rx[2]);
    return 0;
}

static int mlx90393_write_register(const mlx90393_t *dev, uint8_t reg, uint16_t value)
{
    uint8_t tx[4] = { CMD_WRITE_REGISTER, (uint8_t)(value >> 8), (uint8_t)value, (uint8_t)(reg << 2) };
    uint8_t status;

    int ret = i2c_write_read(dev->i2c_dev, dev->i2c_addr, tx, sizeof(tx), &status, 1);
    if (ret != 0) {
        return ret;
    }
    return (status & STATUS_ERROR) ? -EIO : 0;
}

int mlx90393_init(mlx90393_t *dev)
{
    if (!device_is_ready(dev->i2c_dev)) {
        printk("# [%s] I2C bus driver not ready\n", dev->label);
        return -ENODEV;
    }

    uint8_t status = 0;

    /* Force exit to standby so the reset is accepted even if a mode was running */
    mlx90393_send_command(dev, CMD_EXIT_MODE, &status);
    k_msleep(5);

    /* Issue software reset */
    if (mlx90393_send_command(dev, CMD_RESET, &status) != 0) {
        return -EIO;
    }
    k_msleep(20);

    /* Read gain and resolution so raw counts can be converted to gauss */
    uint16_t reg0, reg2;
    if (mlx90393_read_register(dev, 0x00, &reg0) != 0 ||
        mlx90393_read_register(dev, 0x02, &reg2) != 0) {
        return -EIO;
    }
    dev->hallconf = reg0 & 0x0F;
    dev->gain_sel = (reg0 >> 4) & 0x07;
    dev->res_x = (reg2 >> 5) & 0x03;
    dev->res_y = (reg2 >> 7) & 0x03;
    dev->res_z = (reg2 >> 9) & 0x03;

    /* Set on-chip filtering (OSR bits [1:0], DIG_FILT bits [4:2]), keep the rest */
    reg2 = (reg2 & ~0x001F) | ((MLX90393_DIG_FILT & 0x07) << 2) | (MLX90393_OSR & 0x03);
    if (mlx90393_write_register(dev, 0x02, reg2) != 0 ||
        mlx90393_read_register(dev, 0x02, &reg2) != 0) {
        return -EIO;
    }
    dev->osr = reg2 & 0x03;
    dev->dig_filt = (reg2 >> 2) & 0x07;

    /* Conversion time (datasheet): per axis 0.064 ms * 2^OSR * (2 + 2^DIG_FILT),
     * three axes, plus margin */
    dev->conv_ms = (uint16_t)(3.0f * 0.064f * (1 << dev->osr) * (2 + (1 << dev->dig_filt))) + 10;

    printk("# [%s] GAIN_SEL=%u HALLCONF=0x%X RES(x,y,z)=%u,%u,%u OSR=%u DIG_FILT=%u (%u ms)\n",
           dev->label, dev->gain_sel, dev->hallconf, dev->res_x, dev->res_y, dev->res_z,
           dev->osr, dev->dig_filt, dev->conv_ms);
    if (dev->hallconf != 0x0C) {
        printk("# [%s] Warning: HALLCONF is not 0xC, gauss values are approximate\n", dev->label);
    }

    return 0;
}

/* Convert one axis to uT. RES 2 and 3 return unsigned data offset by 32768 / 16384. */
static float axis_to_ut(int16_t raw, uint8_t res, float base_sens)
{
    int32_t counts = raw;
    if (res == 2) {
        counts = (uint16_t)raw - 32768;
    } else if (res == 3) {
        counts = (uint16_t)raw - 16384;
    }
    return (float)counts * base_sens * (float)(1 << res);
}

void mlx90393_to_gauss(const mlx90393_t *dev, const mlx90393_data_t *raw,
                       mlx90393_gauss_t *out)
{
    /* 1 gauss = 100 uT */
    out->x = axis_to_ut(raw->x, dev->res_x, sens_xy_ut[dev->gain_sel]) / 100.0f;
    out->y = axis_to_ut(raw->y, dev->res_y, sens_xy_ut[dev->gain_sel]) / 100.0f;
    out->z = axis_to_ut(raw->z, dev->res_z, sens_z_ut[dev->gain_sel]) / 100.0f;
}

int mlx90393_read_axes(const mlx90393_t *dev, mlx90393_data_t *data)
{
    if (data == NULL) {
        return -EINVAL;
    }

    uint8_t buffer[7]; // 1 byte status + 6 bytes data (2 bytes per axis)

    /* Trigger single measurement on X, Y, and Z */
    uint8_t start_cmd = CMD_START_MEASUREMENT | AXIS_XYZ_FLAGS;
    uint8_t status = 0;
    int ret = i2c_write_read(dev->i2c_dev, dev->i2c_addr, &start_cmd, 1, &status, 1);
    if (ret != 0) {
        printk("# [%s] SM failed: %d\n", dev->label, ret);
        return ret;
    }

    /* Wait for conversion cycle */
    k_msleep(dev->conv_ms);

    /* Read back measurement registers */
    uint8_t read_cmd = CMD_READ_MEASUREMENT | AXIS_XYZ_FLAGS;
    ret = i2c_write_read(dev->i2c_dev, dev->i2c_addr, &read_cmd, 1, buffer, sizeof(buffer));
    if (ret != 0) {
        printk("# [%s] RM failed: %d (SM status 0x%02x)\n", dev->label, ret, status);
        return ret;
    }

    /* Big-endian 16-bit signed conversion */
    data->x = (int16_t)((buffer[1] << 8) | buffer[2]);
    data->y = (int16_t)((buffer[3] << 8) | buffer[4]);
    data->z = (int16_t)((buffer[5] << 8) | buffer[6]);

    return 0;
}

int mlx90393_read_gauss(const mlx90393_t *dev, mlx90393_gauss_t *out)
{
    mlx90393_data_t raw;
    int ret = mlx90393_read_axes(dev, &raw);
    if (ret == 0) {
        mlx90393_to_gauss(dev, &raw, out);
    }
    return ret;
}
