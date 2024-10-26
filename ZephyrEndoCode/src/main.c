/* main.c - starts up threads in an orderly fashion 
* then basically sleeps .
* started April 2023 by R. Fearing copying from EE192 2021 skeleton
* converting FreeRTOS to Zephyr RTOS
*
*  modified to have 12 PWM channel for pressure regulators
* and using PC6, PC7, PC8, PC9 for PWM 
*/

/*
 * Copyright (c) 2012-2014 Wind River Systems, Inc.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr.h>
#include <sys/printk.h>
#include <stdio.h>
#include <stdlib.h>
#include <console/console.h>

//#include <device.h>
//#include <devicetree.h>
//#include <drivers/gpio.h>

#include "common.h"

/*******************************************************************************
 * Prototypes
 ******************************************************************************/
extern void printq_add(char *msg);
extern int led_init();
extern void led_toggle();
extern void dac_init(void);
extern void adc_init(void);
extern void adc_test(void);
extern void pwm_init(void);
extern void gpout_init(void);
extern void pwm_test(void);
extern void hx711_init(void);
extern void qdec_init(void);
extern void hx711_test(void);
extern void start_hx711(void);
extern void start_print_thread(void);
extern void start_heartbeat(void);
extern void thread_info(void);
extern void start_control(void);
extern void uart_interrupt_init();
extern void start_uart_input(void);
extern void start_print_state(void); 


void main(void)
{ 	long a = 0;
	char string[80];
	// use # as first character for comment to ignore
	printk("# Endonasal Branch 7/17/24 from main()\n");
 
  	if(led_init())
  		printk("# led_init: success. Wait for LED blink\n");
	else
		printk("# led_init: failed.\n");
 
  	while(a < 50)
  	{ 	led_toggle();
  		k_msleep(SLEEP_TIME_MS/10);
		a = a + 1;
	}
  
   	start_print_thread();
	printq_add("# printq test message- hello from main.c \n");
	snprintf(string, 80, "# Clock cycles per second %d\n",CONFIG_SYS_CLOCK_HW_CYCLES_PER_SEC);
	printq_add(string);
	k_msleep(250); // suspend main() to allow print to run
	// snprintf(string, 80, "# float number %f\n", 3.14159);
	// printk("%s", string);
	/* Peripheral initialization */
    dac_init();
    adc_init();
//	adc_test();
  	pwm_init();
	gpout_init();
 //   pwm_test();
	hx711_init();
 //	hx711_test();
 	qdec_init();
 
	/* thread starting*/
    start_heartbeat();
	// k_msleep(10);
	// thread_info(); // get thread info for debugging
	uart_interrupt_init();
    start_uart_input();
	// k_msleep(10);
	// thread_info(); // get thread info for debugging
	// printq_add("# main.c after start_uart_input\n");
	start_hx711();
	// k_msleep(10);
	// thread_info(); // get thread info for debugging
    start_control();

	start_print_state();
	k_msleep(250); // suspend main() to allow print to run 
    thread_info(); // get thread info for debugging
	//k_msleep(10);
	//thread_info(); // get thread info for debugging
 	k_msleep(4*SLEEP_TIME_MS); // wait to see what time threads have used
 	thread_info(); // get thread info for debugging
	// printq_add("# main.c after thread_info()\n");
	printq_add("# STM32READY\n"); // python script should wait for this before starting
	
	while(1)
	{	k_msleep(5*SLEEP_TIME_MS);  // just wait so other threads can run
		
	}
}