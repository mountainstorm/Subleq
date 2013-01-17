//
//  subleq-dbg.c
//  subleq-dbg
//
//  Created by R J Cooper on 17/09/2011.
//  Copyright 2011 __MyCompanyName__. All rights reserved.
//

#include <Python/Python.h>
#include <stdint.h>
#include <stdio.h>
#include "Processor.h"
#include <dlfcn.h>


// define our type; this allows us to manage the buffer ourselves, which is important as 
// once we patch in any addresses we dont want it moving in memory
typedef struct __Code {
    PyObject_HEAD
    char* buffer;
    unsigned int length;
} Code;


PyMODINIT_FUNC initsubleq(void);

// Code instance methods
static void Code_dealloc(Code* self);
static PyObject* Code_new(PyTypeObject* type, PyObject* args, PyObject* kwds);
static int Code_init(Code* self, PyObject* args, PyObject* kwds);
static PyObject* Code_getString(Code* self, PyObject* args);
static PyObject* Code_patchBAR(Code* self, PyObject* args);
static PyObject* Code_patchDlsym(Code* self, PyObject* args);
static PyObject* Code_step(Code* self, PyObject* args);


// The Code "Class" - a new python type
static PyMethodDef Code_methods[] = {
    {"getString", (PyCFunction) Code_getString, METH_VARARGS, "returns the range as a string"},
    {"patchBAR", (PyCFunction) Code_patchBAR, METH_VARARGS, "patches the base address of this\
    														 instances underlying buffer, into\
    														 the buffer at the supplied offset"},
    {"patchDlsym", (PyCFunction) Code_patchDlsym, METH_VARARGS, "patches the address of dlsym\
    															 into the underlying buffer at\
    															 the specificed offset"},    														 
    {"step", (PyCFunction) Code_step, METH_VARARGS, "steps the subleq processor one microinstruction"},
    {NULL}
};


static PyTypeObject CodeType = {
	PyObject_HEAD_INIT(NULL)
	0,											/*ob_size*/
	"subleq.Code",								/*tp_name*/
	sizeof(Code), 								/*tp_basicsize*/
	0,											/*tp_itemsize*/
	(destructor) Code_dealloc,					/*tp_dealloc*/
	0,											/*tp_print*/
	0,											/*tp_getattr*/
	0,											/*tp_setattr*/
	0,											/*tp_compare*/
	0,											/*tp_repr*/
	0,											/*tp_as_number*/
	0,											/*tp_as_sequence*/
	0,											/*tp_as_mapping*/
	0,											/*tp_hash */
	0,											/*tp_call*/
	0,											/*tp_str*/
	0,											/*tp_getattro*/
	0,											/*tp_setattro*/
	0,											/*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,	/*tp_flags*/
	"Code object, initialized from a string and used for passing data to/from\
	the subleq processor",						/* tp_doc */
	0,											/* tp_traverse */
	0,											/* tp_clear */
	0,											/* tp_richcompare */
	0,											/* tp_weaklistoffset */
	0,											/* tp_iter */
	0,											/* tp_iternext */
	Code_methods,								/* tp_methods */
	0,											/* tp_members */
	0,											/* tp_getset */
	0,											/* tp_base */
	0,											/* tp_dict */
	0,											/* tp_descr_get */
	0,											/* tp_descr_set */
	0,											/* tp_dictoffset */
	(initproc) Code_init,						/* tp_init */
	0,											/* tp_alloc */
	Code_new,									/* tp_new */ 
};


PyMODINIT_FUNC initsubleq(void) {
	if (PyType_Ready(&CodeType) == 0) {
		PyObject* module = Py_InitModule("subleq", NULL);
		if (module) {
			Py_INCREF(&CodeType);
			PyModule_AddObject(module, "Code", (PyObject*) &CodeType);
		}
	}
}


static void Code_dealloc(Code* self) {
	if (	self
		 && self->ob_type
		 && self->ob_type->tp_free) {
		if (self->buffer) {
			free(self->buffer);
			self->buffer = NULL;
		}
		self->length = 0;
		self->ob_type->tp_free((PyObject*)self);
	}
}


static PyObject* Code_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
	Code* self = NULL;
	if (type) {
		 self = (Code*) type->tp_alloc(type, 0);
		 if (self) {
		 	self->buffer = NULL;
		 	self->length = 0;
		 }
	}
	return (PyObject*) self;
}


static int Code_init(Code* self, PyObject* args, PyObject* kwds) {
	int retVal = -1;
	if (	self
		 && args) {
		const char* src = NULL;		
		int length = 0;
		    
		if (PyArg_ParseTuple(args, "s#", &src, &length)) {
    	    if (	src
    	    	 && length > 0) {
    	    	 self->buffer = (char*) malloc(length);
    	    	 if (self->buffer) {
    	    	 	(void) memcpy(self->buffer, src, length);
    	    	 	self->length = (unsigned int) length;
    	    	 	retVal = 0;
    	    	 }
    	    }
    	}
	}
	return retVal;
}


static PyObject* Code_getString(Code* self, PyObject* args) {
	PyObject* retVal = Py_BuildValue("");
	if (	self
		 && self->buffer
		 && args) {
		int offset = 0;
		int length = 0;
		
		if (PyArg_ParseTuple(args, "ii", &offset, &length)) {
			if (	offset >= 0 
				 && length > 0
				 && (offset + length) <= self->length) {
				// TODO: is this a memory leak of retVal?
				retVal = Py_BuildValue("s#", &self->buffer[offset], length);
			}
		}
	}
    return retVal;
}


static PyObject* Code_patchBAR(Code* self, PyObject* args) {
	PyObject* retVal = NULL;
	if (	self
		 && self->buffer
		 && args) {
		long int offset = 0;
		
		if (PyArg_ParseTuple(args, "i", &offset)) {
			if (	offset >= 0 
				 && (offset + sizeof(ProcessorWord)) <= self->length) {
				*((ProcessorWord*) &self->buffer[offset]) = (ProcessorWord) self->buffer;
				retVal = Py_BuildValue("");
			}
		}
	}
    return retVal;
}


static PyObject* Code_patchDlsym(Code* self, PyObject* args) {
	PyObject* retVal = NULL;
	if (	self
		 && self->buffer
		 && args) {
		long int offset = 0;
		
		if (PyArg_ParseTuple(args, "i", &offset)) {
			if (	offset >= 0 
				 && (offset + sizeof(ProcessorWord)) <= self->length) {
				*((ProcessorWord*) &self->buffer[offset]) = (ProcessorWord) dlsym;
				retVal = Py_BuildValue("");
			}
		}
	}
    return retVal;
}


static PyObject* Code_step(Code* self, PyObject* args) {
	PyObject* retVal = NULL;
	if (	self
		 && self->buffer
		 && args) {
		int ip = 0;
		
		if (PyArg_ParseTuple(args, "i", &ip)) {
			if (ip >= 0) {
				retVal = Py_BuildValue("i", Processor_step(self->buffer, self->length, ip));
			}
		}
	}
    return retVal;
}

