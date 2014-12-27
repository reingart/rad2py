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
import uuid

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



class EditorCtrl(stc.StyledTextCtrl):
    "Editor based on Styled Text Control"

    CURRENT_LINE_MARKER_NUM = 0x10
    BREAKPOINT_MARKER_NUM = 1
    CURRENT_LINE_MARKER_MASK = 2 ** CURRENT_LINE_MARKER_NUM
    BREAKPOINT_MARKER_MASK = 2 ** BREAKPOINT_MARKER_NUM
   
    def __init__(self, parent, ID,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=0, filename=None, debugger=None, cfg={}, 
                 metadata=None, get_current_phase=None,
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
        self.breakpoints = {}
        self.metadata = metadata    # dict of uuid, origin for line tracking
        self.clipboard = None       # lines text and metadata for cut/paste
        self.actions_buffer = []    # insertions / deletions for undo and redo
        self.actions_pointer = 0
        self.get_current_phase = get_current_phase or (lambda: None)
        app = wx.GetApp()
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
        self.SetMarginMask(0, 0x0F)
        self.SetMarginWidth(0, 12)
        # margin 1 for current line arrow
        self.SetMarginSensitive(1, False)
        self.SetMarginMask(1, self.CURRENT_LINE_MARKER_MASK)
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
        self.SetProperty("fold.comment.python", "1")
        self.SetProperty("fold.quotes.python", "1")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDEROPEN, stc.STC_MARK_BOXMINUS, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDER, stc.STC_MARK_BOXPLUS, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDERSUB, stc.STC_MARK_VLINE, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDERTAIL, stc.STC_MARK_LCORNER, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDEREND, stc.STC_MARK_BOXPLUSCONNECTED, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDEROPENMID, stc.STC_MARK_BOXMINUSCONNECTED, "white", "#808080")
        self.MarkerDefine(stc.STC_MARKNUM_FOLDERMIDTAIL, stc.STC_MARK_TCORNER, "white", "#808080")

        # Define the current line marker
        self.MarkerDefine(self.CURRENT_LINE_MARKER_NUM, wx.stc.STC_MARK_SHORTARROW, wx.BLACK, (255,255,128))
        self.MarkerDefine(self.CURRENT_LINE_MARKER_NUM+1, wx.stc.STC_MARK_BACKGROUND, wx.BLACK, (255,255,128))
        # Define the breakpoint marker
        self.MarkerDefine(self.BREAKPOINT_MARKER_NUM, wx.stc.STC_MARK_CIRCLE, wx.BLACK, (255,0,0))
        self.MarkerDefine(self.BREAKPOINT_MARKER_NUM+1, wx.stc.STC_MARK_PLUS, wx.BLACK, wx.WHITE)
        self.MarkerDefine(self.BREAKPOINT_MARKER_NUM+2, wx.stc.STC_MARK_DOTDOTDOT, wx.BLACK, wx.BLUE)

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
        self.Bind(stc.EVT_STC_MODIFIED, self.OnModified)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_CHAR, self.OnChar)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)

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

            # if metadata is given, avoid updating it in the initial inserts
            if self.metadata:
                mask = self.GetModEventMask()
                # disable modification events
                self.SetModEventMask(0)
            else:
                mask = None
                # add the metadata for the first line (even empty files has one) 
                phase = self.get_current_phase()
                datum = {"uuid": str(uuid.uuid1()), "origin": 0, "phase": phase}
                datum["text"] = ""
                self.metadata.insert(0, datum)
            
            # load text (unicode!)
            self.SetText(text)
            
            # re-enable modification events (if disabled):
            if mask is not None:
                self.SetModEventMask(mask)
            
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
            self.metadata = None

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
        # rollback any change to the metadata
        if hasattr(self.metadata, "sync"):
            self.metadata.sync(commit=False)
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

    def GotoPos(self, pos):
        "Set caret to a position and ensure it is visible (unfolding)"
        # enforce line visibility (expands any header line hiding it):
        lineno = self.LineFromPosition(pos)
        self.EnsureVisibleEnforcePolicy(lineno)
        stc.StyledTextCtrl.GotoPos(self, pos)
        # scroll properly (just in case, should not be necessary)!
        self.EnsureCaretVisible()
        # TODO: SetFocus?
    
    def OnSave(self, event=None):
        if self.filename:
            self.SaveFile(self.filename)
            self.modified = False
            self.filetimestamp = os.stat(self.filename).st_mtime
            self.SetTitle()
            self.GetCodeObject()
            if hasattr(self.metadata, "sync"):
                self.metadata.sync(commit=True)
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
        elif key == ord('X') and control and not alt:
            self.Cut()
        elif key == ord('C') and control and not alt:
            self.Copy()
        elif key == ord('V') and control and not alt:
            self.Paste()
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


    def GetScript(self):
        "Return Jedi script object suitable to AutoComplete and ShowCallTip"
        source = self.GetText() #.encode(self.encoding)
        pos = self.GetCurrentPos()
        col = self.GetColumn(pos)
        line = self.GetCurrentLine() + 1
        return jedi.Script(source, line, col, self.filename)


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

    def GetDefinition(self):
        #prepare
        script = self.GetScript()
        if True:
            definitions = script.goto_assignments()
        else:
            definitions = script.goto_definitions()
        while definitions:
            definition = definitions.pop()
            if "__builtin__" not in definition.module_path:
                break
        else:
            return None, None, None
        return definition.module_path, definition.line, definition.column+1

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
        lineclicked = self.LineFromPosition(evt.GetPosition())
        if evt.GetMargin() == 0:
            # update beakpoints
            if evt.GetShift() or evt.GetAlt() or evt.GetControl():
                # conditional / temporary bp:
                self.ToggleAltBreakpoint(evt, lineclicked)
            else:
                self.ToggleBreakpoint(evt, lineclicked)
        elif evt.GetMargin() == 3:
            # fold and unfold as needed
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

    def ToggleBreakpoint(self, evt=None, lineno=None, cond=None, temp=False):
        ok = None
        if lineno is None:
            lineno = self.LineFromPosition(self.GetCurrentPos())
            # fix the line number (starting at 0 for STC, 1 for debugger):
            lineno += 1
        else:
            lineno = int(lineno)
        # toggle breakpoints:
        if self.MarkerGet(lineno - 1) & self.BREAKPOINT_MARKER_MASK:
            # delete the breakpoint (if debugger is running) and marker
            if self.debugger:
                ok = self.debugger.ClearBreakpoint(self.filename, lineno)
            if ok is not None:
                # look for the marker handle (lineno can be moved)
                for handle in self.breakpoints:
                    if lineno - 1 == self.MarkerLineFromHandle(handle):
                        break
                else:
                    # handle not found (this should not happen)!
                    handle = None
                # remove the main breakpoint marker (handle) and alternate ones
                self.MarkerDeleteHandle(handle)
                if self.breakpoints[handle]['cond']:
                    self.MarkerDelete(lineno - 1, self.BREAKPOINT_MARKER_NUM+1)
                if self.breakpoints[handle]['temp']:
                    self.MarkerDelete(lineno - 1, self.BREAKPOINT_MARKER_NUM+2)
                del self.breakpoints[handle]
        else:
            # set the breakpoint (if debugger is running) and marker
            if self.debugger:
                ok = self.debugger.SetBreakpoint(self.filename, lineno, temp, cond)
            if ok is not None:
                # set the main breakpoint marker (get handle)
                handle = self.MarkerAdd(lineno - 1, self.BREAKPOINT_MARKER_NUM) 
                # set alternate markers (if any)
                if cond:
                    self.MarkerAdd(lineno - 1, self.BREAKPOINT_MARKER_NUM+1)
                if temp:
                    self.MarkerAdd(lineno - 1, self.BREAKPOINT_MARKER_NUM+2)
                # store the breakpoint in a struct for the debugger:
                bp = {'lineno': lineno, 'temp': temp, 'cond': cond}
                self.breakpoints[handle] = bp

    def ToggleAltBreakpoint(self, evt, lineno=None):
        if lineno is None:
            lineno = self.LineFromPosition(self.GetCurrentPos())
            # fix the line number (starting at 0 for STC, 1 for debugger):
            lineno += 1
        # search the breakpoint
        for handle in self.breakpoints:
            if lineno == self.MarkerLineFromHandle(handle):
                cond = self.breakpoints[handle]['cond']
                break
        else:
            cond = temp = handle = None            
        # delete the breakpoint if it already exist:
        if handle:
            self.ToggleBreakpoint(evt, lineno)
        # ask the condition
        dlg = wx.TextEntryDialog(self, "Conditional expression:"
                                 "(empty for temporary 1 run breakpoint)", 
                                 'Set Cond./Temp. Breakpoint', cond or "")
        if dlg.ShowModal() == wx.ID_OK:
            cond = dlg.GetValue() or None
            temp = cond is None
        dlg.Destroy()
        # set the conditional / temporary breakpoint:
        if cond or temp:
            self.ToggleBreakpoint(evt, lineno, cond, temp)

    def ClearBreakpoints(self, evt):
        lineno = 1
        while True:
            lineno = self.MarkerNext(lineno, self.BREAKPOINT_MARKER_MASK)
            if lineno<0:
                break
            self.ToggleBreakpoint(evt, lineno + 1)

    def GetBreakpoints(self):
        lineno = 0
        # update line numbers for each marker (text could be added/deleted):
        for handle in self.breakpoints:
            lineno = self.MarkerLineFromHandle(handle)
            self.breakpoints[handle]['lineno'] = lineno + 1
        return self.breakpoints

    def FoldAll(self, expanding=None):
        lineCount = self.GetLineCount()

        if expanding is None:
            expanding = True
            # find out if we are folding or unfolding
            for lineNum in range(lineCount):
                if self.GetFoldLevel(lineNum) & stc.STC_FOLDLEVELHEADERFLAG:
                    expanding = not self.GetFoldExpanded(lineNum)
                    break

        lineNum = 0

        while lineNum < lineCount:
            level = self.GetFoldLevel(lineNum)

            if level & stc.STC_FOLDLEVELBASE:

                self.SetFoldExpanded(lineNum, expanding)
                if expanding:
                    lineNum = self.Expand(lineNum, True)
                    lineNum = lineNum - 1
                else:
                    lastChild = self.GetLastChild(lineNum, -1)

                    if lastChild > lineNum:
                        self.HideLines(lineNum+1, lastChild)

            lineNum = lineNum + 1

    def GetFoldAll(self):
        "Export all fold information for persistence -line number 1 based-"
        linecount = self.GetLineCount()
        folds = []
        lineno = 0
        while lineno < linecount:
            level = self.GetFoldLevel(lineno)
            if level  & stc.STC_FOLDLEVELHEADERFLAG:
                fold = {
                        'level': level,
                        'start_lineno': lineno + 1,
                        'end_lineno': self.GetLastChild(lineno, -1) + 1,
                        'expanded': self.GetFoldExpanded(lineno),
                       }
                folds.append(fold)
            lineno = lineno + 1
        return folds

    def SetFold(self, start_lineno, expanded, level, **kwargs):
        "Programatically fold/unfold (exported) -line number 1 based-"
        if expanded != self.GetFoldExpanded(start_lineno - 1):
            self.ToggleFold(start_lineno - 1)

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
        self.MarkerDeleteAll(self.CURRENT_LINE_MARKER_NUM+1)
        if linenum:
            # line numbering for editor is 0 based, dbg is 1 based.
            linenum = linenum - 1  
            self.EnsureVisibleEnforcePolicy(linenum)
            self.GotoLine(linenum)
            self.MarkerAdd(linenum, self.CURRENT_LINE_MARKER_NUM)
            self.MarkerAdd(linenum, self.CURRENT_LINE_MARKER_NUM+1)
   
    def GetLineText(self, linenum, encode=False, strip=True):
        "Get the contents of a line (i.e. used by debugger) LineNum is 1-based"
        text = self.GetLine(linenum - 1) 
        if strip:
            text = text.rstrip().rstrip("\r").rstrip("\n")
        if encode:
            text = text.encode(self.encoding)
        return text

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
            self.Copy()
        elif evtid == wx.ID_PASTE:
            self.Paste()
        elif evtid == wx.ID_CUT:
            self.Cut()
        elif evtid == wx.ID_DELETE:
            self.CmdKeyExecute(wx.stc.STC_CMD_CLEAR)
        elif evtid == wx.ID_UNDO:
            self.CmdKeyExecute(stc.STC_CMD_UNDO)  
        elif evtid == wx.ID_REDO:
            self.CmdKeyExecute(stc.STC_CMD_REDO)  
    
    def Cut(self):
        "Override default Cut to track lines using an internal clipboard"
        start = self.LineFromPosition(self.GetSelectionStart())
        end = self.LineFromPosition(self.GetSelectionEnd())
        # store the uuids and line text to check on pasting:
        original_text_lines = [self.GetLineText(i+1) for i in range(start, end)]
        self.clipboard = original_text_lines, self.metadata[start:end]
        # call the default method:
        return stc.StyledTextCtrl.Cut(self)

    def Copy(self):
        "Override default Copy to track lines using an internal clipboard"
        # just clean internal clipboard as lines will be new when pasted
        self.clipboard = None
        return stc.StyledTextCtrl.Copy(self)
        
    def Paste(self):
        "Override default Paste to track lines using an internal clipboard"
        start = self.LineFromPosition(self.GetSelectionStart())
        ret = stc.StyledTextCtrl.Paste(self)
        # only restore uuids if text is the same (not copied from other app):
        if self.clipboard:
            original_text_lines, metadata_saved = self.clipboard
            end = start + len(metadata_saved)
            new_text_lines = [self.GetLineText(i+1) for i in range(start, end)]
            if metadata_saved and original_text_lines == new_text_lines:
                ##print "restoring", start, metadata_saved
                self.metadata[start:end] = metadata_saved
                self.clipboard = None
        return ret
        
    def Undo(self):
        print "UNDO!"
        
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

    def OnModified(self, evt):
        "Handle modifications to keep track of line identifiers (uuid)"
        # TODO: drag and drop 
        # cut and paste is handled in their own methods (post-modification)
        # undo and redo is handled using the action buffer (history)
        # insertions and deletions are mapped to a list of uuids
        # uses line origin (initially 0) to detect boundaries of inserted text 
        mod_type = evt.GetModificationType()
        pos = evt.GetPosition()
        lineno = self.LineFromPosition(pos)
        count = abs(evt.GetLinesAdded())            # negative on deletions
        offset = self.PositionFromLine(lineno) 
        undo = mod_type & stc.STC_PERFORMED_UNDO
        redo = mod_type & stc.STC_PERFORMED_REDO
        mod_inserted = mod_type & stc.STC_MOD_INSERTTEXT
        mod_deleted = mod_type & stc.STC_MOD_DELETETEXT 
        # track lines only if there are lines inserted / deleted (count)
        if count:
            # adjust offest with the origin column
            if lineno < len(self.metadata):
                offset += self.metadata[lineno]["origin"]
                self.metadata[lineno]["origin"] = 0
            # add the line after the current if not at the very begging
            # if at the beggin, the current line is moved down
            # (this preserves the correct uuid when inserting or deleting)
            after = 1 if offset < pos else 0
            if mod_inserted:
                ##print "Inserted %d @ %d %d %d" % (count, lineno, pos, offset)
                if undo:
                    action_info = self.get_last_action()
                elif redo:
                    action_info = self.get_next_action()
                else:
                    action_info = {}
                for i in range(count):
                    j = lineno + i + after
                    if undo or redo:
                        # restore previous uuid and origin
                        new_uuid = action_info[j]["uuid"]
                        origin = action_info[j]["origin"]
                        phase = action_info[j]["phase"]
                    else:
                        # create a new UUID
                        new_uuid, origin = str(uuid.uuid1()), 0
                        phase = self.get_current_phase()
                    datum = {"uuid": new_uuid, "origin": origin, "phase": phase}
                    datum["text"] = self.GetLineText(j+1)
                    self.metadata.insert(j, datum)
                    if not undo and not redo:
                        action_info[j] = {"uuid": new_uuid, "origin": origin, 
                                          "phase": phase}
                if not undo and not redo:
                    self.store_action(action_info)
            if mod_deleted:
                ##print "Removed %d lines @ %d" % (count, lineno)
                if not undo and not redo:
                    action_info = {}
                    for i in range(count):
                        j = lineno + i + after
                        action_info[j] = self.metadata[j]
                    self.store_action(action_info)
                del self.metadata[lineno + after:count + lineno + after]
            # move action buffer (history) pointer ahead/backwards accordingly
            if undo or redo:
                # note: a STC undo action could involve several pointer units
                self.actions_pointer += 1 if redo else -1
        elif self.metadata:
            # no newline, track insert and deletes (moving origin column)
            u = self.metadata[lineno]["uuid"]
            origin = self.metadata[lineno]["origin"]
            if mod_inserted:
                new_origin = (pos - offset) + evt.GetLength()
                if new_origin > origin:
                    self.metadata[lineno]["origin"] = new_origin
            elif mod_deleted:
                new_origin = (pos - offset)
                if new_origin < origin:
                    self.metadata[lineno]["origin"] = new_origin
            else:
                new_origin = None
            # update the current phase of this line as it was modified:
            new_text = evt.GetText().strip('\n')
            if (mod_inserted or mod_deleted) and new_text:
                # restore the phase if undoing or redoing an action:
                if undo:
                    action_info = self.get_last_action()
                    phase = action_info['phase']
                elif redo:
                    action_info = self.get_next_action()
                    phase = action_info['phase']
                else:
                    # store current metadata for future use (prior modification)
                    # NOTE: don't put it directly as it is a mutable dict 
                    self.store_action({'phase': self.metadata[lineno]['phase']})
                    phase = self.get_current_phase()
                self.metadata[lineno]["phase"] = phase
                self.metadata[lineno]["text"] = self.GetLineText(lineno+1)
                # update metadata pointer
                if undo or redo:
                    self.actions_pointer += 1 if redo else -1

            ##print "Origin", origin, new_origin, evt.GetLength(), pos, offset
        # output some debugging messages (uuid internal representation):
        if False:
            for i, m in enumerate(self.metadata):
                txt = self.GetLineText(i+1)
                lineno = i + 1
                print "%s %s%4d:%s" % (m["uuid"], m["origin"], lineno, txt)

    def store_action(self, action_info):
        "Save the action info to perorm a Undo / Redo"
        # remove further actions (in case they were undone)
        del self.actions_buffer[self.actions_pointer:]
        self.actions_buffer.append(action_info)
        ##print "saving action info", self.actions_pointer, action_info
        self.actions_pointer += 1

    def get_last_action(self):
        "Return the action info needed to perform an Undo"
        action_info = self.actions_buffer[self.actions_pointer - 1]
        ##print "loading action info", self.actions_pointer - 1, action_info
        return action_info

    def get_next_action(self):
        "Return the action info needed to perform a Redo"
        action_info = self.actions_buffer[self.actions_pointer]
        ##print "loading action info", self.actions_pointer, action_info
        return action_info


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


