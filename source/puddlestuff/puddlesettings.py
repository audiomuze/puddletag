#!/usr/bin/env python

"""In this module, all the dialogs for configuring puddletag are
stored. These are accessed via the Preferences windows.

The MainWin class is the important class since it creates,
the dialogs in a stacked widget and calls their methods as needed.

Each dialog must have in it's init method an argument called 'cenwid'.
cenwid is is puddletag's mainwindow found in puddletag.MainWin.
If cenwid is passed, then the dialog should read all it's values,
apply them and return(close). This is done when puddletag starts.

In addittion, each dialog should have a saveSettings functions, which
is called when settings pertinent to that dialog need to be saved.

It is not required, but recommended, that each dialog should also have 
an applySettings(self, cenwid) method, which can be called when 
settings need to be applied.
"""

"""
puddlesettings.py

Copyright (C) 2008 concentricpuddle

This file is part of puddletag, a semi-good music tag editor.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys, resource
from copy import copy
from puddleobjects import ButtonLayout, OKCancel, HeaderSetting, ListBox
import pdb

class ListModel(QAbstractListModel):
    def __init__(self, options):
        QAbstractListModel.__init__(self)
        self.options = options
        
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
            return QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            return QVariant(self.headerdata[section])
        return QVariant(int(section + 1))
    
    def data(self, index, role = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.options)):
            return QVariant()
        column = index.column()
        if (role == Qt.DisplayRole) or (role == Qt.ToolTipRole):
            try:
                return QVariant(self.options[index.row()][0])
            except IndexError: return QVariant()
        return QVariant()
    
    def widget(self, row):
        return self.options[row][1]
    
    def rowCount(self, index=QModelIndex()):
        return len(self.options)
    
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(QAbstractListModel.flags(self, index))

class SettingsList(QListView):
    def __init__(self, parent = None):
        QListView.__init__(self, parent)
    
    def selectionChanged(self, selected, deselected):
        self.emit(SIGNAL("selectionChanged"), selected.indexes()[0].row())
        
class PatternEditor(QDialog):
    def __init__(self, parent = None, cenwid = None):
        QDialog.__init__(self, parent)
        self.listbox = ListBox()
        buttons = ButtonLayout()
        settings = QSettings()
        
        patterns = settings.value("editor/patterns").toStringList()
        if patterns.count() == 0:
            patterns = QSettings(":/puddletag.conf", QSettings.IniFormat).value("editor/patterns").toStringList()
        
        if cenwid:
            cenwid.patterncombo.clear()
            cenwid.patterncombo.addItems(patterns)
            return
        self.listbox.addItems(patterns)
        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox)
        hbox.addLayout(buttons)
        self.setLayout(hbox)
        
        self.connect(buttons, SIGNAL("add"), self.addPattern)
        self.connect(buttons, SIGNAL("edit"), self.editItem)
        self.connect(buttons, SIGNAL("remove"), self.listbox.removeSelected)
        self.connect(buttons, SIGNAL("moveup"), self.listbox.moveUp)
        self.connect(buttons, SIGNAL("movedown"), self.listbox.moveDown)
    
    def saveSettings(self):
        settings = QSettings()
        patterns = [self.listbox.item(row).text() for row in xrange(self.listbox.count())]
        settings.setValue("editor/patterns",QVariant(QStringList(patterns)))

    
    def addPattern(self):
        self.listbox.addItem("")
        self.listbox.setCurrentRow(self.listbox.count() - 1)
        self.editItem(True)
        self.listbox.setFocus()
    
    def editItem(self, add = False):
        item = self.listbox.currentItem()
        if item:
            (text, ok) = QInputDialog.getText(self, "Enter new pattern","Enter a pattern here:", QLineEdit.Normal, item.text())
        if ok:
            item.setText(text)
    
    def applySettings(self, cenwid):
        patterns = [self.listbox.item(row).text() for row in xrange(self.listbox.count())]
        cenwid.patterncombo.clear()
        cenwid.patterncombo.addItems(patterns)
        
        
class ComboSetting(HeaderSetting):
    """Class that sets the type of tag that a combo should display
    and what combos should be in the same row.    
    """
    def __init__(self, parent = None, cenwid = None):
        
        settings = QSettings()
        numtitles = settings.beginReadArray("FrameCombo")
        #Default shit
        titles = []
        tags = []
        for z in range(numtitles):
            settings.setArrayIndex(z)
            titles.append(settings.value("titles").toString())
            tags.append(settings.value("tags").toString())
        settings.endArray()
        if not titles:
            titles = ['Artist', 'Title', 'Album', 'Track', u'Year', "Genre", 'Comment']

        if not tags:
            tags = ['artist', 'title', 'album', 'track', u'year', 'genre', 'comment']
        
        newtags = [(unicode(title),unicode(tag)) for title, tag in zip(titles, tags)]
        HeaderSetting.__init__(self, newtags, parent, False)
        self.grid.addWidget(QLabel("You need to restart puddletag for these settings to be applied."),3,0)
        #Get the number of rows
        numrows = settings.beginReadArray("FrameCombo")
        rowcolors = {}
        if numrows <= 0:
            settings = QSettings(":/puddletag.conf",QSettings.IniFormat)
            numrows = settings.beginReadArray("FrameCombo")
        
        for i in range(numrows):
            settings.setArrayIndex(i)
            rowcolor = settings.value('row', QVariant(-1)).toLongLong()[0]
            combos = list([long(z) for z in settings.value("rows").toStringList()])
            rowcolors[rowcolor] = combos
            if rowcolor != -1:
                for z in combos:
                    rowcolor = QColor(rowcolor)
                    self.listbox.item(z).setBackgroundColor(rowcolor)
                    textcolor = (255-rowcolor.red(),255 - rowcolor.green(),255 - rowcolor.blue())
                    self.listbox.item(z).setTextColor(QColor(*textcolor))
        settings.endArray()
        
        if cenwid is not None:
            cenwid.combogroup.setCombos(newtags, rowcolors)
            return
        
        self.samerow = QPushButton("&Samerow")
        self.vboxgrid.addWidget(self.samerow)
        self.connect(self.samerow, SIGNAL("clicked()"), self.sameRow)
    
    def reject(self):
        pass
    
    def sameRow(self):
        """Just picks a random color and sets the selected items that that colour"""
        import random
        color = QColor()
        (r, g, b) = int(255*random.random()), int(255*random.random()), int(255*random.random())
        color.setRgb(r, g, b)
        
        for item in self.listbox.selectedItems():
            item.setBackgroundColor(color)
            textcolor = (255 - color.red(), 255 - color.green(), 255 - color.blue())
            item.setTextColor(QColor(*textcolor))
        
    def saveSettings(self):
        row = self.listbox.currentRow()
        if row > -1:
            self.tags[row][0] = unicode(self.textname.text())
            self.tags[row][1] = unicode(self.tag.text())
        
        settings = QSettings()
        titles = [z[0] for z in self.tags]
        tags = [z[1] for z in self.tags]
        colors = {}
        
        for row in xrange(self.listbox.count()):
            color = self.listbox.item(row).backgroundColor().rgb()
            if color not in colors:
                colors[color] = [row]
            else:
                colors[color].append(row)
        
        settings.beginWriteArray('FrameCombo')
        for i,color in enumerate(colors):
            settings.setArrayIndex(i)
            settings.setValue('row', QVariant(color))
            settings.setValue("rows", QVariant([unicode(z) for z in colors[color]]))
        for i,z in enumerate(titles):
            settings.setArrayIndex(i)
            settings.setValue("titles", QVariant(z))
            settings.setValue("tags", QVariant(tags[i]))
        settings.endArray()
        self.colors = colors
    
    def add(self):
        HeaderSetting.add(self)
        [self.listbox.setItemSelected(item, False) for item in self.listbox.selectedItems()]
        self.listbox.setCurrentRow(self.listbox.count() -1)
        self.sameRow()
        
        
class PlayCommand(QWidget):
    def __init__(self, parent = None, cenwid = None):
        
        settings = QSettings()
        text = [unicode(z) for z in settings.value("Table/playcommand",QVariant(['xmms'])).toStringList()]
        if cenwid is not None:
            cenwid.cenwid.table.setPlayCommand(text)
            return
            
        QWidget.__init__(self, parent)
        self.vbox = QVBoxLayout()
        self.label = QLabel("Enter the command to play files with.")
        self.text= QLineEdit()     
            
        self.text.setText(" ".join(text))
        
        self.vbox.addWidget(self.label)
        self.vbox.addWidget(self.text)
        self.vbox.addStretch()
        self.setLayout(self.vbox)
    
    def applySettings(self, cenwid):
        cenwid.cenwid.table.setPlayCommand(unicode(self.text.text()).split(" "))
    
    def saveSettings(self):
        settings = QSettings()
        settings.setValue("Table/playcommand", QVariant(self.text.text().split(" ")))
        
class GeneralSettings(QWidget):
    def __init__(self, parent = None, cenwid = None):
        def convertstate(state):
            if state == 0:
                return Qt.Unchecked
            else:
                return Qt.Checked

        settings = QSettings()

        vbox = QVBoxLayout()
        self.subfolders = QCheckBox("Subfolders")        
        self.subfolders.setCheckState(convertstate(settings.value('General/subfolders', QVariant(0)).toInt()[0]))
        self.pathinbar = QCheckBox("Show filename in titlebar")
        self.pathinbar.setCheckState(convertstate(settings.value('General/pathinbar', QVariant(1)).toInt()[0]))
        self.gridlines = QCheckBox("Show gridlines")
        self.gridlines.setCheckState(convertstate(settings.value('General/gridlines', QVariant(1)).toInt()[0]))
        self.vertheader = QCheckBox("Show file numbers")
        self.vertheader.setCheckState(convertstate(settings.value('General/vertheader', QVariant(0)).toInt()[0]))
        
        [vbox.addWidget(z) for z in [self.subfolders, self.pathinbar, self.gridlines, self.vertheader]]
        vbox.addStretch()
        
        if cenwid is not None:
            self.applySettings(cenwid)
            return        
        
        QWidget.__init__(self, parent)
        self.setLayout(vbox)
        
    def applySettings(self, cenwid):
        def convertState(checkbox):
            if checkbox.checkState() == Qt.Checked:
                return True
            else:
                return False
            
        cenwid.cenwid.table.subFolders = convertState(self.subfolders)
        cenwid.pathinbar = convertState(self.pathinbar)
        cenwid.cenwid.gridvisible = convertState(self.gridlines)
        if convertState(self.vertheader):
            cenwid.cenwid.table.verticalHeader().show()
        else:            
            cenwid.cenwid.table.verticalHeader().hide()
            
    
    def saveSettings(self):
        settings = QSettings()
        settings.setValue('General/subfolders', QVariant(self.subfolders.checkState()))
        settings.setValue('General/gridlines', QVariant(self.gridlines.checkState()))
        settings.setValue('General/pathinbar', QVariant(self.pathinbar.checkState()))
        settings.setValue('General/vertheader', QVariant(self.vertheader.checkState()))
    
        
class MainWin(QDialog):
    """In order to use a class as an option add it to self.widgets"""
    def __init__(self, cenwid = None, parent = None, readvalues = False):
        QDialog.__init__(self, parent)
        self.setWindowTitle("puddletag settings")
        if readvalues:
            self.combosetting = ComboSetting(parent = self, cenwid = cenwid)
            self.musicplayer = PlayCommand(parent = self, cenwid = cenwid)
            self.gensettings = GeneralSettings(parent = self, cenwid = cenwid)
            self.patterns = PatternEditor(parent = self, cenwid = cenwid)
            return
        
        self.combosetting = ComboSetting()
        self.musicplayer = PlayCommand()
        self.gensettings = GeneralSettings()
        self.patterns = PatternEditor()
        
        self.listbox = SettingsList()
            
        self.widgets = {0: ["General Settings", self.gensettings], 1:["Combos", self.combosetting], 2:["Music Player", self.musicplayer], 3:["Patterns", self.patterns]}
        self.model = ListModel(self.widgets)
        self.listbox.setModel(self.model)
        self.cenwid = cenwid
        
        self.stack = QStackedWidget()
                
        self.grid = QGridLayout()
        self.grid.addWidget(self.listbox)
        self.grid.addWidget(self.stack,0,1)
        self.grid.setColumnStretch(1,2)
        self.setLayout(self.grid)
        
        self.connect(self.listbox, SIGNAL("selectionChanged"), self.showOption)
        
        selection = QItemSelection()
        self.selectionModel= QItemSelectionModel(self.model)
        index = self.model.index(0,0)
        selection.select(index, index)
        self.listbox.setSelectionModel(self.selectionModel)
        self.selectionModel.select(selection, QItemSelectionModel.Select)
        
        self.okbuttons = OKCancel()
        self.okbuttons.ok.setDefault(True)
        self.grid.addLayout(self.okbuttons, 1,0,1,2)
        
        self.connect(self.okbuttons,SIGNAL("ok"), self.saveSettings)
        self.connect(self, SIGNAL("accepted"),self.saveSettings)
        self.connect(self.okbuttons,SIGNAL("cancel"), self.close)
                            
    def showOption(self, option):
        widget = self.widgets[option][1]
        stack = self.stack
        if stack.indexOf(widget) == -1:
            stack.addWidget(widget)
        stack.setCurrentWidget(widget)
        if self.width() < self.sizeHint().width():
            self.setMinimumWidth(self.sizeHint().width())
    
    def saveSettings(self):
        for z in self.widgets.values():
            z[1].saveSettings()
            try:
                z[1].applySettings(self.cenwid)
            except AttributeError:
                pass
                #sys.stderr.write(z[0] + " doesn't have a settings applySettings method.\n")
        self.close()

if __name__ == "__main__":
    app=QApplication(sys.argv)
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")   
    qb=MainWin()
    qb.show()
    app.exec_()
        
        
        
    