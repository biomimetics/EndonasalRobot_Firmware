/* module to initialize some general purpose outputs 
PA12
PC8
PC9
PC13 
outputs are configured using push-pull (active high and active low)
*/
#include "stm32f4xx_ll_bus.h"
#include "stm32f4xx_ll_gpio.h"
#include <zephyr.h>
#include <stdio.h>
#include "common.h"

void gpout_int(void);
void digitalOutputOff(uint32_t);
void digitalOutputOn(uint32_t);


void gpout_init(void)
{
/* Enable GPIO clock */
    LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOA);
 //   LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOB);
    LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOC);

    LL_GPIO_InitTypeDef GPIO_InitStruct;
// Configure GPIOA PA12 for Output1Pin
    GPIO_InitStruct.Pin = LL_GPIO_PIN_12;
    GPIO_InitStruct.Mode = LL_GPIO_MODE_OUTPUT;
    GPIO_InitStruct.OutputType = LL_GPIO_OUTPUT_PUSHPULL;
    LL_GPIO_Init(GPIOA, &GPIO_InitStruct);
    LL_GPIO_ResetOutputPin(GPIOA, Output1Pin); // disable at initialize

// Configure GPIOC pins 
// also PC8, PC9, PC13 for output 
  //  GPIO_InitStruct.Pin = LL_GPIO_PIN_8 | LL_GPIO_PIN_9 | LL_GPIO_PIN_13;
  // ENDONASAL
    GPIO_InitStruct.Pin =  LL_GPIO_PIN_13;
    GPIO_InitStruct.Mode = LL_GPIO_MODE_OUTPUT;
    GPIO_InitStruct.OutputType = LL_GPIO_OUTPUT_PUSHPULL;
    LL_GPIO_Init(GPIOC, &GPIO_InitStruct);
  // ENDONASAL  
 //   LL_GPIO_ResetOutputPin(GPIOC, Output2Pin); // disable at initialize
 //   LL_GPIO_ResetOutputPin(GPIOC, Output3Pin); // disable at initialize
    LL_GPIO_ResetOutputPin(GPIOC, Output4Pin); // disable at initialize

    #ifdef DEBUG_PRINT
//    printk("# End GP Output init. PA12 PC8 PC9 PC13\n");
    printk("# End GP Output init. PA12 PC13\n");
    #endif
}


// general output bits (used for solenoid valves)
void digitalOutputOn(uint32_t value)
{   switch(value)
    {   case 1:
            LL_GPIO_SetOutputPin(GPIOA, Output1Pin);
            break;
        case 99:
 //           LL_GPIO_SetOutputPin(GPIOC, Output2Pin);
            break;
        case 100:
 //           LL_GPIO_SetOutputPin(GPIOC, Output3Pin);
            break;
        case 4:
            LL_GPIO_SetOutputPin(GPIOC, Output4Pin);
            break;
        default: 
            printk("invalid channel for DigitalOutputOn\n");
            break;  // ignore if out of range
    }
}
// general output bits (used for solenoid valves)
void digitalOutputOff(uint32_t value)
{   switch(value)
    {   case 1:
            LL_GPIO_ResetOutputPin(GPIOA, Output1Pin);
            break;
        case 99:
//            LL_GPIO_ResetOutputPin(GPIOC, Output2Pin);
            break;
        case 100:
 //           LL_GPIO_ResetOutputPin(GPIOC, Output3Pin);
            break;
        case 4:
            LL_GPIO_ResetOutputPin(GPIOC, Output4Pin);
            break;
        default: 
            printk("invalid channel for DigitalOutputOff\n");
            break;  // ignore if out of range
    }
}
