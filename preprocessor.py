from re import findall,sub,search,match
from os.path import exists as fileExists
from os.path import join as pathJoin
from os.path import abspath as pathAbs
from os.path import relpath as pathRelative
from os.path import dirname as pathDir

PATTERN_INCLUDE = r'\s*#include\s+[<\"]([^>\"]*)[>\"]'
PATTERN_DEFINE_VAR = r'\s*#define\s+([A-Za-z0-9_]+)\s*(.+)?'
PATTERN_DEFINE_FUNC = r'\s*#define\s+([A-Za-z0-9_]+)\((.+)\)(\s+(.+))?'
PATTERN_UNDEF = r'\s*#undef\s+([A-Za-z0-9_]+)'
PATTERN_CONDITIONAL = r'\s*#(if|ifdef|else|endif)'
PATTERN_DIRECTIVE = r'\s*#(\w+)'
PATTERN_MACRO_USE = r'([A-Za-z0-9_]+)\s*(\()?'

PATTERN_MACRO_ADDLINE = r'\\\s*$'

PATTERN_COMMENT_LINE = r'\s*//.*'
PATTERN_COMMENT_BLOCK_START = r'\/\*'
PATTERN_COMMENT_BLOCK_END = r'\*\/'

class PreprocessorException(Exception):
	def __init__(self, message,file,line):
		self.message = message
		self.file = file
		self.line = line

class PreprocessorWarning:
	def __init__(self, message,file,line):
		self.message = message
		self.file = file
		self.line = line

class BaseMacro:
	def __init__(self):
		self.locationFile = ""
		self.locationLine = 0
	def setupLocation(self,file,line):
		self.locationFile = file
		self.locationLine = line

class MacroVariable(BaseMacro):
	def __init__(self, name, value,argumentList=None):
		self.name = name
		self.value = value
		self.argumentList = argumentList

	def isFunction(self):
		return self.argumentList is not None
	def isConstVariable(self):
		return self.argumentList is None

class PreprocessorValidator:
	def __init__(self):
		self.exceptions:list[PreprocessorException] = []
		self.warnings:list[PreprocessorWarning] = []
	
	def isValid(self):
		return len(self.exceptions) == 0

