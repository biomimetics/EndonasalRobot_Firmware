#include <zephyr.h>
#include <device.h>
#include <devicetree.h>
#include <drivers/gpio.h>
#include <drivers/uart.h>
#include <sys/printk.h>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#include "mlx90393.h"
#include "calibration.h"

/*
 * Serial protocol (same as ZephyrEndoCode / control-record.py), 230400 baud:
 *
 *   STM32 -> PC: comment lines start with "# ". After init "# STM32READY" is
 *                sent, then one comma separated state line every PRNWAIT ms:
 *                    time, mag1_x, mag1_y, mag1_z, mag2_x, mag2_y, mag2_z
 *                (time in s since boot, field in gauss with calibration
 *                offsets removed, "nan" for a sensor that failed to read)
 *
 *   PC -> STM32: lines of "CMD value" pairs, several pairs per line allowed:
 *                    PRNWAIT ms   time between state lines
 *                    CALIB x      run the six-position calibration (x ignored)
 */

/* Initial time between state lines; change from Python with PRNWAIT */
#define PRINTWAIT 1000

/* Command line buffer; commands are up to 7 characters, like ZephyrEndoCode */
#define CMD_LINE_LENGTH 80
#define INPUT_CMD_LENGTH 8
#define CMD_QUEUE_LENGTH 8

/* Blue USER button (B1) on the Nucleo starts a calibration */
static const struct gpio_dt_spec button = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);
static struct gpio_callback button_cb;
static volatile bool button_flag;

/* Console UART (USART2 on the ST-Link virtual COM port) also receives commands */
static const struct device *uart_dev = DEVICE_DT_GET(DT_CHOSEN(zephyr_console));

/* Complete received lines, filled by the UART interrupt, read by main() */
K_MSGQ_DEFINE(cmd_lines, CMD_LINE_LENGTH, CMD_QUEUE_LENGTH, 4);
static volatile uint32_t dropped_lines;

static int32_t print_wait = PRINTWAIT;

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

static void button_isr(const struct device *port, struct gpio_callback *cb, uint32_t pins)
{
    button_flag = true;
}

/* Collect characters into a line; queue it at '\r' or '\n' (no printing in ISR) */
static void uart_isr(const struct device *dev, void *user_data)
{
    static char line[CMD_LINE_LENGTH];
    static size_t len;
    uint8_t c;

    if (!uart_irq_update(dev)) {
        return;
    }
    while (uart_irq_rx_ready(dev) && uart_fifo_read(dev, &c, 1) == 1) {
        if (c == '\r' || c == '\n') {
            if (len > 0) {
                line[len] = '\0';
                if (k_msgq_put(&cmd_lines, line, K_NO_WAIT) != 0) {
                    dropped_lines++;
                }
                len = 0;
            }
        } else if (len < CMD_LINE_LENGTH - 1) {
            line[len++] = (char)c;
        }
    }
}

/* Handle one command; replies are comments so Python can ignore them */
static void run_cmd(const char *cmd, int value)
{
    if (strcmp(cmd, "PRNWAIT") == 0) {
        if (value < 1) {
            value = 1;
        }
        printk("# PRNWAIT changed from %d to %d ms\n", print_wait, value);
        print_wait = value;
    } else if (strcmp(cmd, "CALIB") == 0) {
        calibration_run(sensors, offsets, NUM_SENSORS);
    } else {
        printk("# command %s unrecognized\n", cmd);
    }
}

