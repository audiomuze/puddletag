# -*- coding: utf-8 -*-
from puddlestuff.actiondlg import ActionWindow, CreateFunction
from puddlestuff.constants import RIGHTDOCK, SELECTIONCHANGED
from PyQt4.QtGui import QPushButton, QHBoxLayout
from PyQt4.QtCore import SIGNAL
from puddlestuff.mainwin.funcs import run_func, applyaction
from functools import partial
import pdb

class ActionDialog(ActionWindow):
    def __init__(self, *args, **kwargs):
        self.emits = []
        self.receives = [(SELECTIONCHANGED, self._update)]
        if 'status' in kwargs:
            self._status = kwargs['status']
            del(kwargs['status'])
        super(ActionDialog, self).__init__(*args, **kwargs)
        self.okcancel.ok.hide()
        self.okcancel.cancel.hide()
        self._apply = QPushButton('Appl&y')
        write = lambda funcs: applyaction(self._status['selectedfiles'], funcs)
        self.connect(self._apply, SIGNAL('clicked()'),
            partial(self.okClicked, False))
        self.connect(self, SIGNAL('donewithmyshit'), write)
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self._apply)
        self.grid.addLayout(hbox, 3,0,1,2)

    def _update(self):
        try:
            self._example = self._status['selectedfiles'][0]
        except IndexError:
            self._example = None
        self.updateExample()


class FunctionDialog(CreateFunction):
    def __init__(self, *args, **kwargs):
        self.emits = []
        self.receives = [(SELECTIONCHANGED, self._update)]
        if 'status' in kwargs:
            self._status = kwargs['status']
            del(kwargs['status'])
        super(FunctionDialog, self).__init__(*args, **kwargs)
        self.okcancel.ok.hide()
        self.okcancel.cancel.hide()
        self._apply = QPushButton('Appl&y')
        write = lambda func: run_func(self._status['selectedfiles'], func)
        self.connect(self._apply, SIGNAL('clicked()'), 
            partial(self.okClicked, False))
        self.connect(self, SIGNAL('valschanged'), write)
        
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self._apply)
        self.vbox.addLayout(hbox)

    def _update(self):
        try:
            f = self._status['selectedfiles'][0]
        except IndexError:
            return
        field = self._status['selectedtags'][0].keys()[0]
        self.example = f
        self._text = f.get(field, u'')
        
        widget = self.stack.currentWidget()
        
        widget._text = self._text
        widget.example = f

        widget.showexample()


controls = [
    ("Functions", FunctionDialog, RIGHTDOCK, False),
    ("Actions", ActionDialog, RIGHTDOCK, False)]