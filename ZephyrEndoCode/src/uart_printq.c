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

// Includes
#include <stdio.h>
#include <stdlib.h>
#include <zephyr.h>
#include <sys/printk.h>
#include "common.h"

/*******************************************************************************
 * Definitions
 ******************************************************************************/

// allow 128 characters per message
K_MSGQ_DEFINE(printq, TEXT_LINE_LENGTH, 8, 4); // 8 items max 

// use semaphor to only give 1 thread access to printq at a time
K_SEM_DEFINE(printq_sem, 0,1); // in effect binary semaphore, max count of 1

static char text_buffer[TEXT_LINE_LENGTH];

/* size of stack area used by each thread */
#define STACKSIZE 1024
/* scheduling priority used by each thread */
/* CAUTION: if printq reading is higher priority than writing can block with empty printq
* and lockout lower priority threads 
*/ 
#define PRINT_PRIORITY 70  //higher number = lower priority, 
#define THREAD_DELAY 1000 // milliseconds

typedef unsigned long int   u32_t;
extern void led_toggle();
extern u32_t get_time_diff(void);
/*******************************************************************************
 * Prototypes
 ******************************************************************************/
void printq_add(char *msg);
void printq_init(uint32_t queue_length, uint32_t max_msg_length);
void uart_print_thread();
void printString(char *);  // quick replacement for printf to save stack space
void start_print_thread(void);

/*******************************************************************************
 * Functions
 ******************************************************************************/

// Initialize logging queue (used for both UART and WiFi) and recv queue for commands from WiFi
void printq_init(uint32_t queue_length, uint32_t max_msg_length)
{   // already set up by K_MSGQ_DEFINE(print

}


// return checksum character to append to a string
uint16_t checksum(char *buffer)
{   int i, j;
    uint16_t sum = 0;
    char number[7];
    // printf("buffer =\n %s", buffer);
    i = 0;
    sum = 0;
    /* stop before copying \n */
    while( (buffer[i]!='\n') && (buffer[i]!= '\0') && (i< TEXT_LINE_LENGTH-4))
    {
      //  printf("i=%d char=%x \t", i, (int)buffer[i]);
        sum += (unsigned char) buffer[i];
        text_buffer[i] = buffer[i]; // copy text to strip \n character
        i++;
    }
    // checksum doesn't include \n, just add up characters, and print as decimal for ease of reading in python - last 4 characters of line
    sum = (sum & 0xffff); // truncate to 16 bit value
    // printf("end of checksum. checksum %d %x\n", sum, sum);
    snprintf(number, 7," %4x\n", sum); // <sp>+4 nums + \n + \0
    for(j =0; j<7; j++)
    { text_buffer[i+j] = number[j]; }
    text_buffer[i+j+1]='\0';

    return(sum);
}


// add an item to the print queue
// textbuffer is set by checksum()
void printq_add(char *msg)
{   uint32_t printq_used;
    uint16_t cksum;

    cksum = checksum(msg);
  //  printk("%s %4x\n", msg,cksum);
  //  printk("%s", text_buffer);
    if(k_sem_take(&printq_sem, K_MSEC(50)))
    { printk("# printq access blocked by other thread. msg = %s", msg); } //assume msg has \n
    else
    {
        if(k_msgq_put(&printq, text_buffer, K_NO_WAIT) != 0) // send data to back of queue,
        {  printq_used = k_msgq_num_used_get (&printq);
           printk("# printq_add: printq put failed. Used %d with %s\n", printq_used, msg);
           
            
        }
    }
    // non-blocking, wait=0 ==> return immediately if the queue is already full.
    #ifdef DEBUG_PRINT1
    printk("# printq_add %d %s", count, msg);
    #endif
    k_sem_give(&printq_sem);
}

K_THREAD_STACK_DEFINE(print_thread_stack_area, STACKSIZE);
static struct k_thread print_thread_data;

void start_print_thread(void)
{
    printk("# Starting print thread\n");
    /* spawn print thread */
	k_tid_t tid = k_thread_create(&print_thread_data, print_thread_stack_area,
			STACKSIZE, uart_print_thread, NULL, NULL, NULL,
			PRINT_PRIORITY, 0, K_FOREVER);

	k_thread_name_set(tid, "print_thread");

	k_thread_start(&print_thread_data);
}



// Task for printing log
void uart_print_thread()
{   int no_msg;
    // uint32_t time_diff;
    uint32_t counter = 0;
    char log[TEXT_LINE_LENGTH + 1];

    while (1)
    {   no_msg = k_msgq_get(&printq, &log, K_NO_WAIT); // wait for new item on queue
        if (no_msg == 0)
        {
           //  time_diff = get_time_diff();
            #ifdef DEBUG_PRINT1
                printk("msg %d %s ", counter, log);  // \n and \r already in log
            #else
                printk("%s", log);  // \n and \r already in log
                // printString(log); // already formatted, so quicker than printk??
            #endif

            // 
           // time_diff = get_time_diff();
     //   printk("# time for printk: %u\n", time_diff);
            counter++;
            // led_toggle();
        }
        
        k_msleep(1); // let other threads run
    }
}

// add end of string protection
void printString(char *string)
{   
    int i=0;
    while ((string[i] != '\0') && (i < TEXT_LINE_LENGTH)) 
    {
            fputc(string[i],stdout); // print single character, avoid printf to save on stack space and speed up
            i++;
    }   
    if (i>= TEXT_LINE_LENGTH) 
        printk("# printString buffer overrun %d chars", i);
}

