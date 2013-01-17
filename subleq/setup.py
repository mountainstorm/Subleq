from distutils.core import setup, Extension

setup(name = "Subleq",
	  version = "1.0",
	  ext_modules = [Extension("subleq", 
	  						   ["subleq.c", "Processor.c"],
	  						   extra_objects=["callc.o"],
	  						   extra_link_args=["-read_only_relocs", "suppress"])])