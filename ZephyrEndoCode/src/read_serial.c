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


/* thread for reading serial input without blocking
* serial input is written to command queue for asynchronous processing 
*/

#include <zephyr.h>
#include <sys/printk.h>
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <errno.h>
extern int errno;

#include <string.h>

#include <console/console.h>
#include "common.h"

/*******************************************************************************
 * Definitions
 ******************************************************************************/

extern struct k_msgq cmdq;  // command queue to hold received USB commands
extern volatile uint32_t uart_rx_overrun_count;  // bumped by Rx ISR when a byte is lost

/* size of stack area used by each thread */
#define STACKSIZE 2048
/* scheduling priority - larger = lower priority */
#define PRIORITY 64  // high number, low priority for input thread (blocking)

#undef CONFIG_UART_CONSOLE_ECHO
#define CONFIG_UART_CONSOLE_ECHO 0



/*******************************************************************************
 * Prototypes
 ******************************************************************************/
extern void printq_add(char *msg);
extern float get_time_float(void);
extern uint32_t get_time(void);
extern uint32_t get_time_diff(void);
void start_uart_input(void);
void uart_input_thread(void);
int parse_input(char *, struct cmd_struct_def *);

K_THREAD_STACK_DEFINE(input_stack_area, STACKSIZE);
static struct k_thread input_thread_data;   // structure to hold kernel data about thread


void start_uart_input(void)
{
    printk("# Starting uart input thread\n");
/* spawn control thread */
	k_tid_t tid = k_thread_create(&input_thread_data, input_stack_area,
			K_THREAD_STACK_SIZEOF(input_stack_area), 
            (k_thread_entry_t) uart_input_thread, 
            NULL, NULL, NULL, PRIORITY, 0, K_FOREVER);

	k_thread_name_set(tid, "input_thread");
	k_thread_start(&input_thread_data);
}

/* parse input manually- use basic functions to avoid problems with excess length or improperly terminated strings
* this avoid issues with strlcpy, or missing strtok_r()
*/
int parse_input(char *input, struct cmd_struct_def *cmd_struct)
{ 
  int i = 0; int j =0;
  char value_string[INPUT_CMD_LENGTH];
  int value;
  int digits_seen = 0;
  char *end_pointer; // end of scan for string to long conversion
  char c;

  cmd_struct->valid = 0;   // not trustworthy until a real number is parsed
  cmd_struct->value = 0;

  // copy first string to command in structure, up to space delimiter, or end of string
  c = input[i]; // read next character
  while( (i < INPUT_CMD_LENGTH-1) && (c != '\0') && (c != ' ') && (c != '\n') && (c != '\r'))
  { cmd_struct->cmd[i] = input[i];
    i++;
    c = input[i];
  }
  cmd_struct->cmd[i] = '\0'; // force string to be properly terminated at last input or truncate
  if( i==0)
  {  return(0); }   // no command text left: end of line

  // skip the delimiter(s) between the command word and its value
  while (input[i] == ' ')
  {  i++; }

  /* Collect the value. A space (or any non-digit) ENDS the value -- it is never
   * skipped over. Skipping spaces here used to splice two numbers together when
   * a byte was lost: "DAC3 0     4 9037" parsed as DAC3 = 049037 = full scale.
   */
  while( (j < INPUT_CMD_LENGTH-1) && (input[i] != '\0') )
  { c = input[i];
    if ( (c >= '0') && (c <= '9') )
    { value_string[j] = c;
      i++; j++;
      digits_seen = 1;
    }
    else if ( (c == '-') && (j == 0) )  // sign only allowed as first character
    { value_string[j] = c;
      i++; j++;
    }
    else
    { break; }  // space, letter, CR/LF or anything else terminates the value
  }
  value_string[j] = '\0'; // terminate string

  if (!digits_seen)
  { /* The command word arrived with no number behind it: the line was truncated
     * or bytes were lost. Substituting 0 here used to drive the addressed
     * actuator to zero pressure. Report the advance so scanning can continue
     * from the offending character, but leave valid = 0 so the caller drops it.
     */
    return(i);
  }

  value = (int) strtol(value_string, &end_pointer, 10);  // using base 10
  cmd_struct -> value = value;
  cmd_struct -> valid = 1;

  // consume trailing padding spaces so the next command starts on its first char
  while (input[i] == ' ')
  {  i++; }
  // printk("# cmd = %s value = %d\n", cmd_struct->cmd, cmd_struct->value);
  return(i);
}