class FilePreprocessor:

	def __init__(self, filename,parentFiles = None):
		self.filename = pathAbs(filename)
		with open(self.filename,'r',encoding='utf-8') as f:
			self.code = f.read()

		self.includes = set()
	
		self.parentFiles = parentFiles if parentFiles is not None else []

		self.macro_vars:dict[str, MacroVariable] = dict()

		self.parent_vars:dict[str, MacroVariable] = dict()

		self.ppv:PreprocessorValidator = None
		
		self.curpos = 0
		self.all_lines = []

	@property
	def curline(self):
		return self.curpos + 1

	def validate(self) -> PreprocessorValidator:
		pv = PreprocessorValidator()
		self.validateCode(pv)
		return pv
	
	def validateCode(self, pv:PreprocessorValidator):
		self.ppv = pv
		lines = self.code.split('\n')
		self.all_lines = lines
		
		self.curpos = 0

		inBlockComment = False

		while self.curpos < len(lines):
			line = lines[self.curpos]
			

			if not inBlockComment and match(PATTERN_COMMENT_BLOCK_START,line):
				inBlockComment = True
			if inBlockComment and match(PATTERN_COMMENT_BLOCK_END,line):
				inBlockComment = False
			
			if inBlockComment:
				self.curpos += 1
				continue

			if match(PATTERN_COMMENT_LINE,line):
				pass
			elif match(PATTERN_INCLUDE,line):
				self.handleInclude(line)
			elif match(PATTERN_DEFINE_FUNC,line):
				self.handleDefineFunc(line)
			elif match(PATTERN_DEFINE_VAR,line):
				self.handleDefineVar(line)
			elif match(PATTERN_UNDEF,line):
				self.handleUndef(line)
			elif match(PATTERN_CONDITIONAL,line):
				pass # conditional directives no throws errors
			elif match(PATTERN_DIRECTIVE,line):
				self.handleDirective(line)
			elif match(PATTERN_MACRO_USE,line):
				self.handleMacroUse(line)
			self.curpos += 1

		self.ppv = None
	
	def handleDirective(self, line):
		dirName = match(PATTERN_DIRECTIVE,line).group(1)
		self.ppv.exceptions.append(PreprocessorException(f'Directive error: Unknown directive "{dirName}"',self.filename,self.curline))
		pass

	def handleInclude(self, line):
		pathIncl = match(PATTERN_INCLUDE,line).group(1)

		inclPathAbs = pathAbs( pathJoin(pathDir(self.filename),pathIncl) )
		if not fileExists(inclPathAbs):
			self.ppv.exceptions.append(PreprocessorException(f'Include error: File "{inclPathAbs}" not found',self.filename,self.curline))
			return
		
		if inclPathAbs in self.parentFiles:
			self.ppv.warnings.append(PreprocessorWarning(f'Include warning: File "{inclPathAbs}" already included',self.filename,self.curline))
			return

		pp = FilePreprocessor(inclPathAbs,self.parentFiles + [self.filename])
		pp.parent_vars = self.macro_vars
		vld = pp.validate()
		
		#todo optional enable for extended logging
		self.ppv.exceptions.extend(vld.exceptions)
		self.ppv.warnings.extend(vld.warnings)

		if not vld.isValid():
			self.ppv.exceptions.append(PreprocessorException(f'Include error: File "{inclPathAbs}" invalid content',self.filename,self.curline))
			return

		self.includes.add(inclPathAbs)
		pp.applyPreprocInfoFor(self)

		pass
	def handleDefineFunc(self, line):
		grp = match(PATTERN_DEFINE_FUNC,line)# 1,2,4 -> name,args,value
		mfnc = MacroVariable(grp.group(1),grp.group(4),findall(r"\w+",grp.group(2)))
		mfnc.setupLocation(self.filename,self.curline)
		redefined = False
		if mfnc.name in self.macro_vars:
			redefined = True
			self.ppv.warnings.append(PreprocessorWarning(
				f'Define warning: Macro "{mfnc.name}" already defined in "{self.macro_vars[mfnc.name].locationFile}"'
				,self.filename,self.curline))
		if mfnc.name in self.parent_vars:
			redefined = True
			self.ppv.warnings.append(PreprocessorWarning(
				f'Define warning: Macro "{mfnc.name}" already defined in "{self.parent_vars[mfnc.name].locationFile}"'
				,self.filename,self.curline
			))

		self.macro_vars[mfnc.name] = mfnc
		pass
	def handleDefineVar(self, line):
		grp = match(PATTERN_DEFINE_VAR,line)
		mfnc = MacroVariable(grp.group(1),grp.group(2) or "")
		mfnc.setupLocation(self.filename,self.curline)
		redefined = False
		if mfnc.name in self.macro_vars:
			redefined = True
			self.ppv.warnings.append(PreprocessorWarning(
				f'Define warning: Macro "{mfnc.name}" already defined in "{self.macro_vars[mfnc.name].locationFile}"'
				,self.filename,self.curline
			))
		if mfnc.name in self.parent_vars:
			redefined = True
			self.ppv.warnings.append(PreprocessorWarning(
				f'Define warning: Macro "{mfnc.name}" already defined in "{self.parent_vars[mfnc.name].locationFile}"'
				,self.filename,self.curline
			))

		self.macro_vars[mfnc.name] = mfnc
		pass

	def handleUndef(self, line):
		grp = match(PATTERN_UNDEF,line)
		macroName = grp.group(1)
		foundUndef = False
		if macroName in self.macro_vars or macroName in self.parent_vars:
			if macroName in self.macro_vars:
				foundUndef = True
				self.macro_vars.pop(macroName)
			if macroName in self.parent_vars:
				foundUndef = True
				self.parent_vars.pop(macroName)
		if not foundUndef:
			self.ppv.warnings.append(PreprocessorWarning(
				f'Undef warning: Macro "{macroName}" not defined'
				,self.filename,self.curline
			))

	def handleMacroUse(self, line):
		grp = match(PATTERN_MACRO_USE,line)
		macroName = grp.group(1)
		self._resolveMacro()

	def _resolveMacro(self):
		
		curl = self.all_lines[self.curpos]
		content = curl
		baseline = self.curpos
		while match(PATTERN_MACRO_ADDLINE,curl):
			self.curpos += 1
			curl = self.all_lines[self.curpos]
			content += curl

		pat_int_muse = r'([A-Za-z0-9_]+)\(([^\(\)]*)\)'

		#find functions
		while match(pat_int_muse,content):
			grp = match(pat_int_muse,content)
			name=grp.group(1)
			args=grp.group(2)
			pmacr = self.getMacro(name)
			if pmacr is None:
				self.ppv.exceptions.append(PreprocessorException(f'Macro "{name}" not defined',self.filename,self.curline))
				return
			if not pmacr.isFunction():
				self.ppv.exceptions.append(PreprocessorException(f'Macro "{name}" is not a function',self.filename,self.curline))
				return
			argvals = args.split(',')
			if len(argvals) != len(pmacr.argumentList):
				self.ppv.exceptions.append(PreprocessorException(f'Wrong number of arguments for macro "{name}" ({len(argvals)} instead of {len(pmacr.argumentList)})',self.filename,self.curline))
				return
			content = content.replace(grp.group(0),"$__REPLACED__$")
		
		#find vars
		while match(r'([A-Za-z0-9_]+)(\(?)',content):
			grp = match(r'([A-Za-z0-9_]+)(\(?)',content)
			name = grp.group(1)
			hasOpenBracket = grp.group(2)
			pmacr = self.getMacro(name)
			if pmacr:
				if pmacr.isConstVariable() and hasOpenBracket:
					self.ppv.exceptions.append(PreprocessorException(f'Macro "{name}" is not a function',self.filename,self.curline))
					return
				if pmacr.isFunction() and not hasOpenBracket:
					self.ppv.exceptions.append(PreprocessorException(f'Macro "{name}" missing brackets',self.filename,self.curline))
			content = content.replace(grp.group(0),'$__REPLACED__$')

	def getMacro(self,defname):
		if defname in self.macro_vars:
			return self.macro_vars[defname]
		if defname in self.parent_vars:
			return self.parent_vars[defname]
		return None

	def applyPreprocInfoFor(self,caller):
		caller.macro_vars.update(self.macro_vars)
		caller.includes.update(self.includes)

if __name__ == '__main__':
	pp = FilePreprocessor('test/test.sqf')

	pv = pp.validate()

	for wrn in pv.warnings:
		print(f"[WARNING]: {wrn.message} (file: {wrn.file} at {wrn.line})")

	for ex in pv.exceptions:
		print(f"[ERROR]: {ex.message} (file: {ex.file} at {ex.line})")

