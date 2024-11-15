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


#include <zephyr.h>
#include <sys/printk.h>

// prototypes
void thread_info_print(k_tid_t, void *);
void thread_info(void);

void thread_info_print(k_tid_t thread_id, void *user_data)
{ 
    char thread_name[80];
	int err;
	const char *state_msg; // pointer to a constant string
	int priority;
	int stack_ptr, stack_size;
	long long unsigned int cycles; 
	
   // k_tid_t thread_id;
	// thread_id = k_current_get();
	err = k_thread_name_copy(thread_id, thread_name, sizeof(thread_name));
	if (err)
	{	printk("# thread name copy error %d\n", err);
	}
	state_msg = k_thread_state_str(thread_id); // CAUTION: possible string overflow!
	
	priority = k_thread_priority_get(thread_id);
	stack_ptr = thread_id ->stack_info.start;
	stack_size = thread_id ->stack_info.size;

	k_thread_runtime_stats_t rt_stats_thread;
 	k_thread_runtime_stats_get(thread_id, &rt_stats_thread);
	cycles = rt_stats_thread.execution_cycles;

	printk("# %16s  %10s %8d \t%x \t%d \t %llu\n", 
			thread_name, state_msg, priority, stack_ptr, stack_size, cycles);
}


void thread_info(void)
{	void *cb_data[80]; 

	printk("# Name                State     Priority   Stack         size     cycles\n");
	k_thread_foreach((k_thread_user_cb_t) thread_info_print, cb_data);

}