#!/usr/bin/env python
# coding:utf-8

"Integrated Styled Text Editor for Python"

# Based on wx examples, SPE & picalo implementations

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


import codecs
import locale
import os
import re
import inspect
import keyword
import types

import wx
import wx.stc as stc
import wx.py

import images

# Some configuration constants 
WORDCHARS = "_.abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
FACES = {'times': 'DejaVu Sans', 'mono': 'DejaVu Sans Mono', 
         'helv' : 'DejaVu Serif', 'other': 'DejaVu',
         'size' : 10, 'size2': 8}
CALLTIPS = True # False or 'first paragraph only'     
AUTOCOMPLETE = True
AUTOCOMPLETE_IGNORE = []
PY_CODING_RE = re.compile(r'coding[:=]\s*([-\w.]+)')


def getargspec(func):
    """Get argument specifications (for CallTip)"""
    try:
        func=func.im_func
    except:
        pass
    try:
        return inspect.formatargspec(*inspect.getargspec(func)).replace('self, ','')+'\n\n'
    except:
        pass
    try:
        return inspect.formatargvalues(*inspect.getargvalues(func)).replace('self, ','')+'\n\n'
    except:
        return ''


class EditorCtrl(stc.StyledTextCtrl):
    "Editor based on Styled Text Control"

    CURRENT_LINE_MARKER_NUM = 2
    BREAKPOINT_MARKER_NUM = 1
    CURRENT_LINE_MARKER_MASK = 0x4
    BREAKPOINT_MARKER_MASK = 0x2
   
    def __init__(self, parent, ID,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=0, filename=None, debugger=None, cfg={},
                 lang="python", cfg_styles={}):
        global TAB_WIDTH, IDENTATION, CALLTIPS, AUTOCOMPLETE, FACES

        stc.StyledTextCtrl.__init__(self, parent, ID, pos, size, style)

        # read configuration
        TAB_WIDTH = cfg.get("tab_width", 4)
        USE_TABS = cfg.get('use_tabs', False)
        IDENTATION = " " * TAB_WIDTH
        EDGE_COLUMN = cfg.get("edge_column", 79)
        ENCODING = cfg.get("encoding", "utf_8")
        CALLTIPS = cfg.get("calltips", True)
        AUTOCOMPLETE = cfg.get("autocomplete", False)
        VIEW_WHITESPACE = cfg.get('view_white_space', False)
        VIEW_EOL = cfg.get('view_eol', False)
        self.eol = EOL_MODE = cfg.get('eol_mode', stc.STC_EOL_CRLF)
        
        for key, default in FACES.items():
            value = cfg.get("face_%s" % key, default)
            if key in ("size", "size2"):
                value = int(value)
            FACES[key] = value

        # internal settings
        self.parent = parent
        self.debugger = debugger
        self.filename = filename
        self.modified = False
        self.calltip = 0
        self.namespace = {}
        # default encoding and BOM (pep263, prevent syntax error  on new fieles)
        self.encoding = ENCODING 
        self.bom = codecs.BOM_UTF8

        self.CmdKeyAssign(ord('B'), stc.STC_SCMOD_CTRL, stc.STC_CMD_ZOOMIN)
        self.CmdKeyAssign(ord('N'), stc.STC_SCMOD_CTRL, stc.STC_CMD_ZOOMOUT)

        self.SetLexer(stc.STC_LEX_PYTHON)
        keywords=keyword.kwlist
        keywords.extend(['None','as','True','False'])
        self.SetKeyWords(0, " ".join(keywords))
        self.AutoCompSetIgnoreCase(False)

        self.SetViewWhiteSpace(VIEW_WHITESPACE)
        #self.SetBufferedDraw(False)
        self.SetViewEOL(VIEW_EOL)
        self.SetEOLMode(EOL_MODE)
        self.SetCodePage(wx.stc.STC_CP_UTF8)
        self.SetUseAntiAliasing(True)
        self.SetTabWidth(TAB_WIDTH)
        self.SetIndentationGuides(True)
        self.SetUseTabs(USE_TABS)
        if EDGE_COLUMN:
            self.SetEdgeMode(stc.STC_EDGE_LINE)
            self.SetEdgeColumn(EDGE_COLUMN)
            self.SetEdgeColour(wx.Colour(200,200,200))
        self.SetWordChars(WORDCHARS)
        self.SetBackSpaceUnIndents(1)

        #MARGINS
        self.SetMargins(0,0)

        # margin 0 for breakpoints
        self.SetMarginSensitive(0, True)
        self.SetMarginType(0, wx.stc.STC_MARGIN_SYMBOL)
        self.SetMarginMask(0, 0x3)
        self.SetMarginWidth(0, 12)
        # margin 1 for current line arrow
        self.SetMarginSensitive(1, False)
        self.SetMarginMask(1, 0x4)
        # margin 2 for line numbers
        self.SetMarginType(2, stc.STC_MARGIN_NUMBER)
        self.SetMarginWidth(2, 28)
        # margin 3 for markers (folding)
        self.SetMarginType(3, stc.STC_MARGIN_SYMBOL)
        self.SetMarginMask(3, stc.STC_MASK_FOLDERS)
        self.SetMarginSensitive(3, True)
        self.SetMarginWidth(3, 12)
        
        #FOLDING
        self.SetProperty("fold", "1")
        self.SetProperty("tab.timmy.whinge.level", "1")
        self.SetProperty("fold.comment.python", "0")
        self.SetProperty("fold.quotes.python", "0")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDEROPEN, stc.STC_MARK_BOXMINUS, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDER, stc.STC_MARK_BOXPLUS, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDERSUB, stc.STC_MARK_VLINE, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDERTAIL, stc.STC_MARK_LCORNER, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDEREND, stc.STC_MARK_BOXPLUSCONNECTED, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDEROPENMID, stc.STC_MARK_BOXMINUSCONNECTED, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDERMIDTAIL, stc.STC_MARK_TCORNER, "white", "#808080")

        # Define the current line marker
        self.MarkerDefine(self.CURRENT_LINE_MARKER_NUM, wx.stc.STC_MARK_SHORTARROW, wx.BLACK, (255,255,128))
        # Define the breakpoint marker
        self.MarkerDefine(self.BREAKPOINT_MARKER_NUM, wx.stc.STC_MARK_CIRCLE, wx.BLACK, (255,0,0))
        

        # Make some styles,  The lexer defines what each style is used for, we
        # just have to define what each style looks like.  This set is adapted from
        # Scintilla sample property files.       
        self.SetStyles(lang, cfg_styles)

        self.SetCaretForeground("BLUE")


        # register some images for use in the AutoComplete box.
        self.RegisterImage(1, 
            wx.ArtProvider.GetBitmap(wx.ART_FOLDER, size=(16,16))
            )
        self.RegisterImage(2, 
            wx.ArtProvider.GetBitmap(wx.ART_NEW, size=(16,16)))
        self.RegisterImage(3, 
            wx.ArtProvider.GetBitmap(wx.ART_COPY, size=(16,16)))

        self.Bind(wx.EVT_MENU, self.OnSave, id = wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self.OnSaveAs, id = wx.ID_SAVEAS)

        self.Bind(stc.EVT_STC_UPDATEUI, self.OnUpdateUI)
        self.Bind(stc.EVT_STC_MARGINCLICK, self.OnMarginClick)
        self.Bind(wx.stc.EVT_STC_CHANGE, self.OnChange)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_CHAR, self.OnChar)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)       

        self.Bind(wx.EVT_FIND, self.OnFindReplace)
        self.Bind(wx.EVT_FIND_NEXT, self.OnFindReplace)
        self.Bind(wx.EVT_FIND_REPLACE, self.OnFindReplace)
        self.Bind(wx.EVT_FIND_REPLACE_ALL, self.OnReplaceAll)
        self.Bind(wx.EVT_FIND_CLOSE, self.OnFindClose)

        menu_handlers = [
            (wx.ID_FIND, self.OnFindReplace),
            (wx.ID_REPLACE, self.DoReplace),
            #(wx.ID_CUT, self.OnCut),
            #(wx.ID_COPY, self.OnCopy),
            #(wx.ID_PASTE, self.OnPaste),
        ]
        for menu_id, handler in menu_handlers:
            self.Bind(wx.EVT_MENU, handler, id=menu_id)
      

        # key bindings (shortcuts). TODO: configuration
        accels = [
                    #(wx.ACCEL_ALT,  ord('X'), wx.Newid()),
                    (wx.ACCEL_CTRL, ord('G'), wx.NewId(), self.DoGoto),
                    (wx.ACCEL_CTRL, ord('F'), wx.NewId(), self.DoFind),
                    (wx.ACCEL_CTRL, ord('H'), wx.NewId(), self.DoReplace),
                    (wx.ACCEL_NORMAL, wx.WXK_F3, wx.NewId(), self.OnFindForward),
                    (wx.ACCEL_SHIFT, wx.WXK_F3, wx.NewId(), self.OnFindReverse),
                    #(wx.ACCEL_NORMAL, wx.WXK_F9, wx.Newid()),
                ]
        atable = wx.AcceleratorTable([acc[0:3] for acc in accels])
        for acc in accels:
            self.Bind(wx.EVT_MENU, acc[3], id=acc[2])
        self.SetAcceleratorTable(atable)

        self.finddlg = None
        
        self.OnOpen()
        self.SetFocus()

    def SetStyles(self, lang='python', cfg_styles={}):
        self.StyleClearAll()

        #INDICATOR STYLES FOR ERRORS
        self.IndicatorSetStyle(0, stc.STC_INDIC_SQUIGGLE)
        self.IndicatorSetForeground(0, wx.RED)

        # INDICATOR STYLES FOR SELECTION (FIND/REPLACE)
        self.IndicatorSetStyle(1, stc.STC_INDIC_BOX) #ROUNDBOX
        self.IndicatorSetForeground(1, wx.Colour(0xFF, 0xA5, 0x00))
        
        # read configuration
        for key, value in cfg_styles.items():
            self.StyleSetSpec(eval("stc.%s" % key.upper()), value % FACES)

    def LoadFile(self, filename, encoding=None):
        "Replace STC.LoadFile for non-unicode files and BOM support"
        start = 0
        f = open(filename, "Ur")
        # detect encoding
        sniff = f.read(240)
        match = PY_CODING_RE.search(sniff)
        if match:
            encoding = match.group(1)
        # First 2 to 4 bytes are BOM?
        boms = (codecs.BOM, codecs.BOM_BE, codecs.BOM_LE, codecs.BOM_UTF8, 
                codecs.BOM_UTF16, codecs.BOM_UTF16_BE, codecs.BOM_UTF16_LE,
                codecs.BOM_UTF32, codecs.BOM_UTF32_BE, codecs.BOM_UTF32_LE)
        encodings = ("utf_16", "utf_16_be", "utf_16_le", "utf_8", 
                     "utf_16", "utf_16_be", "utf_16_le", None, None, None)                    
        for i, bom in enumerate(boms):
            if sniff[:len(bom)] == bom:
                encoding = encodings[i]
                start = len(bom)
                self.bom = bom
                break
        else:
            # no BOM found, use to platform default if no encoding specified
            if not encoding:
                encoding = locale.getpreferredencoding()
            self.bom = None

        if not encoding:
            raise RuntimeError("Unsupported encoding!")

        # detect line endings ['CRLF', 'CR', 'LF'][self.eol]
        line = f.readline()
        if f.newlines:
            self.eol = {'\r\n': stc.STC_EOL_CRLF, '\n\r': stc.STC_EOL_CRLF,
                        '\r': wx.stc.STC_EOL_CR, 
                        '\n': stc.STC_EOL_LF}[f.newlines]
            self.SetEOLMode(self.eol)
            
        # rewin and load text
        f.seek(start)
        self.SetText(f.read().decode(encoding))
        f.close()
        self.encoding = encoding 


    def SaveFile(self, filename, encoding=None):
        f = open(filename, "wb")
        if self.bom:
            # preserve Byte-Order-Mark
            f.write(self.bom)
        f.write(self.GetText().encode(self.encoding))
        f.close()
        self.parent.NotifyRepo(self.filename, action="saved", status="")

    def OnOpen(self, event=None):
        if self.filename:
            self.LoadFile(self.filename)
            self.modified = False
            self.filetimestamp = os.stat(self.filename).st_mtime
            self.SetTitle()

    def SetTitle(self):
        if self.filename:
            title = os.path.basename(self.filename)
        else:
            title = "New"
        if self.modified:
            title += " *" 
        self.parent.SetTitle(title)

    def OnChange(self, event=None):
        if not self.modified:
            self.modified = True
            self.SetTitle()

    def OnFocus(self, event=None):
        # check for data changes
        if self.filename and self.filetimestamp != None:
          if self.filetimestamp != os.stat(self.filename).st_mtime:
            self.filetimestamp = os.stat(self.filename).st_mtime
            if wx.MessageBox('The content of this file has changed on disk.  You might be changing it in another editor.  Would you like to synchronize the text here with the file on disk?', 'Content Changed', style=wx.YES_NO) == wx.YES:
              self.OnOpen()
        event.Skip()

    def GetCodeObject(self):
        '''Retrieves the code object created from this script'''
        # required by compile
        text = self.GetText()
        if isinstance(text, unicode):
            text = text.encode("utf8")
        text = text.rstrip().replace('\r\n','\n')+'\n'
        try:
            return compile(text, self.filename or '<script>', 'exec')
        except Exception, e:
            offset = e.offset or 0  # sometimes these are None
            lineno = e.lineno or 0
            wx.MessageBox('You have a syntax error on line' + ' ' + str(lineno) + ', ' + 'column' + ' ' + str(offset) + '.', 'Syntax Error')
            self.parent.NotifyDefect(description=str(e), type="20", filename=self.filename, lineno=lineno, offset=offset)
            return None      

    def DoGoto(self, evt):
        dlg = wx.TextEntryDialog(
                self, 'Insert line number, or regex expression:',
                'Goto Line/Regex', '')
        if dlg.ShowModal() == wx.ID_OK:
            text = dlg.GetValue()
            if text.isdigit():
                pos = self.PositionFromLine(int(text)-1)
            else:
                # use STC regex (not standard!)
                text = "\<" + text.replace(" ", "[ \t]*") 
                start, end = 0,  self.GetLength()
                mode = wx.stc.STC_FIND_WHOLEWORD | wx.stc.STC_FIND_MATCHCASE | \
                       wx.stc.STC_FIND_REGEXP
                pos = int(self.FindText(start, end, text, mode))
            if pos>=0:
                self.GotoPos(pos)
        dlg.Destroy()


    def GotoLineOffset(self, lineno, offset):
        self.GotoPos(self.PositionFromLine(lineno-1) + offset - 1)
    
    def OnSave(self, event=None):
        if self.filename:
            self.SaveFile(self.filename)
            self.modified = False
            self.filetimestamp = os.stat(self.filename).st_mtime
            self.SetTitle()
            self.GetCodeObject()
            return wx.OK
        else:
            return self.OnSaveAs(event)
        
        
    def OnSaveAs(self, event=None):
        dlg = wx.FileDialog(self, message='Save Script As...', 
                defaultDir=os.getcwd(), defaultFile="", 
                style=wx.SAVE | wx.CHANGE_DIR | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            self.filename = dlg.GetPath()
            filepath, ext = os.path.splitext(self.filename)
            if ext.lower() != '.py':
               self.filename += '.py'
            self.SaveFile(self.filename.replace('\\', '\\\\'))
            self.SetTitle()
            self.filetimestamp = os.stat(self.filename).st_mtime
            self.modified = False
            return wx.OK
        return wx.CANCEL

    def OnKeyDown(self, event):
        key = event.GetKeyCode()
        control = event.ControlDown()
        #shift=event.ShiftDown()
        alt = event.AltDown()
        if key == wx.WXK_RETURN and not control and not alt and not self.AutoCompActive():
            #auto-indentation
            if self.CallTipActive():
                self.CallTipCancel()
                self.calltip = 0
            line = self.GetCurrentLine()
            txt = self.GetLine(line)
            pos = self.GetCurrentPos()
            linepos = self.PositionFromLine(line)
            self.CmdKeyExecute(stc.STC_CMD_NEWLINE)
            indent = self.GetLineIndentation(line)
            padding = IDENTATION * (indent/max(1, TAB_WIDTH))
            newpos = self.GetCurrentPos()
            # smart indentation
            stripped = txt[:pos-linepos].split('#')[0].strip()
            firstword = stripped.split(" ")[0]
            if stripped and self.NeedsIndent(firstword,lastchar=stripped[-1]):
                padding += IDENTATION
            elif self.NeedsDedent(firstword):
                padding = padding[:-TAB_WIDTH]
            self.InsertText(newpos, padding)
            newpos  += len(padding)
            self.SetCurrentPos(newpos)
            self.SetSelection(newpos, newpos)
        else:
            event.Skip()

    def NeedsIndent(self,firstword,lastchar):
        "Tests if a line needs extra indenting, ie if, while, def, etc "
        # remove trailing : on token
        if len(firstword) > 0:
            if firstword[-1] == ":":
                firstword = firstword[:-1]
        # control flow keywords
        if firstword in ["for","if", "else", "def","class","elif","while",
              "try","except","finally",] and lastchar == ':':
            return True
        else:
            return False

    def NeedsDedent(self,firstword):
        "Tests if a line needs extra dedenting, ie break, return, etc "
        # control flow keywords
        if firstword in ["break","return","continue","yield","raise"]:
            return True
        else:
            return False

    def OnChar(self,event):
        key = event.GetKeyCode()
        control = event.ControlDown()
        alt = event.AltDown()
        # GF We avoid an error while evaluating chr(key), next line.
        if key > 255 or key < 0:
            event.Skip()
        elif alt and chr(key) == "3":  
            self.ToggleComment()
        # GF No keyboard needs control or alt to make '(', ')' or '.'
        # GF Shift is not included as it is needed in some keyboards.
        elif chr(key) in ['(',')','.'] and not control and not alt:
            if key == ord('(') and CALLTIPS:
                # ( start tips
                if self.CallTipActive():
                    self.calltip += 1
                    self.AddText('(')
                else:
                    self.ShowCallTip('(')
            elif key == ord(')'):
                # ) end tips
                self.AddText(')')
                if self.calltip:
                    self.calltip -= 1
                    if not self.calltip:
                        self.CallTipCancel()
            elif key == ord('.') and AUTOCOMPLETE:
                # . Code completion
                self.AutoComplete(obj=1)
            else:
                event.Skip()
        else:
            event.Skip()

    def GetWord(self,whole=None):
        for delta in (0,-1,1):
            word    = self._GetWord(whole=whole,delta=delta)
            if word: return word
        return ''

    def _GetWord(self,whole=None,delta=0):
        pos = self.GetCurrentPos()+delta
        line = self.GetCurrentLine()
        linepos = self.PositionFromLine(line)
        txt = self.GetLine(line)
        start = self.WordStartPosition(pos,1)
        if whole:
            end = self.WordEndPosition(pos,1)
        else:
            end = pos
        return txt[start-linepos:end-linepos]

    def GetWords(self,word=None,whole=None):
        if not word: word = self.GetWord(whole=whole)
        if not word:
            return []
        else:
            return list(set([x for x 
                in re.findall(r"\b" + word + r"\w*\b", self.GetText())
                if x.find(',')==-1 and x[0]!= ' ']))

    def GetWordObject(self,word=None,whole=None):
        if not word: word=self.GetWord(whole=whole)
        try:
            obj = self.Evaluate(word)
            return obj
        except:
            return None

    def GetWordFileName(self,whole=None):
        wordlist=self.GetWord(whole=whole).split('.')
        wordlist.append('')
        index=1
        n=len(wordlist)
        while index<n:
            word='.'.join(wordlist[:-index])
            try:
                filename = self.GetWordObject(word=word).__file__
                filename = replace('.pyc','.py').replace('.pyo','.py')
                if os.path.exists(filename):
                    return filename
            except:
                pass
            index+=1
        return '"%s.py"'%'.'.join(wordList[:-1])

    def Evaluate(self, word):
        if word in self.namespace.keys():return self.namespace[word]
        try:
            self.namespace[word] = eval(word,self.namespace)
            return self.namespace[word]
        except:
            if word in AUTOCOMPLETE_IGNORE:
                return None
            else:
                try:
                    components = word.split('.')
                    try:
                        mod= __import__(word)
                    except:
                        if len(components) < 2:
                            return None
                        mod = '.'.join(components[:-1])
                        try:
                            mod= __import__(mod)
                        except:
                            return None
                    for comp in components[1:]:
                        mod = getattr(mod, comp)
                    self.namespace[word]=mod
                    return mod
                except:
                    return None

    def AutoComplete(self, obj=0):
        word    = self.GetWord()
        if not word:
            if obj:
                self.AddText('.')
            return
        if obj:
            self.AddText('.')
            word+='.'
        words   = self.GetWords(word=word)
        for dot in range(len(word)):
            if word[-dot-1] == '.':
                try:
                    obj = self.GetWordObject(word[:-dot-1])
                    if obj:
                        for attr in dir(obj):
                            #attr = '%s%s'%(word[:-dot],attr)
                            attr = '%s%s'%(word,attr)
                            if attr not in words: words.append(attr)
                except:
                    pass
                break
        if words:
            words.sort()
            try:
                self.AutoCompShow(len(word), " ".join(words))
            except:
                pass

    def ShowCallTip(self,text=''):
        #prepare
        obj = self.GetWordObject()
        self.AddText(text)
        if not obj: return
        #classes, methods & functions
        if type(obj) in [types.ClassType,types.TypeType] and hasattr(obj,'__init__'):
            init = obj.__init__
            tip = getargspec(init).strip()
            if tip in ['(self, *args, **kwargs)','(*args, **kwargs)']:
                tip = ""
            else:
                tip = "%s\n"%tip
            doci = init.__doc__
            if doci:
                doc = '%s\n'%(doci.strip())
            else:
                doc = ""
            tip = getargspec(init)
        else:
            doc = ""
            tip = getargspec(obj)
        #normal docstring
        _doc = obj.__doc__
        #compose
        if _doc: doc += _doc
        if doc:
            if CALLTIPS == 'first paragraph only':
                tip += doc.split('\n')[0]
            else:
                tip += doc
        if tip:
            pos = self.GetCurrentPos()
            self.calltip  = 1
            tip+='\n(Press ESC to close)'
            self.CallTipSetBackground('#FFFFE1')
            self.CallTipShow(pos, tip.replace('\r\n','\n'))

    def OnUpdateUI(self, evt):
        # check for matching braces
        braceatcaret = -1
        braceopposite = -1
        charbefore = None
        caretpos = self.GetCurrentPos()

        if caretpos > 0:
            charbefore = self.GetCharAt(caretpos - 1)
            stylebefore = self.GetStyleAt(caretpos - 1)

        # check before
        if charbefore and chr(charbefore) in "[]{}()" and stylebefore == stc.STC_P_OPERATOR:
            braceatcaret = caretpos - 1

        # check after
        if braceatcaret < 0:
            charafter = self.GetCharAt(caretpos)
            styleafter = self.GetStyleAt(caretpos)

            if charafter and chr(charafter) in "[]{}()" and styleafter == stc.STC_P_OPERATOR:
                braceatcaret = caretpos

        if braceatcaret >= 0:
            braceopposite = self.BraceMatch(braceatcaret)

        if braceatcaret != -1  and braceopposite == -1:
            self.BraceBadLight(braceatcaret)
        else:
            self.BraceHighlight(braceatcaret, braceopposite)
            #pt = self.PointFromPosition(braceOpposite)
            #self.Refresh(True, wxRect(pt.x, pt.y, 5,5))
            #print pt
            #self.Refresh(False)

    def OnMarginClick(self, evt):
        # fold and unfold as needed
        lineclicked = self.LineFromPosition(evt.GetPosition())
        if evt.GetMargin() == 0:
            self.ToggleBreakpoint(lineclicked)
        elif evt.GetMargin() == 2:
            if evt.GetShift() and evt.GetControl():
                self.FoldAll()
            else:
                lineclicked = self.LineFromPosition(evt.GetPosition())

                if self.GetFoldLevel(lineclicked) & stc.STC_FOLDLEVELHEADERFLAG:
                    if evt.GetShift():
                        self.SetFoldExpanded(lineclicked, True)
                        self.Expand(lineclicked, True, True, 1)
                    elif evt.GetControl():
                        if self.GetFoldExpanded(lineclicked):
                            self.SetFoldExpanded(lineclicked, False)
                            self.Expand(lineclicked, False, True, 0)
                        else:
                            self.SetFoldExpanded(lineclicked, True)
                            self.Expand(lineclicked, True, True, 100)
                    else:
                        self.ToggleFold(lineclicked)

    def ToggleBreakpoint(self, evt, lineno=None):
        #import pdb; pdb.set_trace()
        if not lineno:
            lineno = self.LineFromPosition(self.GetCurrentPos())
        # toggle breakpoints:
        if self.MarkerGet(lineno) & self.BREAKPOINT_MARKER_MASK:
            if self.debugger:
                self.debugger.ClearBreakpoint(self.filename, lineno+1)
            self.MarkerDelete(int(lineno), self.BREAKPOINT_MARKER_NUM)
        else:
            if self.debugger:
                self.debugger.SetBreakpoint(self.filename, lineno+1)
            self.MarkerAdd(int(lineno), self.BREAKPOINT_MARKER_NUM)


    def FoldAll(self):
        lineCount = self.GetLineCount()
        expanding = True

        # find out if we are folding or unfolding
        for lineNum in range(lineCount):
            if self.GetFoldLevel(lineNum) & stc.STC_FOLDLEVELHEADERFLAG:
                expanding = not self.GetFoldExpanded(lineNum)
                break

        lineNum = 0

        while lineNum < lineCount:
            level = self.GetFoldLevel(lineNum)
            if level & stc.STC_FOLDLEVELHEADERFLAG and \
               (level & stc.STC_FOLDLEVELNUMBERMASK) == stc.STC_FOLDLEVELBASE:

                if expanding:
                    self.SetFoldExpanded(lineNum, True)
                    lineNum = self.Expand(lineNum, True)
                    lineNum = lineNum - 1
                else:
                    lastChild = self.GetLastChild(lineNum, -1)
                    self.SetFoldExpanded(lineNum, False)

                    if lastChild > lineNum:
                        self.HideLines(lineNum+1, lastChild)

            lineNum = lineNum + 1

    def Expand(self, line, doExpand, force=False, visLevels=0, level=-1):
        lastChild = self.GetLastChild(line, level)
        line = line + 1

        while line <= lastChild:
            if force:
                if visLevels > 0:
                    self.ShowLines(line, line)
                else:
                    self.HideLines(line, line)
            else:
                if doExpand:
                    self.ShowLines(line, line)

            if level == -1:
                level = self.GetFoldLevel(line)

            if level & stc.STC_FOLDLEVELHEADERFLAG:
                if force:
                    if visLevels > 1:
                        self.SetFoldExpanded(line, True)
                    else:
                        self.SetFoldExpanded(line, False)

                    line = self.Expand(line, doExpand, force, visLevels-1)

                else:
                    if doExpand and self.GetFoldExpanded(line):
                        line = self.Expand(line, True, force, visLevels-1)
                    else:
                        line = self.Expand(line, False, force, visLevels-1)
            else:
                line = line + 1

        return line

    def SynchCurrentLine(self, linenum):
        self.MarkerDeleteAll(self.CURRENT_LINE_MARKER_NUM)
        if linenum:
            # line numbering for editor is 0 based, dbg is 1 based.
            linenum = linenum - 1  
            self.EnsureVisibleEnforcePolicy(linenum)
            self.GotoLine(linenum)
            self.MarkerAdd(linenum, self.CURRENT_LINE_MARKER_NUM)


    def ToggleComment(self):
        "Toggle the comment of the selected region"
        sel = self.GetSelection()
        start = self.LineFromPosition(sel[0])
        end = self.LineFromPosition(sel[1])

        # Modify the selected line(s)
        self.BeginUndoAction()
        try:
            nchars = 0
            lines = range(start, end+1)
            lines.reverse()
            for line_num in lines:
                lstart = self.PositionFromLine(line_num)
                lend = self.GetLineEndPosition(line_num)
                text = self.GetTextRange(lstart, lend)
                tmp = text.strip()
                if len(tmp):
                    if tmp.startswith("#"):
                        text = text.replace('#', u'', 1)
                        nchars = nchars - 1
                    else:
                        text = '#' + text
                        nchars = nchars + 1
                    self.SetTargetStart(lstart)
                    self.SetTargetEnd(lend)
                    self.ReplaceTarget(text)
        finally:
            self.EndUndoAction()
            if sel[0] != sel[1]:
                self.SetSelection(sel[0], sel[1] + nchars)
            else:
                self.GotoPos(sel[0] + nchars)

    def get_find_mode(self):
        ret = 0
        if self.finddata.GetFlags() & wx.FR_WHOLEWORD:
            ret = ret | wx.stc.STC_FIND_WHOLEWORD
        elif self.finddata.GetFlags() & wx.FR_MATCHCASE:
            ret = ret | wx.stc.STC_FIND_MATCHCASE
        return ret


    def DoFind(self, evt=None, title="Find", style=0):
        if not self.finddlg:
            self.finddata = wx.FindReplaceData()
            self.finddata.SetFlags(wx.FR_DOWN)
            self.finddlg = wx.FindReplaceDialog(self, self.finddata, title,
                style)
            self.finddlg.style = style
        self.finddlg.Show(True)

    def DoReplace(self, evt):
        self.DoFind(evt, title="Find & Replace", style=wx.FR_REPLACEDIALOG)
        
    def OnFindReplace(self, evt):
        findstring = self.finddata.GetFindString()
        mode = self.get_find_mode()
        self.HighlightText(findstring, mode)
        if (self.finddata.GetFlags() & wx.FR_DOWN):
            start = self.GetCurrentPos()
            end = self.GetLength()
        else: 
            # revert direction:
            start, end = self.GetSelection()[0], 0

        pos = int(self.FindText(start, end, findstring, mode))
        if pos != -1:
            self.GotoPos(pos+len(findstring))
            self.SetSelection(pos, pos + len(findstring))
            if evt.GetEventType() == wx.wxEVT_COMMAND_FIND_REPLACE:
                replacestring = evt.GetReplaceString()
                self.ReplaceSelection(replacestring)
                self.GotoPos(pos+len(replacestring))
                self.SetSelection(pos, pos + len(replacestring))
            else:
                if not self.finddlg.style & wx.FR_REPLACEDIALOG:
                    self.finddlg.Hide()
                else:
                    self.GotoPos(start)
                wx.CallAfter(self.SetFocus)
            self.EnsureCaretVisible()
        else:
            wx.Bell()

    def OnFindForward(self, evt):
        flags = self.finddata.GetFlags()
        self.finddata.SetFlags(flags | wx.FR_DOWN)
        self.OnFindReplace(evt)

    def OnFindReverse(self, evt):
        flags = self.finddata.GetFlags()
        self.finddata.SetFlags(flags & ~wx.FR_DOWN)
        self.OnFindReplace(evt)

    def OnReplaceAll(self, evt):
        # get event data
        findstring = self.finddata.GetFindString()
        replacestring = evt.GetReplaceString()
        mode = self.get_find_mode()
        start, end = 0, self.GetLength()
        lenght= len(findstring)
        # search the text, replace targets
        while True:
            start = int(self.FindText(start, end, findstring, mode))
            if start == -1:
                break
            self.SetTargetStart(start)
            self.SetTargetEnd(start+lenght)
            self.ReplaceTarget(replacestring)
            start += len(replacestring)
        
    def HighlightText(self, findstring, mode):
        start, end = 0, self.GetLength()
        style = wx.stc.STC_INDIC1_MASK
        lenght= len(findstring)
        # clear all highlighted previous found text
        self.StartStyling(start, style)
        self.SetStyling(end, 0)
        # highlight found text:
        while lenght:
            start = int(self.FindText(start, end, findstring, mode))
            if start == -1:
                break
            self.StartStyling(start, style)
            self.SetStyling(lenght, style)
            start += lenght
        # dummy style to draw last found text (wx bug?)
        self.StartStyling(end, style)
        self.SetStyling(0, style)

    def OnFindClose(self, evt):
        self.finddlg.Destroy()
        del self.finddata
        self.finddlg = None
        self.HighlightText("",None)
        
    def DoBuiltIn(self, event):
        evtid = event.GetId()
        if evtid == wx.ID_COPY:
            self.CmdKeyExecute(wx.stc.STC_CMD_COPY)
        elif evtid == wx.ID_PASTE:
            self.Paste()
        elif evtid == wx.ID_CUT:
            self.CmdKeyExecute(wx.stc.STC_CMD_CUT)
        elif evtid == wx.ID_DELETE:
            self.CmdKeyExecute(wx.stc.STC_CMD_CLEAR)


class StandaloneEditor(wx.Frame):

    def __init__(self, filename=None):
        wx.Frame.__init__(self, None)
        self.Show()
        self.editor = EditorCtrl(self, -1, filename=filename)
        self.SendSizeEvent() 


if __name__ == '__main__':
    app = wx.App()
    editor = StandaloneEditor(filename="hola.py")
    editor.editor.SynchCurrentLine(4)
    app.MainLoop()


