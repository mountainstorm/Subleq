//
//  Processor.h
//  subleq
//
//  Created by R J Cooper on 10/09/2011.
//  Copyright 2011 Mountainstorm. All rights reserved.
//
//  C subleq implementation
//


#ifndef subleq_Processor_h
#define subleq_Processor_h


#include <stdint.h>


#if __LP64__ 
typedef int64_t ProcessorWord;
#else
typedef int32_t ProcessorWord;
#endif 


int Processor_step(char* data, unsigned int length, int ip);


#endif
