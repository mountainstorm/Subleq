.globl _callc32
.globl _callc64


#if __LP64__

.data
gProcessorRsp:	.quad	0

.text
_callc64:
	movq %rsp, gProcessorRsp(%rip)
	movq gProcessorRsp(%rip), %rsp
	ret

#else	

.data
gProcessorEsp:	.long	0

.text
_callc32:
	movl %esp, gProcessorEsp
	movl %esp, %eax
	addl $4, %eax
	movl (%eax), %esp
	popl %eax
	call *%eax
	pushl %eax
	movl gProcessorEsp, %esp
	ret
	
#endif
