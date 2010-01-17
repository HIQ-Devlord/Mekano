import cPickle
import re

def loadpickleitems(filename):
    """
    Return a generator that yields each item in a pickled
    file.
    """
    fin = open(filename)
    while(True):
        try:
            r = cPickle.load(fin)
            yield r
        except EOFError:
            fin.close()
            return

def dump(obj, filename):
    """
    Pickle an object to a file
    """
    with open(filename, "w") as fout:
        cPickle.dump(obj, fout, -1)

def load(filename):
    """
    Load a single object from a pickle file.
    """
    with open(filename) as fin:
        return cPickle.load(fin)


class StateMachineFileParser:
    """A state machine based line-oriented parser.

    You should subclass this and implement 'state'
    functions that begin with 'on', for example:

        onStart(self, line)

    Each such function:
      * takes a single argument 'line' which
        contains the next line read from fin.
      * returns the next state to go into, e.g. "End",
        or returns None (i.e. returns nothing) to stay
        in the same state.
      * returns False to terminate further parsing.
    
    To begin parsing, call the parse() function.
    """

    def __init__(self, fin, start = "Start"):
        if not hasattr(fin, "readline"):
            raise Exception("fin must be a file-like object")
        self.__fin = fin
        self.__stateFunctions = {}
        self.start = start

    def __introspect(self):
        """
        Find all functions that begin with 'on' and create
        a map from the rest of their name to the function object.
        """
        for fn in filter(lambda x: x.startswith("on"), dir(self)):
            self.__stateFunctions[fn[2:]] = getattr(self, fn)

    def parse(self):
        self.__introspect()

        state = self.start
        for line in self.__fin:
            fn = self.__stateFunctions[state]
            newstate = fn(line)
            if newstate is False:
                break
            elif newstate is not None:
                state = newstate
        self.onFinish(line)
    
    def onFinish(self, line):
        pass


class TrecParser(StateMachineFileParser):
    """TREC file parser

    tp = TrecParser(fin, callback)

    The callback function receives (docid, text).
    
    If the callback function returns False, further
    parsing is terminated. Not returning anything does not
    constitute returning False!
    """
    
    def __init__(self, fin, callback):
        StateMachineFileParser.__init__(self, fin, "Misc")
        self.docid = None
        self.textlines = []
        self.callback = callback
        
    def onMisc(self, line):
        """Waiting for a new doc to start"""
        if line.startswith("<DOCNO>"):
            p = line.find("<", 7)
            self.docid = line[7:p].strip()
            self.textlines = []
            return "GotDocId"

    def onGotDocId(self, line):
        """Waiting for the TEXT section to start"""
        if line.startswith("<TEXT>"):
            return "Text"

    def onText(self, line):
        """Seeing text lines"""
        if line.startswith("</TEXT>"):
            r = self.callback(self.docid, "".join(self.textlines))
            if r is False:
                return False
            return "Misc"
        else:
            self.textlines.append(line)
    
class SMARTParser(StateMachineFileParser):
    """SMART file parser

    tp = SMARTParser(fin, callback, sections = None)

    The callback function receives (docid, cats, text).
    If the callback function returns False, further
    parsing is terminated. Not returning anything does not
    constitute returning False!
    
    sections:    None          Read all sections.
                 ["T", "W"]    Only read sections .T and .W
    """

    def __init__(self, fin, callback, sections = None):
        StateMachineFileParser.__init__(self, fin, "Misc")
        self.docid = None
        self.cats = None
        self.textlines = []
        self.callback = callback
        self.sectionheader = None
        self.cat_regex = re.compile("([^ ]+) 1")
        self.allowedsections = sections

    def onMisc(self, line):
        """Waiting for a new doc to start"""
        if line.startswith(".I"):
            self.docid = line[2:].strip()
            self.textlines = []
            self.cats = None
            self.sectionheader = None
            return "GotDocId"

    def onGotDocId(self, line):
        """Waiting for the .C section to start"""
        if line.startswith(".C"):
            return "SawDotC"
    
    def onSawDotC(self, line):
        """Reading the categories line"""
        self.cats = [c.group(1) for c in self.cat_regex.finditer(line)]
        return "SectionHeader"
    
    def onSectionHeader(self, line):
        """Reading the section header line"""
        self.sectionheader = line[1:2]
        return "SectionText"

    def onSectionText(self, line):
        """Seeing text lines"""
        if line.startswith("."):
            if line.startswith(".I"):
                self.doCallBack()
                return self.onMisc(line)
            else:
                return self.onSectionHeader(line)
        
        if self.allowedsections is not None and self.sectionheader not in self.allowedsections:
            return None
        
        self.textlines.append(line)
    
    def onFinish(self, line):
        self.doCallBack()
    
    def doCallBack(self):
        if len(self.textlines):
            self.callback(self.docid, self.cats, "".join(self.textlines))
    
