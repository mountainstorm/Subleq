#!/usr/bin/python
# coding: latin-1
#
# subleq-debug.py
# subleq
#
# Created by R J Cooper on 10/09/2011.
# Copyright 2011 Mountainstorm. All rights reserved.
#
# debug a memory layout - show where literals and labels are
#

import os
import os.path
import types
import struct
import sys
import subprocess
import pickle
from copy import deepcopy
import subleq


class SubleqDebugger:
	kBlue = "\033[34m"
	kGreen = "\033[32m"
	kRed = "\033[31m"
	kClear = "\033[0m"
	kBold = "\033[1;30m"
	kCls = "\033[2J\033[H"


	def __init__(self, input, pack):	
		self.pack = pack
		self.dbg = None
		self.bps = {}
		self.notes = None
		self.ip = 0

		self.lastAddrs = {}
		self.commands = {
			"h": {
				"brief": "display help on avaliable commands",
				"func": self.cmdHelp
			},
			"q": {
				"brief": "exit the debuggger",
				"func": self.cmdQuit
			},
			"bp": {
				"brief": "add breakpoint <hex-addr>",
				"func": self.cmdBp
			},
			"bc": {
				"brief": "clear breakpoint <hex-addr>",
				"func": self.cmdBc
			},
			"si": {
				"brief": "step instruction - exeecute the currently highlighted microcode instruction",
				"func": self.cmdSi
			},
			"c": {
				"brief": "continue - run until breakpoint hit",
				"func": self.cmdC
			},
			"r": {
				"brief": "restart - restart execution",
				"func": self.cmdR
			},
			"p": {
				"brief": "print [ip|<hex-addr>]|[ip|<hex-addr> <hex-addr>] - print code",
				"func": self.cmdP
			}
		}

		f = file(input, "rb")
		if f:
			self.originalData = f.read()
			f.close()
			dbgFile = os.path.splitext(input)[0] + ".dbg"
			f = file(dbgFile, "rb")
			if f:
				self.dbg = pickle.load(f)
				f.close()
				self.setupDisplay()
				self.setupLabels()
				self.setupLiterals()
				self.setupOffsets()
				self.setupInst()
				self.reset()
					
				self.update(self.ip)
			else:
				print "Unable to open debug info file: %s" % (dbgFile)
		else:
			print "Unable to open file: %s" % (input)


	def color(self, c, str):
		return c + str + SubleqDebugger.kClear


	def getWordSize(self):
		return struct.calcsize(self.pack)


	def getSubleqSize(self):
		return (3 * self.getWordSize())
				
		
	def readData(self):
		retVal = {}
		for i in xrange(0, len(self.originalData), self.getWordSize()):
			retVal[i], = struct.unpack(self.pack, self.code.getString(i, self.getWordSize()))
		return retVal

	
	def setupDisplay(self):
		self.display = {}
		for addr in xrange(0, len(self.originalData), self.getWordSize()):
			self.display[addr] = []
		
		
	def setupLabels(self):
		self.labelWidth = 0
		for label in self.dbg["labels"]:
			str = label + ":"
			self.addDisplayItem(self.dbg["labels"][label], "label", str)
			# calculate the column width
			width = len(str)
			if width > self.labelWidth:
				self.labelWidth = width
	
	def setupLiterals(self):
		for literal in self.dbg["literals"]:
			str = self.color(SubleqDebugger.kBold, "literal %u" % literal)
			self.addDisplayItem(self.dbg["literals"][literal], "note", str)
			
				
	def setupOffsets(self):
		for offset in self.dbg["offsets"]:
			str = self.color(SubleqDebugger.kBold, offset)
			self.addDisplayItem(self.dbg["offsets"][offset], "note", str)
		
	
	def setupInst(self):
		self.addInst(self.dbg["inst"], [])


	def reset(self):
		self.code = subleq.Code(self.originalData)
		self.ip = 0		

		# setup the base address register and dlsym if needed
		for label in self.dbg["labels"]:
			addr = self.dbg["labels"][label]
			if label == "bar":
				self.code.patchBAR(addr)

			if label == "dlsym":
				self.code.patchDlsym(addr)


	def addInst(self, inst, stack):
		for addr in inst:
			if len(inst[addr]["children"]) > 0:
				pad = self.getPad(stack, addr)			
				self.addDisplayItem(addr, 
									"note", 
									 " " + pad + self.color(SubleqDebugger.kBold, inst[addr]["inst"]))
				ns = deepcopy(stack)
				ns.append(inst[addr])
				self.addInst(inst[addr]["children"], ns)
			else:
				pad = self.getPad(stack, addr)
				self.addDisplayItem(addr, "note", self.color(SubleqDebugger.kBlue, "┐") + pad + self.color(SubleqDebugger.kBold, inst[addr]["inst"]))
				pad = self.getPad(stack, addr + self.getWordSize(), self.color(SubleqDebugger.kBlue, "─"))
				self.addDisplayItem(addr + self.getWordSize(), "note", self.color(SubleqDebugger.kBlue, "├") + pad + self.color(SubleqDebugger.kBlue, "─┘"))
				pad = self.getPad(stack, addr + (2 * self.getWordSize()))
				self.addDisplayItem(addr + (2 * self.getWordSize()), "note", self.color(SubleqDebugger.kBlue, "┘") + pad)

		
	def getPad(self, stack, addr, space = " "):
		retVal = ""
		for i in stack:
			if addr >= i["offset"] and addr < (i["offset"] + i["length"] - self.getWordSize()):
				done = False
				if i == stack[-1]:
					j = 0
					for c in sorted(i["children"].keys()):
						if c == addr:
							if j == (len(i["children"]) - 1):
								retVal += space + self.color(SubleqDebugger.kRed, "└ ")
							else:
								retVal += space + self.color(SubleqDebugger.kRed, "├ ")
							done = True
							break
						j += 1
				if not done:
					children = sorted(i["children"].keys())
					if len(children) > 0:
						lastChild = i["children"][children[-1]]
						if addr >= lastChild["offset"] and addr < (lastChild["offset"] + lastChild["length"] - self.getWordSize()):
							retVal += space + space + space
							done = True
					if not done:
						retVal += space + self.color(SubleqDebugger.kRed, "│") + space	
		return retVal


	def addDisplayItem(self, addr, type, value):
		if addr in self.display:
			if len(self.display[addr]) == 0:
				self.display[addr].append({type: value})
			else:
				done = False
				for el in self.display[addr]:
					if type not in el:
						el[type] = value
						done = True
						
				if done == False:	
					self.display[addr].append({type: value}) # add new line
		else:
			print "error: unexpected address: %08x type: %s" % (addr, type)


	def update(self, start, end = None):
		if not end:
			end = len(self.originalData)
		
		addrs = self.readData()
		for addr in sorted(self.display.keys()):
			if addr >= start and addr < end:
				if len(self.display[addr]) == 0:
					self.displayLine("", addrs, addr, True, "")
				else:
					for i in xrange(0, len(self.display[addr])):
						el = self.display[addr][i]
						label = ""
						if "label" in el:
							label = el["label"]
						
						note = ""
						if "note" in el:
							note = el["note"]
						self.displayLine(label, 
										 addrs, 
										 addr, 
										 (i == len(self.display[addr]) - 1), 
										 note)
		self.lastAddrs = deepcopy(addrs)
		
		
	def displayLine(self, label, addrs, addr, displayValue, note):
		labelStr = "".rjust(self.labelWidth - len(label))
		labelStr += self.color(SubleqDebugger.kBold, label)
	
		bp = ":"
		if addr in self.bps:
			bp = self.color(SubleqDebugger.kBlue, "✖")
		
		addrStr = "%08x" % addr
		if self.ip != -1:
			if addr >= self.ip and addr < (self.ip + self.getSubleqSize()):
				addrStr = self.color(SubleqDebugger.kGreen, addrStr)
		
		value = "        "
		if displayValue:
			value = "%08x" % addrs[addr]
			if self.ip != -1:
				if addr >= self.ip and addr < (self.ip + self.getSubleqSize()):
					value = self.color(SubleqDebugger.kGreen, value)
			if addr in self.lastAddrs:
				if self.lastAddrs[addr] != addrs[addr]:
					value = self.color(SubleqDebugger.kRed, "%08x" % addrs[addr])

		print "%s %s %s %s %s" % (labelStr, addrStr, bp, value, note)


	def run(self):
		while True:
			unknown = True
			line = raw_input("sdb> ")

			parts = line.split()
			if len(parts) > 0:
				cmd = parts[0]
				if cmd in self.commands:
					unknown = False
					if self.commands[cmd]["func"](parts) == False:
						print "Failed: " + self.commands[cmd]["brief"]
			if unknown:
				if len(line) > 0:
					print "Unknown command; \"%s\"" % line
					self.cmdHelp(None)
					
	
	def cmdQuit(self, p):
		quit()
				
				
	def cmdHelp(self, p):
		for c in sorted(self.commands.keys()):
			print "  %s : %s" % (c, self.commands[c]["brief"])
		return True


	def cmdBp(self, p):
		retVal = True
		if len(p) == 2:
			self.bps[int(p[1], 16)] = True
			self.update(int(p[1], 16))
			retVal = True
		return retVal


	def cmdBc(self, p):
		retVal = False
		if len(p) == 2:
			del self.bps[int(p[1], 16)] 
			self.update(int(p[1], 16))
			retVal = True
		return retVal


	def cmdSi(self, p):
		oldIp = self.ip
		self.ip = self.code.step(self.ip)
		if self.ip < 0:
			self.update(oldIp)
		else:
			self.update(self.ip)
		if self.ip == -1:
			print "Execution completed"
			

	def cmdC(self, p):
		loop = True
		while loop:
			oldIp = self.ip
			self.ip = self.code.step(self.ip)
			if self.ip < 0:
				self.update(oldIp)
				print "Execution completed"
				loop = False
			else:
				for bp in self.bps:
					if bp >= self.ip and bp < (self.ip + self.getSubleqSize()):
						self.update(self.ip)
						loop = False
						break
		
		
	def cmdR(self, p):
		self.reset()
		self.update(self.ip)		
		
		
	def cmdP(self, p):
		start = self.ip
		end = start + self.getSubleqSize()
		if len(p) == 2:
			if p[1] != "ip":
				start = int(p[1], 16)
			end = len(self.originalData)
		elif len(p) == 3:
			if p[1] != "ip":
				start = int(p[1], 16)
			end = int(p[2], 16)
		self.update(start, end)
	

if __name__ == '__main__':
	argc = len(sys.argv)
	if argc == 2:
		debugger = SubleqDebugger(sys.argv[1], "<i")
		debugger.run()
	else:
		print "Usage: debug.py <input.bin>"
