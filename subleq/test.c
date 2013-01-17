#include <stdio.h>


extern void callc32(void* sp);
extern void callc64(void* sp);


char* hello = "hello world";


long stack[100] = {
};


int main(void) {
	long i = 0;
	printf("stack addr: %08x - printf: %08x - hello: %08x\n", stack, printf, hello);
	stack[98] = puts;
	stack[99] = hello;
	
#if __LP64__
	callc64(stack);
#else
	callc32(&stack[98]);
#endif
/*
	for (i = 0; i < 100; i++) {
		printf("%08x\n", stack[i]);
	}
*/
}