void uart_input_thread(void)
{
    float time_stamp; // should be 64 bits
    char log[TEXT_LINE_LENGTH];
    char cmd_string[40];
    char line[80];
    int i = 0;
    int j = 0;
    int count, new_count;
    char c; 
    struct cmd_struct_def cmd_struct, dummy_struct;    // local copy structure char[8] cmd, int value
    long time_int;
    uint32_t cmdq_used;
    uint32_t overrun_at_line_start;
    
    // console_getline_init();
   // console_init();
    
    time_stamp = get_time_float();  // only 32 bits need to fix to 64
    snprintf(log, sizeof(log), "# Starting uart input thread: at tick %f \n",
           time_stamp);
    printq_add(log);

    while(1)  // main input loop
    {   k_msleep(SLEEP_TIME_MS); // need short delay to not miss input characters
    // or should wait for start of new line, and read at high priority
#ifdef DEBUG_PRINT1
        snprintf(log, sizeof(log),"# uart_input_thread. Enter Command txt+int:\n");
      	printq_add(log);
#endif
        // need getline without echo for interface with python
        overrun_at_line_start = uart_rx_overrun_count;
        c = '\n';
        while( (c == '\n') || (c == '\r'))  
        {  c = (char) console_getchar(); // discard extra line feed characters
        }
        line[0] = c;
        j = 1;
       
        while( (c != '\r') && (c != '\n') && (j < sizeof(line)-1))
        { 
          c = (char) console_getchar();
          line[j] = c;
          j++;
        }
        line[j-1] ='\0';   // omit end of line char. make sure string is terminated, last character is line[79]

        /* If the hardware lost any byte while this line was arriving, the line
         * cannot be trusted: a missing byte can merge two commands, truncate a
         * value, or splice two values into one. Drop the whole line -- Python
         * re-sends the full regulator/solenoid state periodically, so a skipped
         * line is harmless, while executing a corrupted one moves an actuator.
         */
        if (uart_rx_overrun_count != overrun_at_line_start)
        {   snprintf(log, sizeof(log),
                "# Rx overrun (total %u): discarded damaged line \"%s\"\n",
                (unsigned int) uart_rx_overrun_count, line);
            printq_add(log);
            continue;
        }


//        printk("# UART read line %s\n", line);

//        line = console_getline();  // returns pointer to char buffer with line (< 128 length)
        // need to parse input line
        count = 0; new_count = 0;
        time_stamp = get_time_float();
        cmd_struct.time_stamp = time_stamp;
// command is already echoed, only need extra printing for debugging:
#ifdef DEBUG_PRINT1
        snprintf(log, sizeof(log), "# uart_input_thread count %d time %f :\n", 
              i, cmd_struct.time_stamp);
        printq_add(log); 
#endif        
        log[0] = '\0'; // clear string
        strcat(log,"# ");
        while((new_count = parse_input(line+count, &cmd_struct)) != 0)
        { // printk("# cmd = %s value = %d\n", cmd_struct.cmd, cmd_struct.value);
          // input commmand should be added to command queue
          count = count + new_count;

          /* parse_input could not find a number for this command word: drop it
           * rather than execute it with a substituted value.
           */
          if (!cmd_struct.valid)
          {   snprintf(log, sizeof(log),
                  "# dropped malformed cmd \"%s\" (no numeric value)\n", cmd_struct.cmd);
              printq_add(log);
              continue;
          }

          // time_int = get_time_diff();

          /* **************
          time_int = get_time_diff();
          snprintf(log, sizeof(log), "# time diff = %ld cycles\n", 
                       time_int);
          printq_add(log); 
          */ 
          i++;
#ifdef DEBUG_PRINT1
          snprintf(cmd_string, sizeof(cmd_string), "%s %d, ", 
                       cmd_struct.cmd, cmd_struct.value);
         // printq_add(log); 
          strcat(log, cmd_string);
#endif

          /* cmdq can fall behind with burst from python, which is not real time*/
          /* to keep queue from overflowing when full, drop two commands, then add new command*/
           // non-blocking, wait=0 ==> return immediately if the queue is already full.
          if(k_msgq_put(&cmdq, &cmd_struct, K_NO_WAIT) != 0) // send data to back of queue,
          {   cmdq_used = k_msgq_num_used_get (&cmdq);
           //   printk("# uart_input_thread: cmdq put failed. Used %d with %s\n", cmdq_used, cmd_struct.cmd); 
              k_msgq_get(&cmdq, &dummy_struct, K_NO_WAIT); // drop first
              k_msgq_get(&cmdq, &dummy_struct, K_NO_WAIT); // drop second
              if(k_msgq_put(&cmdq, &cmd_struct, K_NO_WAIT) != 0) // try again to send data to back of queue
              { printk("# uart_input_thread: cmdq put failed after 2 drops \n"); }
          }
          
        }

        /* note snprintf is slow and takes ~100 us to print float and 50 us to print int 
          * also, printq can fall behind with more than 1 string per ms 
          */
#ifdef DEBUG_PRINT1
        strcat(log,"\n");
        // snprintf(log, sizeof(log), " \n"); // end command string
        printq_add(log); 
#endif
    }




}