#!/usr/bin/env python
# coding:utf-8

"Integrated Simple console for sys.stdin, sys.stdout and sys.stderr (w/history)"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# based on py.shell PseudoFile

import os
import sys
import time
import wx

DEBUG = False
BREAK_KEYS = ord('C'), ord('D'), ord('Z')


class ConsoleCtrl(wx.TextCtrl):
    "Integrated Simple Console based on TextCtrl (with history)"

    def __init__(self, parent, id=-1, text="",  pos=(0,0), size=(150, 90), 
                 style=wx.NO_BORDER | wx.TE_MULTILINE):
        wx.TextCtrl.__init__(self, parent, id, text, pos, size, style)
        self.isreading = False
        self.input = None           # input buffer
        self.history = []           # history buffer
        self.historyindex = 0
        self.encoding = "utf_8"
        self.startpos = 0           # readline start position
        self.process = None         # executing a piped process?
        self.inputstream = self.errorstream = self.outputstream = None

        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_IDLE, self.OnIdle)

    def OnIdle(self, event):
        if self.process is not None:
            pid = self.process.GetPid()
            if not self.process.Exists(pid):
                return
            if self.process.IsInputAvailable() and self.inputstream:
                if self.inputstream.CanRead():
                    self.write(self.inputstream.read())
            if self.process.IsErrorAvailable() and self.errorstream:
                if self.errorstream.CanRead():
                    self.write(self.errorstream.read())

    def OnKeyDown(self, event):
        "Key press event handler"
        key = event.GetKeyCode()
        controldown = event.ControlDown()
        altdown = event.AltDown()
        shiftdown = event.ShiftDown()
        
        if controldown and key in BREAK_KEYS:
            if DEBUG: print >> sys.stdout, "CTRL+C"
            if self.process:
                self.process.Kill(self.process.pid, wx.SIGKILL)
            else:
                raise KeyboardInterrupt()
        elif self.process and key!=wx.WXK_RETURN:
            if not self.startpos: # simulate readline!
                self.startpos = self.GetInsertionPoint()
            event.Skip()
        elif not self.isreading and self.process is None:
            pass # ignore 
        elif (not controldown and not shiftdown and not altdown) and \
           key in [wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER]:
            self.processline()
        elif key==wx.WXK_UP:
            self.replacefromhistory(-1)
        elif key==wx.WXK_DOWN:
            self.replacefromhistory(+1)
        elif key in (wx.WXK_BACK, wx.WXK_LEFT) and \
            self.GetInsertionPoint()<=self.startpos:
            pass # do not erase output
        else:
            event.Skip() # proceed with normal event handler

    def processline(self):
        "Process the line of text at which the user hit Enter"
        endpos = self.GetInsertionPoint()
        text = self.GetRange(self.startpos, endpos)
        if not text:
            # Match the behavior of the standard Python shell
            # when the user hits return without entering a
            # value.
            text = '\n'
        self.input = text
        self.write(os.linesep)
        if self.process:
            self.outputstream.write(text+"\n")
            self.startpos = None
        
    def readline(self):
        "Replacement for stdin.readline()"
        if self.isreading:
            # if we don't cancel, we will block...
            raise RuntimeError("Already expecting user input!")
        self.SetFocus()
        input = ''
        self.historyindex = len(self.history) - 1
        self.isreading = True
        self.startpos = self.GetInsertionPoint()
        try:
            while not self.input:
                wx.YieldIfNeeded()
            input = self.input
        finally:
            self.input = ''
            self.isreading = False
        input = str(input)  # In case of Unicode.
        self.history.append(input)
        return input

    def readlines(self):
        "Replacement for stdin.readlines()"
        lines = []
        while lines[-1:] != ['\n']:
            lines.append(self.readline())
        return lines

    def write(self, text):
        "Replacement for stdout.write()"
        text = self.fixlineendings(text)
        if DEBUG: print >> sys.stderr, "writing", text
        self.AppendText(text)
        #self.AddEncodedText(text)
        #editpoint = self.GetLength()
        #self.GotoPos(editpoint)
        #self.ScrollToLine(self.LineFromPosition(editpoint))

    def writelines(self, l):
        map(self.write, l)

    def flush(self):
        pass

    def isatty(self):
        return 1
        
    def fixlineendings(self, text):
        "Return text with line endings replaced by OS-specific endings"
        lines = text.split('\r\n')
        for l in range(len(lines)):
            chunks = lines[l].split('\r')
            for c in range(len(chunks)):
                chunks[c] = os.linesep.join(chunks[c].split('\n'))
            lines[l] = os.linesep.join(chunks)
        text = os.linesep.join(lines)
        return text

    def replacefromhistory(self, step):
        "Replace selection with command from the history buffer"
        text = self.history[self.historyindex]
        self.Replace(self.startpos, self.GetInsertionPoint(), text)
        self.historyindex += step
        # wraparound?
        if self.historyindex<0:
            self.historyindex = len(self.history)-1 
        elif self.historyindex>len(self.history)-1:
            self.historyindex = 0

    def close(self):
        self.isreading = False


class StandaloneConsole(wx.Frame):
    "Test frame for a simple console"

    def __init__(self, filename=None):
        wx.Frame.__init__(self, None)
        self.Show()
        self.console = ConsoleCtrl(self, -1)
        self.SendSizeEvent() 
        sys.stdin = sys.stdout =  self.console
        self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
        
    def OnActivate(self, evt):
        if DEBUG: print >> sys.stderr, "activate!"
        # test console
        print "hello world!"
        while True:
            i = raw_input("please type your name?")
            if not i: break
            print "hello", i
        print "goodbye..."


if __name__ == '__main__':
    DEBUG = True
    app = wx.App()
    frame = StandaloneConsole()
    app.MainLoop()


