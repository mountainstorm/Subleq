#!/usr/bin/python
# coding: latin-1
#
# subleq.py
# subleq
#
# Created by R J Cooper on 10/09/2011.
# Copyright 2011 Mountainstorm. All rights reserved.
#
# subleq assembler
#

import ply.lex as lex
import ply.yacc as yacc
import os
import os.path
import types
import struct
import sys
import subprocess
import pickle


class Parser:
	tokens = ()
	precedence = ()

	def __init__(self, **kw):
		self.debug = kw.get('debug', 0)
		self.names = { }
		try:
			modname = os.path.split(os.path.splitext(__file__)[0])[1] + "_" + self.__class__.__name__
		except:
			modname = "parser"+"_"+self.__class__.__name__
		self.debugfile = modname + ".dbg"
		self.tabmodule = modname + "_" + "parsetab"
		#print self.debugfile, self.tabmodule

		# Build the lexer and parser
		lex.lex(module=self, debug=self.debug)
		yacc.yacc(module=self,
				  debug=self.debug,
				  debugfile=self.debugfile,
				  tabmodule=self.tabmodule)

	def run(self, data):
		yacc.parse(data)


class Subleq(Parser):
	def __init__(self, pack):
		Parser.__init__(self)
		self.debug = False
		self.pack = pack # the struct.pack string used for a word
		self.code = ""
		self.linking = None
		self.debugInfo = None
		
		
	def run(self, data):
		self.code = "" # the code stream
		self.instStack = []
		self.linking = {
			"labels": {},	# dict of label names against their offsets
			
			"literals": {},	# dict of literal values and the offsets to point to them
			"fixups": {},	# dict of offsets (to fixup) against the label it should point to

			"offsets": {},	# dict of offsets against the label/literal we want the offset of
			"derefs": {}	# dict of offsets against the label we want the value at
		}
		self.dbg = {
			"labels": {}, 	# dict of label names against their offsets
			"literals": {},	# dict of literal against their offsets
			"offsets" : {}, # dict of .offset strings against their offsets
			"inst" : {},	# dict of offsets against {inst:"", children:{}}
		}
	
		Parser.run(self, data)
		self.link()
		
		
	def link(self):
		self.addAlign(4) # align the literals - not needed but good practice

		# store of all literal names aagainst their locations
		literals = {}

		# output up the literals and fix them up
		for l in self.linking["literals"]:
			offsets = self.linking["literals"][l]
			for o in offsets:
				self.patch(o, len(self.code))
			literals[l] = len(self.code)
			self.code += struct.pack(self.pack, l)
			
		# all the labels exist now; so process all the fixups to point to their labels
		for f in self.linking["fixups"]:
			label = self.linking["fixups"][f]
			if label in self.linking["labels"]:
				self.patch(f, self.linking["labels"][label])
			else:
				print "Error; label %s not defined" % self.linking["fixups"][f]
		
		# sort out all the address
		for o in self.linking["offsets"]:
			label = self.linking["offsets"][o]
			# a literal or unmodified label
			try:
				num = int(label)
				offset = self.getLiteralOffset(num, literals)
				self.dbg["offsets"][offset] = ".offset " + label
			except:
				offset = 0
				if label in self.linking["labels"]:
					num = self.linking["labels"][label]
					offset = self.getLiteralOffset(num, literals)
					self.dbg["offsets"][".offset " + label] = offset
				else:
					print "Error; label %s not defined" % label
			self.patch(o, offset)
			
		# sort out all the derefs
		for d in self.linking["derefs"]:
			label = self.linking["derefs"][d]
			offset = 0
			if label in self.linking["labels"]:
				num = self.linking["labels"][label]
				offset = (num * -1)
			else:
				print "Error; label %s not defined" % label
			self.patch(d, offset)
			
		# put labels into dbg
		self.dbg["labels"] = self.linking["labels"]
		self.dbg["literals"] = literals
		
			
	def getLiteralOffset(self, num, literals):
		# find this num in the literals table
		if num in literals:
			offset = literals[num]
		else:
			offset = len(self.code)
			literals[num] = offset # add our offset literal into dbg
			self.code += struct.pack(self.pack, num)
		return offset
	
	
	def patch(self, offset, value):
		pre = self.code[:offset]
		post = self.code[offset + self.getWordSize():]
		self.code = pre + struct.pack(self.pack, value) + post
			
	def call(self, inst, *args):
		inst = inst.lower()
		p = [None, inst]
		for i in xrange(0, len(args)):
			if type(args[i]) is not types.ListType:
				p.append([args[i]])
			else:
				p.append(args[i])
			if i != (len(args) - 1):
				p.append(",")
		method = getattr(self, "p_%s" % inst)
		method(p)
		
		
	def addLabel(self, label):
		if label not in self.linking["labels"]:
			self.linking["labels"][label] = len(self.code)
		else:
			print "Error; label already defined"
			
			
	def addLiteral(self, literal):
		if literal in self.linking["literals"]:
			self.linking["literals"][literal].append(len(self.code))
		else:
			self.linking["literals"][literal] = [len(self.code)]
			
			
	def addFixup(self, label):
		self.linking["fixups"][len(self.code)] = label
		
		
	def addOffset(self, label):
		self.linking["offsets"][len(self.code)] = label
		
		
	def addDeref(self, label):
		self.linking["derefs"][len(self.code)] = label
			
			
	def addAlign(self, value):
		if len(self.code) % value:
			pad = self.getWordSize() - (len(self.code) % self.getWordSize())
			self.code += struct.pack("%ux" % pad)
				
				
	def beginCallDbg(self, p):
		inst = "%s" % p[1]
		if len(p) >= 3:
			inst += " %s" % self.argToStr(p[2])
			if len(p) >= 5:
				inst += ", %s" % self.argToStr(p[4])
				if len(p) >= 7:
					inst += ", %s" % self.argToStr(p[6])

		call = {"inst": inst, "offset": len(self.code), "children":{}}
		if len(self.instStack) > 0:
			self.instStack[-1]["children"][len(self.code)] = call
		self.instStack.append(call)		


	def argToStr(self, arg):
		if type(arg) == types.ListType:
			if len(arg) == 1:
				arg = arg[0]
			elif len(arg) == 2:
				arg = arg[0] + " " + arg[1]
			elif len(arg) == 3:
				arg = arg[0] + arg[1] + arg[2]
		return arg


	def endCallDbg(self):
		call = self.instStack.pop()
		call["length"] = len(self.code) - call["offset"]
		if len(self.instStack) == 0:
			self.dbg["inst"][call["offset"]] = call


	def packWord(self, value):
		return struct.pack(self.pack, value)
		
		
	def addSubleqArg(self, arg):
		if arg[0] == ".offset":
			self.addOffset(arg[1])
		elif arg[0] == "[":
			self.addDeref(arg[1])
		else:
			# a number or unmodified label
			try:
				self.addLiteral(int(arg[0])) # add a const and a fixup to it
			except:
				self.addFixup(arg[0]) # fixup to label
		self.code += self.packWord(0)		
		
		
	def getSubleqSize(self):
		return (3 * self.getWordSize())
		
		
	def getWordSize(self):
		return struct.calcsize(self.pack)


	def dump(self, start = 0):
		# debug dump the program
		for i in xrange(start, len(self.code), 4):
			a, = struct.unpack("<I", self.code[i:i+4])
			comment = ""
			if i in self.dbg["comments"]:
				comment = self.dbg["comments"][i]
			print "0x%08x : 0x%08x%s" % (i, a, comment)


	#
	# Token definition
	#
	instructions = (
		'SUBLEQ',
		'JMP', 'SUB', 'ADD', 'MOV', 'PUSH', 
		'CALLC', 'HALT',
	)
	
	tokens = instructions + (
		'COMMA', 'COLON', 'LBRACE', 'RBRACE',
		'OFFSET', 
		'ASCII', 'INT', 'FILL', 'ALIGN',
		'IDENTIFIER', 'NUMBER', 'STRING',
	)
	
	
	# Token regex's
	t_COMMA			= r','
	t_COLON			= r':'
	t_LBRACE		= r'\['
	t_RBRACE		= r'\]'
	
	t_OFFSET		= r'\.offset'
	
	t_ASCII			= r'\.ascii'
	t_INT			= r'\.int'
	t_FILL			= r'\.fill'
	t_ALIGN			= r'\.align'
		
	def t_IDENTIFIER(self, t):
		r'[a-zA-Z_][a-zA-Z0-9_]*'
		val = t.value.upper()
		if val in self.instructions:
			t.type = val
		else:
			try:
				self.t_NUMBER(t)
			except:
				pass
		return t
	
	def t_NUMBER(self, t):
		r'[-+]?\d+|[a-fA-F0-9]+h|[01]+b'
		if t.value[-1] == 'b':
			t.value = int(t.value[:-1], 2)
		elif t.value[-1] == 'h':
			t.value = int(t.value[:-1], 16)
			t.type = "NUMBER"
		else:
			t.value = int(t.value)
		return t
	
	def t_STRING(self, t):
		r'"([^"]*)"'
		t.value = t.value[1:-1]
		return t
		
	t_ignore		= ' \t'
	
	def t_COMMENT(self, t):
		r'[;#][^\n]*' # ignore both comments and # (preprocessor) lines 
		pass
		
	def t_newline(self, t):
		r'\n+'
		t.lexer.lineno += len(t.value)
		
	def t_error(self, t):
		#raise SyntaxError("Unknown symbol %r" % (t.value[0],))
		print "Skipping", repr(t.value[0])
		t.lexer.skip(1)
	
	#
	# Statements
	#
	def p_module(self, p):
		'''module : statement-list'''
		pass
		
	def p_statement_list(self, p):
		'''statement-list : statement
						  | statement statement-list'''
		pass
	
	def p_statement(self, p):
		'''statement : label
					 | int
					 | ascii
					 | fill
					 | align
					 | subleq
					 | jmp
					 | sub
					 | add
					 | mov
					 | push
					 | callc
					 | halt'''
		pass
	
	def p_label(self, p):
		'''label : IDENTIFIER COLON'''
		self.addLabel(p[1])
	
	def p_int(self, p):
		'''int : INT intargs'''
		self.code += p[2]
		
	def p_intargs(self, p):	
		'''intargs : NUMBER
				   | NUMBER COMMA intargs'''
		p[0] = self.packWord(p[1])
		if len(p) == 4:
			p[0] += p[3]
			
	def p_ascii(self, p):
		'''ascii : ASCII STRING'''
		self.code += struct.pack("%us" % len(p[2]), p[2])
		self.addAlign(self.getWordSize())
	
	def p_fill(self, p):
		'''fill : FILL NUMBER'''
		for i in xrange(0, p[2]):
			self.code += self.packWord(0)
	
	def p_align(self, p):
		'''align : ALIGN NUMBER'''
		self.addAlign(p[2])
					
	def p_subleq(self, p):
		'''subleq : SUBLEQ arg COMMA arg
				  | SUBLEQ arg COMMA arg COMMA IDENTIFIER'''
		self.beginCallDbg(p)
		self.addSubleqArg(p[2])
		self.addSubleqArg(p[4])
		if len(p) <= 5:
			# jmp to next instruction
			self.code += self.packWord(len(self.code) + self.getWordSize())
		else:
			self.addFixup(p[6][0])
			self.code += self.packWord(0)
		self.endCallDbg()

	def p_jmp(self, p):
		'''jmp : JMP IDENTIFIER''' 
		self.beginCallDbg(p)
		self.call("subleq", "Z", "Z", p[2])
		self.endCallDbg()
			
	def p_sub(self, p):
		'''sub : SUB arg COMMA arg''' 
		self.beginCallDbg(p)
		self.call("subleq", p[2], p[4])
		self.endCallDbg()
		
	def p_add(self, p):
		'''add : ADD arg COMMA arg''' 
		self.beginCallDbg(p)
		self.call("subleq", p[2], "Z")
		self.call("subleq", "Z", p[4])
		self.call("subleq", "Z", "Z")
		self.endCallDbg()
		
	def p_mov(self, p):
		'''mov : MOV arg COMMA arg''' 
		self.beginCallDbg(p)
		self.call("sub", p[4], p[4])
		self.call("add", p[2], p[4])
		self.endCallDbg()

	def p_push(self, p):
		'''push : PUSH arg''' 
		self.beginCallDbg(p)
		self.call("sub", 4, "sp")
		self.call("mov", p[2], ["[", "sp", "]"])
		self.endCallDbg()
		
	def p_callc(self, p):
		'''callc : CALLC''' 
		self.beginCallDbg(p)
		self.call("add", "bar", "sp")		
		self.beginCallDbg(["trap", "trap", -2])
		self.addSubleqArg(["Z"])
		self.addSubleqArg(["sp"])
		self.code += self.packWord(-2)
		self.endCallDbg()
		self.call("sub", "bar", "sp")		
		self.endCallDbg()
		
	def p_arg(self, p):
		'''arg : NUMBER
			   | IDENTIFIER
			   | OFFSET NUMBER
			   | OFFSET IDENTIFIER
			   | LBRACE IDENTIFIER RBRACE'''
		p[0] = p[1:]
	
	def p_halt(self, p):
		'''halt : HALT'''
		self.beginCallDbg(p)
		self.addSubleqArg(["Z"])
		self.addSubleqArg(["Z"])
		self.code += self.packWord(-1)
		self.endCallDbg()
		
	def p_error(self, p):
		val = ""
		line = -1
		if p:
			val = p.value
			line = p.lexer.lineno
		print "Syntax error at '%s' line: %u" % (val, line)


if __name__ == '__main__':
	argc = len(sys.argv)
	if argc == 2 or argc == 3:
		input = sys.argv[1]
		output = os.path.splitext(input)[0] + ".bin"
		if argc == 3:
			output = sys.argv[2]
		dbgFile = os.path.splitext(output)[0] + ".dbg"

		data = subprocess.Popen(["cpp", input], stdout=subprocess.PIPE).communicate()[0]
		subleq = Subleq("<i")
		subleq.run(data)
	
		f = file(output, "wb+")
		if f:
			f.write(subleq.code)
			f.close()
			
			f = file(dbgFile, "wb+")
			if f:
				pickle.dump(subleq.dbg, f)
				f.close()
			else:
				print "Unable to create debug info file: %s" % (dbgFile)
		else:
			print "Unable to create output file: %s" % (output)
	else:
		print "Usage: subleq.py <input.slq> [<output.bin>]"
			