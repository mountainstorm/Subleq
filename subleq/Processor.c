//
//  Machine32.c
//  subleq
//
//  Created by R J Cooper on 10/09/2011.
//  Copyright 2011 Mountainstorm. All rights reserved.
//
//  C 32bit subleq implementation
//

#include "Processor.h"


typedef struct __Instruction {
	ProcessorWord src;
	ProcessorWord dst;
	ProcessorWord jmp;
} __attribute__((__packed__)) Instruction;


extern void callc32(void* sp);
extern void callc64(void* sp);


int Processor_step(char* data, unsigned int length, int ip) {
	int retIp = -1;
	if (    ip >= 0
		 && (ip + sizeof(Instruction) <= length)) {
		Instruction* inst = (Instruction*) &data[ip];
		ProcessorWord src = 0;
		ProcessorWord dst = 0;

		// Note: using abs is causing this to all go very wrong; I suspect its a 32/64 bit issue	
		src = inst->src;
		if (inst->src < 0) {
			src = inst->src * -1;
		}

		dst = inst->dst;
		if (inst->dst < 0) {
			dst = inst->dst * -1;
		}
		if (	((src + sizeof(ProcessorWord)) <= length)
			 && ((dst + sizeof(ProcessorWord)) <= length)) {
			 // dereference data
			if (inst->src < 0) {
				src = *((ProcessorWord*) &data[src]);
			}
		
			if (inst->dst < 0) {
				dst = *((ProcessorWord*) &data[dst]);
			}
			if (	((src + sizeof(ProcessorWord)) <= length)
				 && ((dst + sizeof(ProcessorWord)) <= length)) {
	
				*((ProcessorWord*) &data[dst]) -= *((ProcessorWord*) &data[src]);
		
				retIp = ip + (int) sizeof(Instruction);
				if (*((ProcessorWord*) &data[dst]) <= 0) {
					retIp = (int) inst->jmp;
				}
				
				// native call trap
				if (inst->jmp == -2) {
					ProcessorWord callSp = *((ProcessorWord*) &data[dst]);
#if __LP64__
					callc64((void*) callSp);
#else
					callc32((void*) callSp);
#endif
					retIp = ip + (int) sizeof(Instruction);
				}
			}
		}
	}
	return retIp;
}
