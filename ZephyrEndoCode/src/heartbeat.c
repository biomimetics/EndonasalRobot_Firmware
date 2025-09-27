/* MIT License

Copyright (c) 2024 Regents of The Regents of the University of California

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE. */



/* heart beat task. Can also use for watchdog timer keep alive*/
#include <zephyr.h>
#include <sys/printk.h>

/* size of stack area used by each thread */
#define STACKSIZE 128
/* scheduling priority - larger = lower priority */
#define PRIORITY 32
#define BEATTIME 500 // in ms

extern void led_toggle();

/*******************************************************************************
 * Prototypes
 ******************************************************************************/
void heartbeat_thread(void);
void start_heartbeat(void);

K_THREAD_STACK_DEFINE(heartbeat_stack_area, STACKSIZE);
static struct k_thread heartbeat_thread_data;


void start_heartbeat()
{
    
    printk("# Starting heartbeat thread\n");
/* spawn heartbeat thread */
	k_tid_t tid = k_thread_create(&heartbeat_thread_data, heartbeat_stack_area,
			K_THREAD_STACK_SIZEOF(heartbeat_stack_area), (k_thread_entry_t) heartbeat_thread, 
            NULL, NULL, NULL, PRIORITY, 0, K_FOREVER);

	k_thread_name_set(tid, "heartbeat");

	k_thread_start(&heartbeat_thread_data);

}

void heartbeat_thread(void)
{   // CAUTION: stack is too small to use printk
    while(1)
    {   k_msleep(BEATTIME); // 
        led_toggle();
    }
}