all: callc.s Processor.c Processor.h subleq.c
	-rm *.o
	-rm -r build/
	gcc -c -arch i386 -arch x86_64 callc.s
	python setup.py build
	cp build/lib.macosx-10.7-intel-2.7/subleq.so ../
