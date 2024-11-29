from re import findall,sub,search,match
from os.path import exists as fileExists
from os.path import join as pathJoin
from os.path import abspath as pathAbs
from os.path import relpath as pathRelative
from os.path import dirname as pathDir

PATTERN_INCLUDE = r'\s*#include\s+[<\"]([^>\"]*)[>\"]'
PATTERN_DEFINE_VAR = r'\s*#define\s+([A-Za-z0-9_]+)(\s+(.+))?'
PATTERN_DEFINE_FUNC = r'\s*#define\s+([A-Za-z0-9_]+)\((.+)\)(\s+(.+))?'
PATTERN_CONDITIONAL = r'\s*#(if|ifdef|else|endif|undef)'
PATTERN_DIRECTIVE = r'\s*#(\w+)'

PATTERN_COMMENT_LINE = r'\s*//.*'
PATTERN_COMMENT_BLOCK_START = r'\/*'
PATTERN_COMMENT_BLOCK_END = r'*/'

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

			# if inBlockComment:
			# 	if match(PATTERN_COMMENT_BLOCK_END,line):
			# 		inBlockComment = False
			# 	else:
			# 		self.curpos += 1
			# 		continue

			# if not inBlockComment and match(PATTERN_COMMENT_BLOCK_START,line):
			# 	inBlockComment = True

			if match(PATTERN_COMMENT_LINE,line):
				pass
			elif match(PATTERN_INCLUDE,line):
				self.handleInclude(line)
			elif match(PATTERN_DEFINE_VAR,line):
				self.handleDefineVar(line)
			elif match(PATTERN_DEFINE_FUNC,line):
				self.handleDefineFunc(line)
			elif match(PATTERN_CONDITIONAL,line):
				pass # conditional directives no throws errors
			elif match(PATTERN_DIRECTIVE,line):
				self.handleDirective(line)
			self.curpos += 1

		self.ppv = None
	
	def handleDirective(self, line):
		dirName = match(PATTERN_DIRECTIVE,line).group(1)
		self.ppv.exceptions.append(PreprocessorException(f'Directive error: Unknown directive "{dirName}" (included from "{self.filename}" at line {self.curline})',self.filename,self.curline))
		pass

	def handleInclude(self, line):
		pathIncl = match(PATTERN_INCLUDE,line).group(1)

		inclPathAbs = pathAbs( pathJoin(pathDir(self.filename),pathIncl) )
		if not fileExists(inclPathAbs):
			self.ppv.exceptions.append(PreprocessorException(f'Include error: File "{inclPathAbs}" not found (included from "{self.filename}" at line {self.curline})',self.filename,self.curline))
			return
		
		if inclPathAbs in self.parentFiles:
			self.ppv.warnings.append(PreprocessorWarning(f'Include warning: File "{inclPathAbs}" already included (included from "{self.filename}" at line {self.curline})',self.filename,self.curline))
			return

		pp = FilePreprocessor(inclPathAbs,self.parentFiles + [self.filename])
		vld = pp.validate()
		
		#todo optional enable for extended logging
		self.ppv.exceptions.extend(vld.exceptions)
		self.ppv.warnings.extend(vld.warnings)

		if not vld.isValid():
			self.ppv.exceptions.append(PreprocessorException(f'Include error: File "{inclPathAbs}" invalid content (included from "{self.filename}" at line {self.curline})',self.filename,self.curline))
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
				f'Define warning: Macro "{mfnc.name}" already defined in "{self.macro_vars[mfnc.name].locationFile}" (included from "{self.filename}" at line {self.curline})'
				,self.filename,self.curline))

		self.macro_vars[mfnc.name] = mfnc
		pass
	def handleDefineVar(self, line):
		pass

	def applyPreprocInfoFor(self,caller):
		caller.macro_vars.update(self.macro_vars)
		caller.includes.update(self.includes)

if __name__ == '__main__':
	pp = FilePreprocessor('test/test.sqf')

	pv = pp.validate()

	for wrn in pv.warnings:
		print(wrn.message)

	for ex in pv.exceptions:
		print(ex.message)

