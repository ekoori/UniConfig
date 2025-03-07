#!/usr/bin/env python3

#******************************************************************************
# treemaincontrol.py, provides a class for global tree commands
#
# TreeLine, an information storage program
# Copyright (C) 2023, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY.  See the included LICENSE file for details.
#******************************************************************************

import sys
import pathlib
import os.path
import ast
import io
import gzip
import zlib
import datetime
import platform
from PyQt5.QtCore import QIODevice, QObject, Qt, PYQT_VERSION_STR, qVersion
from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import (QAction, QApplication, QDialog, QFileDialog,
                             QMessageBox, QStyleFactory, QSystemTrayIcon, qApp)
import globalref
import treelocalcontrol
import options
import optiondefaults
import recentfiles
import p3
import icondict
import imports
import configdialog
import miscdialogs
import conditional
import colorset
import helpview
import agentinterface
try:
    from __main__ import __version__, __author__
except ImportError:
    __version__ = ''
    __author__ = ''
try:
    from __main__ import docPath, iconPath, templatePath, samplePath
except ImportError:
    docPath = None
    iconPath = None
    templatePath = None
    samplePath = None

encryptPrefix = b'>>TL+enc'


class TreeMainControl(QObject):
    """Class to handle all global controls.

    Provides methods for all controls and stores local control objects.
    """
    def __init__(self, pathObjects, parent=None):
        """Initialize the main tree controls

        Arguments:
            pathObjects -- a list of file objects to open
            parent -- the parent QObject if given
        """
        super().__init__(parent)
        self.localControls = []
        self.activeControl = None
        self.trayIcon = None
        self.isTrayMinimized = False
        self.configDialog = None
        self.sortDialog = None
        self.numberingDialog = None
        self.findTextDialog = None
        self.findConditionDialog = None
        self.findReplaceDialog = None
        self.filterTextDialog = None
        self.filterConditionDialog = None
        self.aiAgentDialog = None
        self.basicHelpView = None
        self.passwords = {}
        self.creatingLocalControlFlag = False
        globalref.mainControl = self
        self.allActions = {}
        try:
            # check for existing TreeLine session
            socket = QLocalSocket()
            socket.connectToServer('treeline3-session',
                                   QIODevice.WriteOnly)
            # if found, send files to open and exit TreeLine
            if socket.waitForConnected(1000):
                socket.write(bytes(repr([str(path) for path in pathObjects]),
                                   'utf-8'))
                if socket.waitForBytesWritten(1000):
                    socket.close()
                    sys.exit(0)
            # start local server to listen for attempt to start new session
            self.serverSocket = QLocalServer()
            # remove any old servers still around after a crash in linux
            self.serverSocket.removeServer('treeline3-session')
            self.serverSocket.listen('treeline3-session')
            self.serverSocket.newConnection.connect(self.getSocket)
        except AttributeError:
            print(_('Warning:  Could not create local socket'))
        mainVersion = '.'.join(__version__.split('.')[:2])
        globalref.genOptions = options.Options('general', 'TreeLine',
                                               mainVersion, 'bellz')
        optiondefaults.setGenOptionDefaults(globalref.genOptions)
        globalref.miscOptions  = options.Options('misc')
        optiondefaults.setMiscOptionDefaults(globalref.miscOptions)
        globalref.histOptions = options.Options('history')
        optiondefaults.setHistOptionDefaults(globalref.histOptions)
        globalref.toolbarOptions = options.Options('toolbar')
        optiondefaults.setToolbarOptionDefaults(globalref.toolbarOptions)
        globalref.keyboardOptions = options.Options('keyboard')
        optiondefaults.setKeyboardOptionDefaults(globalref.keyboardOptions)
        try:
            globalref.genOptions.readFile()
            globalref.miscOptions.readFile()
            globalref.histOptions.readFile()
            globalref.toolbarOptions.readFile()
            globalref.keyboardOptions.readFile()
        except IOError:
            errorDir = options.Options.basePath
            if not errorDir:
                errorDir = _('missing directory')
            QMessageBox.warning(None, 'TreeLine',
                                _('Error - could not write config file to {}').
                                format(errorDir))
            options.Options.basePath = None
        iconPathList = self.findResourcePaths('icons', iconPath)
        globalref.toolIcons = icondict.IconDict([path / 'toolbar' for path
                                                 in iconPathList],
                                                ['', '32x32', '16x16'])
        globalref.toolIcons.loadAllIcons()
        windowIcon = globalref.toolIcons.getIcon('treelogo')
        if windowIcon:
            QApplication.setWindowIcon(windowIcon)
        globalref.treeIcons = icondict.IconDict(iconPathList, ['', 'tree'])
        icon = globalref.treeIcons.getIcon('default')
        qApp.setStyle(QStyleFactory.create('Fusion'))
        self.colorSet = colorset.ColorSet()
        if globalref.miscOptions['ColorTheme'] != 'system':
            self.colorSet.setAppColors()
        self.recentFiles = recentfiles.RecentFileList()
        if globalref.genOptions['AutoFileOpen'] and not pathObjects:
            recentPath = self.recentFiles.firstPath()
            if recentPath:
                pathObjects = [recentPath]
        self.setupActions()
        self.systemFont = QApplication.font()
        self.updateAppFont()
        if globalref.genOptions['MinToSysTray']:
            self.createTrayIcon()
        qApp.focusChanged.connect(self.updateActionsAvail)
        if pathObjects:
            for pathObj in pathObjects:
                self.openFile(pathObj, True)
        else:
            self.createLocalControl()

    def getSocket(self):
        """Open a socket from an attempt to open a second Treeline instance.

        Opens the file (or raise and focus if open) in this instance.
        """
        socket = self.serverSocket.nextPendingConnection()
        if socket and socket.waitForReadyRead(1000):
            data = str(socket.readAll(), 'utf-8')
            try:
                paths = ast.literal_eval(data)
                if paths:
                    for path in paths:
                        pathObj = pathlib.Path(path)
                        if pathObj != self.activeControl.filePathObj:
                            self.openFile(pathObj, True)
                        else:
                            self.activeControl.activeWindow.activateAndRaise()
                else:
                    self.activeControl.activeWindow.activateAndRaise()
            except(SyntaxError, ValueError, TypeError, RuntimeError):
                pass

    def findResourcePaths(self, resourceName, preferredPath=''):
        """Return list of potential non-empty pathlib objects for the resource.

        List includes preferred, module and user option paths.
        Arguments:
            resourceName -- the typical name of the resource directory
            preferredPath -- add this as the second path if given
        """
        # use abspath() - pathlib's resolve() can be buggy with network drives
        modPath = pathlib.Path(os.path.abspath(sys.path[0]))
        if modPath.is_file():
            modPath = modPath.parent    # for frozen binary
        pathList = [modPath / '..' / resourceName, modPath / resourceName]
        if options.Options.basePath:
            basePath = pathlib.Path(options.Options.basePath)
            pathList.insert(0, basePath / resourceName)
        if preferredPath:
            pathList.insert(1, pathlib.Path(preferredPath))
        return [pathlib.Path(os.path.abspath(str(path))) for path in pathList
                if path.is_dir() and list(path.iterdir())]

    def findResourceFile(self, fileName, resourceName, preferredPath=''):
        """Return a path object for a resource file.

        Add a language code before the extension if it exists.
        Arguments:
            fileName -- the name of the file to find
            resourceName -- the typical name of the resource directory
            preferredPath -- search this path first if given
        """
        fileList = [fileName]
        if globalref.lang and globalref.lang != 'C':
            fileList[0:0] = [fileName.replace('.', '_{0}.'.
                                              format(globalref.lang)),
                             fileName.replace('.', '_{0}.'.
                                              format(globalref.lang[:2]))]
        for fileName in fileList:
            for path in self.findResourcePaths(resourceName, preferredPath):
                if (path / fileName).is_file():
                    return path / fileName
        return None

    def defaultPathObj(self, dirOnly=False):
        """Return a reasonable default file path object.

        Used for open, save-as, import and export.
        Arguments:
            dirOnly -- if True, do not include basename of file
        """
        pathObj = None
        if  self.activeControl:
            pathObj = self.activeControl.filePathObj
        if not pathObj:
            pathObj = self.recentFiles.firstDir()
            if not pathObj:
                pathObj = pathlib.Path.home()
        if dirOnly:
            pathObj = pathObj.parent
        return pathObj

    def openFile(self, pathObj, forceNewWindow=False, checkModified=False,
                 importOnFail=True):
        """Open the file given by path if not already open.

        If already open in a different window, focus and raise the window.
        Arguments:
            pathObj -- the path object to read
            forceNewWindow -- if True, use a new window regardless of option
            checkModified -- if True & not new win, prompt if file modified
            importOnFail -- if True, prompts for import on non-TreeLine files
        """
        match = [control for control in self.localControls if
                 pathObj == control.filePathObj]
        if match and self.activeControl not in match:
            control = match[0]
            control.activeWindow.activateAndRaise()
            self.updateLocalControlRef(control)
            return
        if checkModified and not (forceNewWindow or
                                  globalref.genOptions['OpenNewWindow'] or
                                  self.activeControl.checkSaveChanges()):
            return
        if not self.checkAutoSave(pathObj):
            if not self.localControls:
                self.createLocalControl()
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            fileModTime = datetime.datetime.fromtimestamp(pathObj.stat().
                                                          st_mtime)
            self.createLocalControl(pathObj, None, forceNewWindow, fileModTime)
            self.recentFiles.addItem(pathObj)
            if not (globalref.genOptions['SaveTreeStates'] and
                    self.recentFiles.retrieveTreeState(self.activeControl)):
                self.activeControl.expandRootNodes()
                self.activeControl.selectRootSpot()
            QApplication.restoreOverrideCursor()
        except IOError:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(QApplication.activeWindow(), 'TreeLine',
                                _('Error - could not read file {0}').
                                format(pathObj))
            self.recentFiles.removeItem(pathObj)
        except (ValueError, KeyError, TypeError):
            fileObj = pathObj.open('rb')
            fileObj, encrypted = self.decryptFile(fileObj)
            if not fileObj:
                if not self.localControls:
                    self.createLocalControl()
                QApplication.restoreOverrideCursor()
                return
            fileObj, compressed = self.decompressFile(fileObj)
            if compressed or encrypted:
                try:
                    textFileObj = io.TextIOWrapper(fileObj, encoding='utf-8')
                    self.createLocalControl(textFileObj, None, forceNewWindow,
                                            fileModTime)
                    fileObj.close()
                    textFileObj.close()
                    self.recentFiles.addItem(pathObj)
                    if not (globalref.genOptions['SaveTreeStates'] and
                            self.recentFiles.retrieveTreeState(self.
                                                               activeControl)):
                        self.activeControl.expandRootNodes()
                        self.activeControl.selectRootSpot()
                    self.activeControl.compressed = compressed
                    self.activeControl.encrypted = encrypted
                    QApplication.restoreOverrideCursor()
                    return
                except (ValueError, KeyError, TypeError):
                    pass
            fileObj.close()
            importControl = imports.ImportControl(pathObj)
            structure = importControl.importOldTreeLine()
            if structure:
                self.createLocalControl(pathObj, structure, forceNewWindow)
                self.activeControl.printData.readData(importControl.
                                                      treeLineRootAttrib)
                self.recentFiles.addItem(pathObj)
                self.activeControl.expandRootNodes()
                self.activeControl.imported = True
                QApplication.restoreOverrideCursor()
                return
            QApplication.restoreOverrideCursor()
            if importOnFail:
                importControl = imports.ImportControl(pathObj)
                structure = importControl.interactiveImport(True)
                if structure:
                    self.createLocalControl(pathObj, structure, forceNewWindow)
                    self.activeControl.imported = True
                    return
            else:
                QMessageBox.warning(QApplication.activeWindow(), 'TreeLine',
                                    _('Error - invalid TreeLine file {0}').
                                    format(pathObj))
                self.recentFiles.removeItem(pathObj)
        if not self.localControls:
            self.createLocalControl()

    def decryptFile(self, fileObj):
        """Check for encryption and decrypt the fileObj if needed.

        Return a tuple of the file object and True if it was encrypted.
        Return None for the file object if the user cancels.
        Arguments:
            fileObj -- the file object to check and decrypt
        """
        if fileObj.read(len(encryptPrefix)) != encryptPrefix:
            fileObj.seek(0)
            return (fileObj, False)
        fileContents = fileObj.read()
        fileName = fileObj.name
        fileObj.close()
        while True:
            pathObj = pathlib.Path(fileName)
            password = self.passwords.get(pathObj, '')
            if not password:
                QApplication.restoreOverrideCursor()
                dialog = miscdialogs.PasswordDialog(False, pathObj.name,
                                                    QApplication.
                                                    activeWindow())
                if dialog.exec_() != QDialog.Accepted:
                    return (None, True)
                QApplication.setOverrideCursor(Qt.WaitCursor)
                password = dialog.password
                if miscdialogs.PasswordDialog.remember:
                    self.passwords[pathObj] = password
            try:
                text = p3.p3_decrypt(fileContents, password.encode())
                fileIO = io.BytesIO(text)
                fileIO.name = fileName
                return (fileIO, True)
            except p3.CryptError:
                try:
                    del self.passwords[pathObj]
                except KeyError:
                    pass

    def decompressFile(self, fileObj):
        """Check for compression and decompress the fileObj if needed.

        Return a tuple of the file object and True if it was compressed.
        Arguments:
            fileObj -- the file object to check and decompress
        """
        prefix = fileObj.read(2)
        fileObj.seek(0)
        if prefix != b'\037\213':
            return (fileObj, False)
        try:
            newFileObj = gzip.GzipFile(fileobj=fileObj)
        except zlib.error:
            return (fileObj, False)
        newFileObj.name = fileObj.name
        return (newFileObj, True)

    def checkAutoSave(self, pathObj):
        """Check for presence of auto save file & prompt user.

        Return True if OK to contimue, False if aborting or already loaded.
        Arguments:
            pathObj -- the base path object to search for a backup
        """
        if not globalref.genOptions['AutoSaveMinutes']:
            return True
        basePath = pathObj
        pathObj = pathlib.Path(str(pathObj) + '~')
        if not pathObj.is_file():
            return True
        msgBox = QMessageBox(QMessageBox.Information, 'TreeLine',
                             _('Backup file "{}" exists.\nA previous '
                               'session may have crashed').
                             format(pathObj), QMessageBox.NoButton,
                             QApplication.activeWindow())
        restoreButton = msgBox.addButton(_('&Restore Backup'),
                                         QMessageBox.ApplyRole)
        deleteButton = msgBox.addButton(_('&Delete Backup'),
                                        QMessageBox.DestructiveRole)
        cancelButton = msgBox.addButton(_('&Cancel File Open'),
                                        QMessageBox.RejectRole)
        msgBox.exec_()
        if msgBox.clickedButton() == restoreButton:
            self.openFile(pathObj)
            if self.activeControl.filePathObj != pathObj:
                return False
            try:
                basePath.unlink()
                pathObj.rename(basePath)
            except OSError:
                QMessageBox.warning(QApplication.activeWindow(),
                                  'TreeLine',
                                  _('Error - could not rename "{0}" to "{1}"').
                                  format(pathObj, basePath))
                return False
            self.activeControl.filePathObj = basePath
            self.activeControl.updateWindowCaptions()
            self.recentFiles.removeItem(pathObj)
            self.recentFiles.addItem(basePath)
            return False
        elif msgBox.clickedButton() == deleteButton:
            try:
                pathObj.unlink()
            except OSError:
                QMessageBox.warning(QApplication.activeWindow(),
                                  'TreeLine',
                                  _('Error - could not remove backup file {}').
                                  format(pathObj))
        else:   # cancel button
            return False
        return True

    def createLocalControl(self, pathObj=None, treeStruct=None,
                           forceNewWindow=False, fileModTime=None):
        """Create a new local control object and add it to the list.

        Use an imported structure if given or open the file if path is given.
        Arguments:
            pathObj -- the path object or file object for the control to open
            treeStruct -- the imported structure to use
            forceNewWindow -- if True, use a new window regardless of option
            fileModTime -- file modified time for external modification checks
        """
        self.creatingLocalControlFlag = True
        localControl = treelocalcontrol.TreeLocalControl(self.allActions,
                                                         pathObj, treeStruct,
                                                         fileModTime,
                                                         forceNewWindow)
        localControl.controlActivated.connect(self.updateLocalControlRef)
        localControl.controlClosed.connect(self.removeLocalControlRef)
        self.localControls.append(localControl)
        self.updateLocalControlRef(localControl)
        self.creatingLocalControlFlag = False
        localControl.updateRightViews()
        localControl.updateCommandsAvail()

    def updateLocalControlRef(self, localControl):
        """Set the given local control as active.

        Called by signal from a window becoming active.
        Also updates non-modal dialogs.
        Arguments:
            localControl -- the new active local control
        """
        if localControl != self.activeControl:
            self.activeControl = localControl
            if self.configDialog and self.configDialog.isVisible():
                self.configDialog.setRefs(self.activeControl)

    def removeLocalControlRef(self, localControl):
        """Remove ref to local control based on a closing signal.

        Also do application exit clean ups if last control closing.
        Arguments:
            localControl -- the local control that is closing
        """
        try:
            self.localControls.remove(localControl)
        except ValueError:
            return  # skip for unreporducible bug - odd race condition?
        if globalref.genOptions['SaveTreeStates']:
            self.recentFiles.saveTreeState(localControl)
        if not self.localControls and not self.creatingLocalControlFlag:
            if globalref.genOptions['SaveWindowGeom']:
                localControl.windowList[0].saveWindowGeom()
            else:
                localControl.windowList[0].resetWindowGeom()
            self.recentFiles.writeItems()
            localControl.windowList[0].saveToolbarPosition()
            globalref.histOptions.writeFile()
            if self.trayIcon:
                self.trayIcon.hide()
            # stop listening for session connections
            try:
                self.serverSocket.close()
                del self.serverSocket
            except AttributeError:
                pass
        if self.localControls:
            # make sure a window is active (may not be focused), to avoid
            # bugs due to a deleted current window
            newControl = self.localControls[0]
            newControl.setActiveWin(newControl.windowList[0])
        localControl.deleteLater()

    def createTrayIcon(self):
        """Create a new system tray icon if not already created.
        """
        if QSystemTrayIcon.isSystemTrayAvailable:
            if not self.trayIcon:
                self.trayIcon = QSystemTrayIcon(qApp.windowIcon(), qApp)
                self.trayIcon.activated.connect(self.toggleTrayShow)
            self.trayIcon.show()

    def trayMinimize(self):
        """Minimize to tray based on window minimize signal.
        """
        if self.trayIcon and QSystemTrayIcon.isSystemTrayAvailable:
            # skip minimize to tray if not all windows minimized
            for control in self.localControls:
                for window in control.windowList:
                    if not window.isMinimized():
                        return
            for control in self.localControls:
                for window in control.windowList:
                    window.hide()
            self.isTrayMinimized = True

    def toggleTrayShow(self):
        """Toggle show and hide application based on system tray icon click.
        """
        if self.isTrayMinimized:
            for control in self.localControls:
                for window in control.windowList:
                    window.show()
                    window.showNormal()
            self.activeControl.activeWindow.treeView.setFocus()
        else:
            for control in self.localControls:
                for window in control.windowList:
                    window.hide()
        self.isTrayMinimized = not self.isTrayMinimized

    def updateConfigDialog(self):
        """Update the config dialog for changes if it exists.
        """
        if self.configDialog:
            self.configDialog.reset()

    def currentStatusBar(self):
        """Return the status bar from the current main window.
        """
        return self.activeControl.activeWindow.statusBar()

    def windowActions(self):
        """Return a list of window menu actions from each local control.
        """
        actions = []
        for control in self.localControls:
            actions.extend(control.windowActions(len(actions) + 1,
                                                control == self.activeControl))
        return actions

    def updateActionsAvail(self, oldWidget, newWidget):
        """Update command availability based on focus changes.

        Arguments:
            oldWidget -- the previously focused widget
            newWidget -- the newly focused widget
        """
        self.allActions['FormatSelectAll'].setEnabled(hasattr(newWidget,
                                                              'selectAll') and
                                                    not hasattr(newWidget,
                                                               'editTriggers'))

    def setupActions(self):
        """Add the actions for contols at the global level.
        """
        fileNewAct = QAction(_('&New...'), self, toolTip=_('New File'),
                             statusTip=_('Start a new file'))
        fileNewAct.triggered.connect(self.fileNew)
        self.allActions['FileNew'] = fileNewAct

        fileOpenAct = QAction(_('&Open...'), self, toolTip=_('Open File'),
                              statusTip=_('Open a file from disk'))
        fileOpenAct.triggered.connect(self.fileOpen)
        self.allActions['FileOpen'] = fileOpenAct

        fileSampleAct = QAction(_('Open Sa&mple...'), self,
                                      toolTip=_('Open Sample'),
                                      statusTip=_('Open a sample file'))
        fileSampleAct.triggered.connect(self.fileOpenSample)
        self.allActions['FileOpenSample'] = fileSampleAct

        fileImportAct = QAction(_('&Import...'), self,
                                      statusTip=_('Open a non-TreeLine file'))
        fileImportAct.triggered.connect(self.fileImport)
        self.allActions['FileImport'] = fileImportAct

        fileQuitAct = QAction(_('&Quit'), self,
                              statusTip=_('Exit the application'))
        fileQuitAct.triggered.connect(self.fileQuit)
        self.allActions['FileQuit'] = fileQuitAct

        dataConfigAct = QAction(_('&Configure Data Types...'), self,
                       statusTip=_('Modify data types, fields & output lines'),
                       checkable=True)
        dataConfigAct.triggered.connect(self.dataConfigDialog)
        self.allActions['DataConfigType'] = dataConfigAct

        dataVisualConfigAct = QAction(_('Show C&onfiguration Structure...'),
                 self,
                 statusTip=_('Show read-only visualization of type structure'))
        dataVisualConfigAct.triggered.connect(self.dataVisualConfig)
        self.allActions['DataVisualConfig'] = dataVisualConfigAct

        dataSortAct = QAction(_('Sor&t Nodes...'), self,
                                    statusTip=_('Define node sort operations'),
                                    checkable=True)
        dataSortAct.triggered.connect(self.dataSortDialog)
        self.allActions['DataSortNodes'] = dataSortAct

        dataNumberingAct = QAction(_('Update &Numbering...'), self,
                                   statusTip=_('Update node numbering fields'),
                                   checkable=True)
        dataNumberingAct.triggered.connect(self.dataNumberingDialog)
        self.allActions['DataNumbering'] = dataNumberingAct

        toolsFindTextAct = QAction(_('&Find Text...'), self,
                                statusTip=_('Find text in node titles & data'),
                                checkable=True)
        toolsFindTextAct.triggered.connect(self.toolsFindTextDialog)
        self.allActions['ToolsFindText'] = toolsFindTextAct

        toolsFindConditionAct = QAction(_('&Conditional Find...'), self,
                             statusTip=_('Use field conditions to find nodes'),
                             checkable=True)
        toolsFindConditionAct.triggered.connect(self.toolsFindConditionDialog)
        self.allActions['ToolsFindCondition'] = toolsFindConditionAct

        toolsFindReplaceAct = QAction(_('Find and &Replace...'), self,
                              statusTip=_('Replace text strings in node data'),
                              checkable=True)
        toolsFindReplaceAct.triggered.connect(self.toolsFindReplaceDialog)
        self.allActions['ToolsFindReplace'] = toolsFindReplaceAct

        toolsFilterTextAct = QAction(_('&Text Filter...'), self,
                         statusTip=_('Filter nodes to only show text matches'),
                         checkable=True)
        toolsFilterTextAct.triggered.connect(self.toolsFilterTextDialog)
        self.allActions['ToolsFilterText'] = toolsFilterTextAct

        toolsFilterConditionAct = QAction(_('C&onditional Filter...'),
                           self,
                           statusTip=_('Use field conditions to filter nodes'),
                           checkable=True)
        toolsFilterConditionAct.triggered.connect(self.
                                                  toolsFilterConditionDialog)
        self.allActions['ToolsFilterCondition'] = toolsFilterConditionAct
        
        toolsAIAgentAct = QAction(_('&AI Assistant...'), self,
                       statusTip=_('Open the AI assistant dialog'),
                       checkable=True)
        toolsAIAgentAct.triggered.connect(self.toolsAIAgentDialog)
        self.allActions['ToolsAIAgent'] = toolsAIAgentAct

        toolsGenOptionsAct = QAction(_('&General Options...'), self,
                             statusTip=_('Set user preferences for all files'))
        toolsGenOptionsAct.triggered.connect(self.toolsGenOptions)
        self.allActions['ToolsGenOptions'] = toolsGenOptionsAct

        toolsShortcutAct = QAction(_('Set &Keyboard Shortcuts...'), self,
                                    statusTip=_('Customize keyboard commands'))
        toolsShortcutAct.triggered.connect(self.toolsCustomShortcuts)
        self.allActions['ToolsShortcuts'] = toolsShortcutAct

        toolsToolbarAct = QAction(_('C&ustomize Toolbars...'), self,
                                     statusTip=_('Customize toolbar buttons'))
        toolsToolbarAct.triggered.connect(self.toolsCustomToolbars)
        self.allActions['ToolsToolbars'] = toolsToolbarAct

        toolsFontsAct = QAction(_('Customize Fo&nts...'), self,
                               statusTip=_('Customize fonts in various views'))
        toolsFontsAct.triggered.connect(self.toolsCustomFonts)
        self.allActions['ToolsFonts'] = toolsFontsAct

        toolsColorsAct = QAction(_('Custo&mize Colors...'), self,
                                statusTip=_('Customize GUI colors and themes'))
        toolsColorsAct.triggered.connect(self.toolsCustomColors)
        self.allActions['ToolsColors'] = toolsColorsAct

        formatSelectAllAct =  QAction(_('&Select All'), self,
                                   statusTip=_('Select all text in an editor'))
        formatSelectAllAct.setEnabled(False)
        formatSelectAllAct.triggered.connect(self.formatSelectAll)
        self.allActions['FormatSelectAll'] = formatSelectAllAct

        helpBasicAct = QAction(_('&Basic Usage...'), self,
                               statusTip=_('Display basic usage instructions'))
        helpBasicAct.triggered.connect(self.helpViewBasic)
        self.allActions['HelpBasic'] = helpBasicAct

        helpFullAct = QAction(_('&Full Documentation...'), self,
                   statusTip=_('Open a TreeLine file with full documentation'))
        helpFullAct.triggered.connect(self.helpViewFull)
        self.allActions['HelpFull'] = helpFullAct

        helpAboutAct = QAction(_('&About TreeLine...'), self,
                        statusTip=_('Display version info about this program'))
        helpAboutAct.triggered.connect(self.helpAbout)
        self.allActions['HelpAbout'] = helpAboutAct

        for name, action in self.allActions.items():
            icon = globalref.toolIcons.getIcon(name.lower())
            if icon:
                action.setIcon(icon)
            key = globalref.keyboardOptions[name]
            if not key.isEmpty():
                action.setShortcut(key)

    def fileNew(self):
        """Start a new blank file.
        """
        if (globalref.genOptions['OpenNewWindow'] or
            self.activeControl.checkSaveChanges()):
            searchPaths = self.findResourcePaths('templates', templatePath)
            if searchPaths:
                dialog = miscdialogs.TemplateFileDialog(_('New File'),
                                                        _('&Select Template'),
                                                        searchPaths)
                if dialog.exec_() == QDialog.Accepted:
                    self.createLocalControl(dialog.selectedPath())
                    self.activeControl.filePathObj = None
                    self.activeControl.updateWindowCaptions()
                    self.activeControl.expandRootNodes()
            else:
                self.createLocalControl()
            self.activeControl.selectRootSpot()

    def fileOpen(self):
        """Prompt for a filename and open it.
        """
        if (globalref.genOptions['OpenNewWindow'] or
            self.activeControl.checkSaveChanges()):
            filters = ';;'.join((globalref.fileFilters['trlnopen'],
                                 globalref.fileFilters['all']))
            fileName, selFilter = QFileDialog.getOpenFileName(QApplication.
                                                activeWindow(),
                                                _('TreeLine - Open File'),
                                                str(self.defaultPathObj(True)),
                                                filters)
            if fileName:
                self.openFile(pathlib.Path(fileName))

    def fileOpenSample(self):
        """Open a sample file from the doc directories.
        """
        if (globalref.genOptions['OpenNewWindow'] or
            self.activeControl.checkSaveChanges()):
            searchPaths = self.findResourcePaths('samples', samplePath)
            dialog = miscdialogs.TemplateFileDialog(_('Open Sample File'),
                                                    _('&Select Sample'),
                                                    searchPaths, False)
            if dialog.exec_() == QDialog.Accepted:
                self.createLocalControl(dialog.selectedPath())
                name = dialog.selectedName() + '.trln'
                self.activeControl.filePathObj = pathlib.Path(name)
                self.activeControl.updateWindowCaptions()
                self.activeControl.expandRootNodes()
                self.activeControl.imported = True

    def fileImport(self):
        """Prompt for an import type, then a file to import.
        """
        importControl = imports.ImportControl()
        structure = importControl.interactiveImport()
        if structure:
            self.createLocalControl(importControl.pathObj, structure)
            if importControl.treeLineRootAttrib:
                self.activeControl.printData.readData(importControl.
                                                      treeLineRootAttrib)
            self.activeControl.imported = True

    def fileQuit(self):
        """Close all windows to exit the applications.
        """
        for control in self.localControls[:]:
            control.closeWindows()

    def dataConfigDialog(self, show):
        """Show or hide the non-modal data config dialog.

        Arguments:
            show -- true if dialog should be shown, false to hide it
        """
        if show:
            if not self.configDialog:
                self.configDialog = configdialog.ConfigDialog()
                dataConfigAct = self.allActions['DataConfigType']
                self.configDialog.dialogShown.connect(dataConfigAct.setChecked)
            self.configDialog.setRefs(self.activeControl, True)
            self.configDialog.show()
        else:
            self.configDialog.close()

    def dataVisualConfig(self):
        """Show a TreeLine file to visualize the config structure.
        """
        structure = (self.activeControl.structure.treeFormats.
                     visualConfigStructure(str(self.activeControl.
                                               filePathObj)))
        self.createLocalControl(treeStruct=structure, forceNewWindow=True)
        self.activeControl.filePathObj = pathlib.Path('structure.trln')
        self.activeControl.updateWindowCaptions()
        self.activeControl.expandRootNodes()
        self.activeControl.imported = True
        win = self.activeControl.activeWindow
        win.rightTabs.setCurrentWidget(win.outputSplitter)

    def dataSortDialog(self, show):
        """Show or hide the non-modal data sort nodes dialog.

        Arguments:
            show -- true if dialog should be shown, false to hide it
        """
        if show:
            if not self.sortDialog:
                self.sortDialog = miscdialogs.SortDialog()
                dataSortAct = self.allActions['DataSortNodes']
                self.sortDialog.dialogShown.connect(dataSortAct.setChecked)
            self.sortDialog.show()
        else:
            self.sortDialog.close()

    def dataNumberingDialog(self, show):
        """Show or hide the non-modal update node numbering dialog.

        Arguments:
            show -- true if dialog should be shown, false to hide it
        """
        if show:
            if not self.numberingDialog:
                self.numberingDialog = miscdialogs.NumberingDialog()
                dataNumberingAct = self.allActions['DataNumbering']
                self.numberingDialog.dialogShown.connect(dataNumberingAct.
                                                         setChecked)
            self.numberingDialog.show()
            if not self.numberingDialog.checkForNumberingFields():
                self.numberingDialog.close()
        else:
            self.numberingDialog.close()

    def toolsFindTextDialog(self, show):
        """Show or hide the non-modal find text dialog.

        Arguments:
            show -- true if dialog should be shown
        """
        if show:
            if not self.findTextDialog:
                self.findTextDialog = miscdialogs.FindFilterDialog()
                toolsFindTextAct = self.allActions['ToolsFindText']
                self.findTextDialog.dialogShown.connect(toolsFindTextAct.
                                                        setChecked)
            self.findTextDialog.selectAllText()
            self.findTextDialog.show()
        else:
            self.findTextDialog.close()

    def toolsFindConditionDialog(self, show):
        """Show or hide the non-modal conditional find dialog.

        Arguments:
            show -- true if dialog should be shown
        """
        if show:
            if not self.findConditionDialog:
                dialogType = conditional.FindDialogType.findDialog
                self.findConditionDialog = (conditional.
                                            ConditionDialog(dialogType,
                                                        _('Conditional Find')))
                toolsFindConditionAct = self.allActions['ToolsFindCondition']
                (self.findConditionDialog.dialogShown.
                 connect(toolsFindConditionAct.setChecked))
            else:
                self.findConditionDialog.loadTypeNames()
            self.findConditionDialog.show()
        else:
            self.findConditionDialog.close()

    def toolsFindReplaceDialog(self, show):
        """Show or hide the non-modal find and replace text dialog.

        Arguments:
            show -- true if dialog should be shown
        """
        if show:
            if not self.findReplaceDialog:
                self.findReplaceDialog = miscdialogs.FindReplaceDialog()
                toolsFindReplaceAct = self.allActions['ToolsFindReplace']
                self.findReplaceDialog.dialogShown.connect(toolsFindReplaceAct.
                                                           setChecked)
            else:
                self.findReplaceDialog.loadTypeNames()
            self.findReplaceDialog.show()
        else:
            self.findReplaceDialog.close()

    def toolsFilterTextDialog(self, show):
        """Show or hide the non-modal filter text dialog.

        Arguments:
            show -- true if dialog should be shown
        """
        if show:
            if not self.filterTextDialog:
                self.filterTextDialog = miscdialogs.FindFilterDialog(True)
                toolsFilterTextAct = self.allActions['ToolsFilterText']
                self.filterTextDialog.dialogShown.connect(toolsFilterTextAct.
                                                          setChecked)
            self.filterTextDialog.selectAllText()
            self.filterTextDialog.show()
        else:
            self.filterTextDialog.close()

    def toolsFilterConditionDialog(self, show):
        """Show or hide the non-modal conditional filter dialog.

        Arguments:
            show -- true if dialog should be shown
        """
        if show:
            if not self.filterConditionDialog:
                dialogType = conditional.FindDialogType.filterDialog
                self.filterConditionDialog = (conditional.
                                              ConditionDialog(dialogType,
                                                      _('Conditional Filter')))
                toolsFilterConditionAct = (self.
                                           allActions['ToolsFilterCondition'])
                (self.filterConditionDialog.dialogShown.
                 connect(toolsFilterConditionAct.setChecked))
            else:
                self.filterConditionDialog.loadTypeNames()
            self.filterConditionDialog.show()
        else:
            self.filterConditionDialog.close()
            
    def toolsAIAgentDialog(self, show):
        """Show or hide the non-modal AI agent dialog.
        
        Arguments:
            show -- true if dialog should be shown, false to hide it
        """
        if show:
            if not self.aiAgentDialog:
                self.aiAgentDialog = agentinterface.AgentDialog(self.activeControl)
                toolsAIAgentAct = self.allActions['ToolsAIAgent']
                self.aiAgentDialog.dialogShown = self.aiAgentDialog.finished
                self.aiAgentDialog.dialogShown.connect(lambda: 
                                                     toolsAIAgentAct.setChecked(False))
            self.aiAgentDialog.show()
        else:
            self.aiAgentDialog.close()

    def toolsGenOptions(self):
        """Set general user preferences for all files.
        """
        oldAutoSaveMinutes = globalref.genOptions['AutoSaveMinutes']
        dialog = options.OptionDialog(globalref.genOptions,
                                      QApplication.activeWindow())
        dialog.setWindowTitle(_('General Options'))
        if (dialog.exec_() == QDialog.Accepted and
            globalref.genOptions.modified):
            globalref.genOptions.writeFile()
            self.recentFiles.updateOptions()
            if globalref.genOptions['MinToSysTray']:
                self.createTrayIcon()
            elif self.trayIcon:
                self.trayIcon.hide()
            autoSaveMinutes = globalref.genOptions['AutoSaveMinutes']
            for control in self.localControls:
                for window in control.windowList:
                    window.updateWinGenOptions()
                control.structure.undoList.setNumLevels()
                control.updateAll(False)
                if autoSaveMinutes != oldAutoSaveMinutes:
                    control.resetAutoSave()

    def toolsCustomShortcuts(self):
        """Show dialog to customize keyboard commands.
        """
        actions = self.activeControl.activeWindow.allActions
        dialog = miscdialogs.CustomShortcutsDialog(actions, QApplication.
                                                   activeWindow())
        dialog.exec_()

    def toolsCustomToolbars(self):
        """Show dialog to customize toolbar buttons.
        """
        actions = self.activeControl.activeWindow.allActions
        dialog = miscdialogs.CustomToolbarDialog(actions, self.updateToolbars,
                                                 QApplication.
                                                 activeWindow())
        dialog.exec_()

    def updateToolbars(self):
        """Update toolbars after changes in custom toolbar dialog.
        """
        for control in self.localControls:
            for window in control.windowList:
                window.setupToolbars()

    def toolsCustomFonts(self):
        """Show dialog to customize fonts in various views.
        """
        dialog = miscdialogs.CustomFontDialog(QApplication.
                                              activeWindow())
        dialog.updateRequired.connect(self.updateCustomFonts)
        dialog.exec_()

    def toolsCustomColors(self):
        """Show dialog to customize GUI colors ans themes.
        """
        self.colorSet.showDialog(QApplication.activeWindow())

    def updateCustomFonts(self):
        """Update fonts in all windows based on a dialog signal.
        """
        self.updateAppFont()
        for control in self.localControls:
            for window in control.windowList:
                window.updateFonts()
            control.printData.setDefaultFont()
        for control in self.localControls:
            control.updateAll(False)

    def updateAppFont(self):
        """Update application default font from settings.
        """
        appFont = QFont(self.systemFont)
        appFontName = globalref.miscOptions['AppFont']
        if appFontName:
            appFont.fromString(appFontName)
        QApplication.setFont(appFont)

    def formatSelectAll(self):
        """Select all text in any currently focused editor.
        """
        try:
            QApplication.focusWidget().selectAll()
        except AttributeError:
            pass

    def helpViewBasic(self):
        """Display basic usage instructions.
        """
        if not self.basicHelpView:
            path = self.findResourceFile('basichelp.html', 'doc', docPath)
            if not path:
                QMessageBox.warning(QApplication.activeWindow(), 'TreeLine',
                                    _('Error - basic help file not found'))
                return
            self.basicHelpView = helpview.HelpView(path,
                                                   _('TreeLine Basic Usage'),
                                                   globalref.toolIcons)
        self.basicHelpView.show()

    def helpViewFull(self):
        """Open a TreeLine file with full documentation.
        """
        path = self.findResourceFile('documentation.trln', 'doc', docPath)
        if not path:
            QMessageBox.warning(QApplication.activeWindow(), 'TreeLine',
                                _('Error - documentation file not found'))
            return
        self.createLocalControl(path, forceNewWindow=True)
        self.activeControl.filePathObj = pathlib.Path('documentation.trln')
        self.activeControl.updateWindowCaptions()
        self.activeControl.expandRootNodes()
        self.activeControl.imported = True
        win = self.activeControl.activeWindow
        win.rightTabs.setCurrentWidget(win.outputSplitter)

    def helpAbout(self):
        """ Display version info about this program.
        """
        pyVersion = '.'.join([repr(num) for num in sys.version_info[:3]])
        textLines = [_('TreeLine version {0}').format(__version__),
                     _('written by {0}').format(__author__), '',
                     _('Library versions:'),
                     '   Python:  {0}'.format(pyVersion),
                     '   Qt:  {0}'.format(qVersion()),
                     '   PyQt:  {0}'.format(PYQT_VERSION_STR),
                     '   OS:  {0}'.format(platform.platform())]
        dialog = miscdialogs.AboutDialog('TreeLine', textLines,
                                         QApplication.windowIcon(),
                                         QApplication.activeWindow())
        dialog.exec_()


def setThemeColors():
    """Set the app colors based on options setting.
    """
    if globalref.genOptions['ColorTheme'] == optiondefaults.colorThemes[1]:
        # dark theme
        myDarkGray = QColor(53, 53, 53)
        myVeryDarkGray = QColor(25, 25, 25)
        myBlue = QColor(42, 130, 218)
        palette = QPalette()
        palette.setColor(QPalette.Window, myDarkGray)
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, myVeryDarkGray)
        palette.setColor(QPalette.AlternateBase, myDarkGray)
        palette.setColor(QPalette.ToolTipBase, Qt.darkBlue)
        palette.setColor(QPalette.ToolTipText, Qt.lightGray)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, myDarkGray)
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, myBlue)
        palette.setColor(QPalette.Highlight, myBlue)
        palette.setColor(QPalette.HighlightedText, Qt.black)
        palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
        qApp.setPalette(palette)
