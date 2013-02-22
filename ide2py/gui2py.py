"Basic Proof-of-Concept for GUI design integration"

import sys,os
import wx
import wx.lib.agw.aui as aui

GUI2PY_PATH = "../../gui2py"

class Gui2pyMixin:

    def __init__(self, ):
        
        try:
            try:
                import gui
            except ImportError:
                sys.path.append(GUI2PY_PATH)
                
            # import controls (fill the registry!)
            from gui import Window

            # import tools used by the designer
            from gui.tools.inspector import InspectorPanel
            from gui.tools.propeditor import PropertyEditorPanel
            from gui.tools.designer import BasicDesigner
            from gui.tools.toolbox import ToolBox, ToolBoxDropTarget

            # create the windows and the property editor / inspector
            log = sys.stdout
                  
            self.propeditor = PropertyEditorPanel(self, log)
            self.inspector = InspectorPanel(self, self.propeditor, log)

            self._mgr.AddPane(self.propeditor, aui.AuiPaneInfo().Name("propeditor").
                  Caption("Property Editor").Float().FloatingSize(wx.Size(400, 100)).
                  FloatingPosition(self.GetStartPosition()).DestroyOnClose(False).PinButton(True).
                  MinSize((100, 100)).Right().Bottom().MinimizeButton(True))

            self._mgr.AddPane(self.inspector, aui.AuiPaneInfo().Name("inspector").
                  Caption("inspector").Float().FloatingSize(wx.Size(400, 100)).
                  FloatingPosition(self.GetStartPosition()).DestroyOnClose(False).PinButton(True).
                  MinSize((100, 100)).Right().Bottom().MinimizeButton(True))

            self.toolbox = ToolBox(self)

            self._mgr.AddPane(self.toolbox, aui.AuiPaneInfo().Name("toolbox").
                              ToolbarPane().Left().Position(2))
                              
            filename = os.path.join(GUI2PY_PATH, "sample.pyw")
            vars = {}
            execfile(filename, vars)
            w = None
            for name, value in vars.items():
                if not isinstance(value, Window):
                    continue
                w = value       # TODO: support many windows
                # load the window in the widget inspector
                self.inspector.load_object(w)
                # associate the window with the designer:
                # (override mouse events to allow moving and resizing)
                self.designer = BasicDesigner(w, self.inspector)
                # associate the window with the toolbox:
                # (this will allow to drop new controls on the window)
                dt = ToolBoxDropTarget(w, designer=self.designer, inspector=self.inspector)
                w.drop_target = dt
                # link the designer (context menu)
                self.inspector.set_designer(self.designer)
                w.show()

            ##w.onunload = save 
        
            # this does not work:
            #w.wx_obj.Reparent(self)
            ##self._mgr.AddPane(w.wx_obj, aui.AuiPaneInfo().Name("UserWindow").
            ##                  Float())

            w.stay_on_top = True    # assure the windows stay on top of AUI
            w.show()

        except ImportError, e:
            self.ShowInfoBar(u"cannot import gui2py!: %s" % unicode(e), 
                                 flags=wx.ICON_ERROR, key="gui2py")

