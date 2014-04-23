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
import fileutil

# autocompletion library:
import jedi


# Some configuration constants 
WORDCHARS = "_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
FACES = {'times': 'DejaVu Sans', 'mono': 'DejaVu Sans Mono', 
         'helv' : 'DejaVu Serif', 'other': 'DejaVu',
         'size' : 10, 'size2': 8}
CALLTIPS = True # False or 'first paragraph only'     
AUTOCOMPLETE = True
AUTOCOMPLETE_IGNORE = []


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
                 lang="python", title="", cfg_styles={}):
        global TAB_WIDTH, IDENTATION, CALLTIPS, AUTOCOMPLETE, FACES

        stc.StyledTextCtrl.__init__(self, parent, ID, pos, size, style)

        # read configuration
        TAB_WIDTH = cfg.get("tab_width", 4)
        USE_TABS = cfg.get('use_tabs', False)
        IDENTATION = " " * TAB_WIDTH
        EDGE_COLUMN = cfg.get("edge_column", 79)
        ENCODING = cfg.get("encoding", "utf_8")
        CALLTIPS = cfg.get("calltips", True)
        AUTOCOMPLETE = cfg.get("autocomplete", True)
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
        self.title = title
        self.filetimestamp = None
        self.modified = None
        self.calltip = 0
        app = wx.GetApp()
        if hasattr(app, 'main_frame'):
            self.namespace = app.main_frame.web2py_namespace()
        else:
            self.namespace = {}
        # default encoding and BOM (pep263, prevent syntax error  on new fieles)
        self.encoding = ENCODING 
        self.bom = codecs.BOM_UTF8

        self.CmdKeyAssign(ord('B'), stc.STC_SCMOD_CTRL, stc.STC_CMD_ZOOMIN)
        self.CmdKeyAssign(ord('N'), stc.STC_SCMOD_CTRL, stc.STC_CMD_ZOOMOUT)
        self.CmdKeyAssign(ord('U'), stc.STC_SCMOD_CTRL, stc.STC_CMD_UNDO)
        self.CmdKeyAssign(ord('Z'), stc.STC_SCMOD_CTRL, stc.STC_CMD_UNDO)
        self.CmdKeyAssign(ord('Z'), stc.STC_SCMOD_CTRL | stc.STC_SCMOD_SHIFT, 
                          stc.STC_CMD_REDO)
        self.CmdKeyAssign(ord('Y'), stc.STC_SCMOD_CTRL, stc.STC_CMD_REDO)

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


        # register some images for use in the AutoComplete box appended "?type"
        self.RegisterImage(1, images.module.GetBitmap())
        self.RegisterImage(2, images.class_.GetBitmap())
        self.RegisterImage(3, images.method.GetBitmap())
        self.RegisterImage(4, images.function.GetBitmap())
        self.RegisterImage(5, images.variable.GetBitmap())

        self.Bind(wx.EVT_MENU, self.OnSave, id = wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self.OnSaveAs, id = wx.ID_SAVEAS)

        self.Bind(stc.EVT_STC_SAVEPOINTREACHED, self.OnSavePoint)
        self.Bind(stc.EVT_STC_SAVEPOINTLEFT, self.OnSavePoint)
        self.Bind(stc.EVT_STC_UPDATEUI, self.OnUpdateUI)
        self.Bind(stc.EVT_STC_MARGINCLICK, self.OnMarginClick)
        self.Bind(stc.EVT_STC_CHANGE, self.OnChange)
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
        
        # Mouse over "inspect" (eval):
        self.SetMouseDwellTime(500)
        self.Bind(stc.EVT_STC_DWELLSTART, self.OnHover)
        self.Bind(wx.stc.EVT_STC_DWELLEND, self.OnEndHover)
        
        self.OnOpen()
        self.SetFocus()

    def SetStyles(self, lang='python', cfg_styles={}):
        self.StyleClearAll()

        # INDICATOR STYLE FOR ERRORS/DEFECTS: STC_INDIC0_MASK
        self.IndicatorSetStyle(0, stc.STC_INDIC_SQUIGGLE)
        self.IndicatorSetForeground(0, wx.RED)

        # INDICATOR STYLE FOR SELECTION (FIND/REPLACE): STC_INDIC1_MASK
        self.IndicatorSetStyle(1, stc.STC_INDIC_ROUNDBOX) #ROUNDBOX
        self.IndicatorSetForeground(1, wx.Colour(0xFF, 0xA5, 0x00))
        
        # read configuration
        for key, value in cfg_styles.items():
            self.StyleSetSpec(eval("stc.%s" % key.upper()), value % FACES)

    def LoadFile(self, filename, encoding=None):
        "Replace STC.LoadFile for non-unicode files and BOM support"
        # open the file with universal line-endings support
        f = None
        try:
            if self.debugger and self.debugger.is_remote():
                f = self.debugger.ReadFile(filename)
                readonly = True
            else:
                f = open(filename, "Ur")
                readonly = False

            # analyze encoding and line ending, get text properly decoded
            text, encoding, bom, eol, nl = fileutil.unicode_file_read(f, encoding)
            
            # store internal values for future reference
            self.encoding = encoding 
            self.bom = bom
            self.eol = eol
            
            # set line endings mode
            self.SetEOLMode(self.eol)
                
            # load text (unicode!)
            self.SetText(text)
            
            # remote text cannot be modified:
            if readonly:  
                self.SetReadOnly(True)
            return True
        except Exception, e:
            dlg = wx.MessageDialog(self, unicode(e), "Unable to Load File",
                       wx.OK | wx.ICON_EXCLAMATION)
            dlg.ShowModal()
            dlg.Destroy()
            return False
        finally:
            if f:
                f.close()
            
    def SaveFile(self, filename, encoding=None):
        if self.ReadOnly:
            return  # do not save if the file is readonly (remote debugger)
        f = None
        try:
            f = open(filename, "wb")
            if self.bom:
                # preserve Byte-Order-Mark
                f.write(self.bom)
            f.write(self.GetText().encode(self.encoding))
            f.close()
            self.parent.NotifyRepo(self.filename, action="saved", status="")
            # prevent undo going further than this
            self.EmptyUndoBuffer()
            self.SetSavePoint()
        except Exception, e:
            dlg = wx.MessageDialog(self, unicode(e), "Unable to Save File",
                       wx.OK | wx.ICON_EXCLAMATION)
            dlg.ShowModal()
            dlg.Destroy()
        finally:
            if f:
                f.close()

    def OnOpen(self, event=None):
        if self.filename and self.LoadFile(self.filename):
            self.filetimestamp = os.stat(self.filename).st_mtime
            # call to SetTile setting modified=False (fix LoadFile -> OnChange)
            wx.CallAfter(self.SetTitle, False)
            # prevent undo going further than this (cleaning the document)
            self.EmptyUndoBuffer()
            self.SetSavePoint()
        else:
            # file not loaded correctly, empty its name (assume new)
            self.filename = None

    def GetTitle(self):
        if self.title:
            title = self.title
        elif self.filename:
            title = os.path.basename(self.filename)
        else:
            title = "New"
        if self.modified:
            title += " *"
        return title
        
    def SetTitle(self, modified=None):
        if modified is not None:
            self.modified = modified
        self.parent.SetTitle(self.GetTitle())

    def OnChange(self, event=None):
        "Received EVT_STC_CHANGE, text has been modified -update title-"
            
    def OnSavePoint(self, event):
        "Received EVT_STC_SAVEPOINTREACHED/LEFT, update title"
        self.modified = event.EventType in stc.EVT_STC_SAVEPOINTLEFT.evtType
        self.SetTitle() 

    def OnFocus(self, event=None):
        # check for data changes
        if self.filename and self.filetimestamp != None:
          if self.filetimestamp != os.stat(self.filename).st_mtime:
            self.filetimestamp = os.stat(self.filename).st_mtime
            if wx.MessageBox('The content of the %s file has changed on disk.  '
                             'You might be changing it in another editor.  '
                             'Would you like to synchronize the text here with '
                             'the file on disk?' % self.filename, 
                             'Content Changed: %s' % self.GetTitle(),
                             style=wx.YES_NO) == wx.YES:
              self.OnOpen()
        event.Skip()

    def OnClose(self, event=None):
        "Test if editor can be closed, return None if cancelled, True if saved"
        if self.modified:
            result = wx.MessageBox('File "%s" has changed. '
                             'Do you want to save the changes?' % self.filename, 
                             'Content Changed: %s' % self.GetTitle(), 
                             style=wx.YES_NO | wx.CANCEL)
            if result == wx.YES:
                self.OnSave()
                return True
            elif result == wx.CANCEL:
                if event:
                    event.Veto()
                else:
                    return None
        return False

    def GetCodeObject(self):
        '''Retrieves the code object created from this script'''
        # required by compile
        text = self.GetText()
        if isinstance(text, unicode):
            text = text.encode("utf8")
        text = text.rstrip().replace('\r\n','\n')+'\n'
        try:
            ok = compile(text, self.filename or '<script>', 'exec')
            self.HighlightLines([])  # clear styling of previous errors
            return ok
        except Exception, e:
            offset = e.offset or 0  # sometimes these are None
            lineno = e.lineno or 0
            self.parent.ShowInfoBar('You have a syntax error on line' + ' ' + str(lineno) + ', ' + 'column' + ' ' + str(offset) + '.', 
                     flags=wx.ICON_WARNING)
            # line with a caret indicating the approximate error position:
            desc = e.text + " " * offset + "^"
            self.parent.NotifyDefect(summary=str(e), description=desc, type="20", filename=self.filename, lineno=lineno, offset=offset)
            self.HighlightLines([lineno])
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
        elif key == wx.WXK_SPACE and control and not self.AutoCompActive():
            self.AutoComplete()
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

    def GetWord(self, whole=None, pos=None):
        for delta in (0,-1,1):
            word = self._GetWord(whole=whole, delta=delta, pos=pos)
            if word: return word
        return ''

    def _GetWord(self, whole=None, delta=0, pos=None):
        if pos is None:
            pos = self.GetCurrentPos()+delta
            line = self.GetCurrentLine()
        else:
            line = self.LineFromPosition(pos)
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
        if word in self.namespace:return self.namespace[word]
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


    def GetScript(self):
        "Return Jedi script object suitable to AutoComplete and ShowCallTip"
        source = self.GetText().encode(self.encoding)
        pos = self.GetCurrentPos()
        col = self.GetColumn(pos)
        line = self.GetCurrentLine() + 1
        return jedi.Script(source, line, col, '')


    def AutoComplete(self, obj=0):
        if obj:
            self.AddText('.')
            word = ''
        else:
            word = self.GetWord()
        script = self.GetScript()
        completions = script.complete()
        words = []
        for completion in completions:
            if completion.name.startswith("__"):
                # ignore internal and private attributes
                continue
            img = {"module": 1, "class": 2, "function": 4, "instance": 5, 
                   "statement": 0, "keyword": 0, "import": 0,
                  }.get(completion.type, 0)
            name = "%s?%s" % (completion.name, img)
            if name not in words: words.append(name)
        if words:
            self.AutoCompShow(len(word), " ".join(words))

    def ShowCallTip(self,text=''):
        #prepare
        self.AddText(text)
        script = self.GetScript()
        # parameters:
        for signature in script.call_signatures():
            params = [p.get_code().replace('\n', '') for p in signature.params]
            try:
                params[signature.index] = '%s' % params[signature.index]
            except (IndexError, TypeError):
                pass
        else:
            params = []
        tip = ', '.join(params)
        #normal docstring
        definitions = script.goto_definitions()
        if definitions:
            docs = ['Docstring for %s\n%s\n%s' % (d.desc_with_module, '=' * 40, d.doc)
                if d.doc else '|No Docstring for %s|' % d for d in definitions]
            doc = ('\n' + '-' * 79 + '\n').join(docs)
        else:
            doc = ""
        #compose
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
        
        # update status bar
        self.OnPositionChanged(evt)

    def OnMarginClick(self, evt):
        # fold and unfold as needed
        lineclicked = self.LineFromPosition(evt.GetPosition())
        if evt.GetMargin() == 0:
            self.ToggleBreakpoint(lineclicked)
        elif evt.GetMargin() == 3:
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
        ok = None
        if not lineno:
            lineno = self.LineFromPosition(self.GetCurrentPos())
        # toggle breakpoints:
        if self.MarkerGet(lineno) & self.BREAKPOINT_MARKER_MASK:
            if self.debugger:
                ok = self.debugger.ClearBreakpoint(self.filename, lineno+1)
            if ok is not None:
                self.MarkerDelete(int(lineno), self.BREAKPOINT_MARKER_NUM)
        else:
            if self.debugger:
                ok = self.debugger.SetBreakpoint(self.filename, lineno+1)
            if ok is not None:
                self.MarkerAdd(int(lineno), self.BREAKPOINT_MARKER_NUM)

    def ClearBreakpoints(self, evt):
        lineno = 1
        while True:
            lineno = self.MarkerNext(lineno, self.BREAKPOINT_MARKER_MASK)
            if lineno<0:
                break
            self.ToggleBreakpoint(evt, lineno)

    def GetBreakpoints(self):
        lineno = 0
        breakpoints = {}
        while True:
            lineno = self.MarkerNext(lineno+1, self.BREAKPOINT_MARKER_MASK)
            if lineno<0:
                break
            breakpoints[lineno+1] = (None, None)
        return breakpoints

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
        # do not update if currently in the same line
        self.MarkerDeleteAll(self.CURRENT_LINE_MARKER_NUM)
        if linenum:
            # line numbering for editor is 0 based, dbg is 1 based.
            linenum = linenum - 1  
            self.EnsureVisibleEnforcePolicy(linenum)
            self.GotoLine(linenum)
            self.MarkerAdd(linenum, self.CURRENT_LINE_MARKER_NUM)
   
    def GetLineText(self, linenum):
        lstart = self.PositionFromLine(linenum - 1)
        lend = self.GetLineEndPosition(linenum - 1)
        return self.GetTextRange(lstart, lend).encode(self.encoding)

    def ToggleComment(self, event=None):
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
            # store find data (reference to prevent SEGV)
            self.finddata = wx.FindReplaceData()
            self.finddata.SetFlags(wx.FR_DOWN)
            # use selected text as initial search string
            if self.GetSelectedText():
                self.finddata.SetFindString(self.GetSelectedText())
                self.finddata.SetReplaceString(self.GetSelectedText())
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
        "Find text and applies indicator style (ORANGE BOX) to all occurrences"
        start, end = 0, self.GetLength()
        # force to the lexer to style the text not visible yet
        self.Colourise(start, end)
        style = stc.STC_INDIC1_MASK
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

    def HighlightLines(self, lines):
        "Applies indicator style (RED SQUIGGLE default) to the lines listed"
        start, end = 0, self.GetLength()
        # force to the lexer to style the text not visible yet
        self.Colourise(start, end)
        style = stc.STC_INDIC0_MASK
        # clear all highlighted previous found text
        self.StartStyling(start, style)
        self.SetStyling(end, 0)
        # highlight found text:
        for lineno in lines:
            start = lineno>1 and (self.GetLineEndPosition(lineno-2) + 1) or 0
            lenght = self.GetLineEndPosition(lineno-1) - start
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
        elif evtid == wx.ID_UNDO:
            self.CmdKeyExecute(stc.STC_CMD_UNDO)  
        elif evtid == wx.ID_REDO:
            self.CmdKeyExecute(stc.STC_CMD_REDO)  
    
    def OnHover(self, evt):
        # Abort if not debugging (cannot eval) or position is invalid
        if self.debugger and self.debugger.attached and evt.GetPosition() >= 0:
            # get selected text first:
            expr = self.GetSelectedText()
            if not expr:
                expr = self.GetWord(whole=True, pos=evt.GetPosition())
            # Query qdb debugger to evaluate the expression
            if expr and self.debugger.interacting:
                value = self.debugger.Eval(expr)
                if value is not None:
                    expr_value = "%s = %s" % (expr, value)
                    wx.CallAfter(self.SetToolTipString, expr_value)
        evt.Skip()
        
    def OnEndHover(self, evt):
        self.SetToolTipString("")

    def OnPositionChanged(self, event):
        eolmode = self.GetEOLMode()

        if self.GetOvertype():
            ovrstring = "OVR"
        else:
            ovrstring = "INS"
        linestr = self.GetCurrentLine()+1
        colstr = self.GetColumn(self.GetCurrentPos())
        statustext = "Line: %(line)s, Col: %(col)s  %(ovrstring)s" % {
            "line": linestr, "col": colstr, 
            "ovrstring": ovrstring }
        self.parent.UpdateStatusBar(statustext, eolmode, self.encoding)

    def ChangeEOL(self, eolmode=None):
        self.eol = eolmode
        self.ConvertEOLs(self.eol)
        self.SetEOLMode(self.eol)

    def ToggleBlanks(self, visible=False):
        if visible:
            ws = wx.stc.STC_WS_VISIBLEALWAYS
            eol = 1
        else:
            ws = wx.stc.STC_WS_INVISIBLE
            eol = 0
        self.SetViewWhiteSpace(ws)
        self.SetViewEOL(eol)


class StandaloneEditor(wx.Frame):

    def __init__(self, filename=None):
        wx.Frame.__init__(self, None)
        self.Show()
        self.editor = EditorCtrl(self, -1, filename=filename)
        self.SendSizeEvent() 

    def UpdateStatusBar(self, statustext, eolmode, encoding):
        print statustext, eolmode, encoding


if __name__ == '__main__':
    app = wx.App()
    editor = StandaloneEditor(filename=os.path.abspath("hola.py"))
    editor.editor.SynchCurrentLine(4)
    app.MainLoop()