/* Split a line like "PRNWAIT 10 CALIB 0" into command/value pairs */
static void parse_line(char *line)
{
    char *save;
    char *tok = strtok_r(line, " \t", &save);

    while (tok != NULL) {
        char cmd[INPUT_CMD_LENGTH];
        size_t i;

        for (i = 0; i < INPUT_CMD_LENGTH - 1 && tok[i] != '\0'; i++) {
            cmd[i] = (char)toupper((unsigned char)tok[i]);
        }
        cmd[i] = '\0';

        /* Value is optional: only consume the next token if it is a number */
        int value = 0;
        char *next = strtok_r(NULL, " \t", &save);
        if (next != NULL && (isdigit((unsigned char)next[0]) || next[0] == '-')) {
            value = (int)strtol(next, NULL, 10);
            next = strtok_r(NULL, " \t", &save);
        }
        run_cmd(cmd, value);
        tok = next;
    }
}

static void process_commands(void)
{
    char line[CMD_LINE_LENGTH];

    while (k_msgq_get(&cmd_lines, line, K_NO_WAIT) == 0) {
        parse_line(line);
    }
    if (dropped_lines > 0) {
        printk("# %u command lines dropped (queue full)\n", dropped_lines);
        dropped_lines = 0;
    }
}

static void print_state(float t, const mlx90393_gauss_t gauss[], const bool ok[])
{
    printk("%9.4f", t);
    for (size_t i = 0; i < NUM_SENSORS; i++) {
        if (ok[i]) {
            printk(", %8.4f, %8.4f, %8.4f", gauss[i].x, gauss[i].y, gauss[i].z);
        } else {
            printk(",      nan,      nan,      nan");
        }
    }
    printk("\n");
}

static void init_button(void)
{
    if (!device_is_ready(button.port)) {
        printk("# USER button not available, use CALIB command to calibrate\n");
        return;
    }
    gpio_pin_configure_dt(&button, GPIO_INPUT);
    gpio_pin_interrupt_configure_dt(&button, GPIO_INT_EDGE_TO_ACTIVE);
    gpio_init_callback(&button_cb, button_isr, BIT(button.pin));
    gpio_add_callback(button.port, &button_cb);
}

static void init_uart(void)
{
    if (!device_is_ready(uart_dev)) {
        printk("# console UART not ready, commands disabled\n");
        return;
    }
    uart_irq_callback_user_data_set(uart_dev, uart_isr, NULL);
    uart_irq_rx_enable(uart_dev);
}

void main(void)
{
    printk("# === Initializing Multi-Magnetometer Subsystem ===\n");

    init_button();

    /* Initialize all configured sensors */
    for (size_t i = 0; i < NUM_SENSORS; i++) {
        while (mlx90393_init(sensors[i]) != 0) {
            printk("# [%s] Init failed! Retrying in 2s (check wiring)...\n", sensors[i]->label);
            k_msleep(2000);
        }
        printk("# [%s] Successfully initialized.\n", sensors[i]->label);
    }

    init_uart();

    printk("# Press the blue USER button or send CALIB to run hard-iron calibration.\n");
    printk("# Commands: PRNWAIT ms, CALIB. State every %d ms (gauss):\n", print_wait);
    printk("#      t=,   mag1_x,   mag1_y,   mag1_z,   mag2_x,   mag2_y,   mag2_z\n");
    printk("# STM32READY\n"); /* Python waits for this before starting */

    mlx90393_gauss_t gauss[NUM_SENSORS];
    bool ok[NUM_SENSORS];
    int64_t next_print = k_uptime_get();

    while (1) {
        /* Sensors are read continuously; the newest values are printed */
        for (size_t i = 0; i < NUM_SENSORS; i++) {
            ok[i] = (mlx90393_read_gauss(sensors[i], &gauss[i]) == 0);
            if (ok[i]) {
                calibration_apply(&offsets[i], &gauss[i]);
            }
        }

        int64_t now = k_uptime_get();
        if (now >= next_print) {
            print_state(now / 1000.0f, gauss, ok);
            next_print = now + print_wait;
        }

        process_commands();

        if (button_flag) {
            calibration_run(sensors, offsets, NUM_SENSORS);
            button_flag = false; /* ignore presses made during calibration */
            printk("# Press USER button to recalibrate.\n");
        }

        k_yield();
    }
}
