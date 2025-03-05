#!/usr/bin/env python3

#******************************************************************************
# threedview.py, provides a 3D visualization view
#
# TreeLine, an information storage program
# Copyright (C) 2023, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version. This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY. See the included LICENSE file for details.
#******************************************************************************

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPixmap, QPainter, QFont, QIcon
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout,
                            QLineEdit, QPushButton, QTextEdit, QGridLayout)

import globalref

class DemoTreeImage(QLabel):
    """A static image widget showing a demo tree structure.
    """
    def __init__(self, parent=None):
        """Initialize the image widget.
        
        Arguments:
            parent -- parent widget
        """
        super().__init__(parent)
        self.setMinimumHeight(300)
        self.setMinimumWidth(500)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #2a3142; border-radius: 8px;")
        
        # Set text
        font = self.font()
        font.setPointSize(12)
        font.setBold(True)
        self.setFont(font)
        self.setWordWrap(True)
        self.setText(_("3D Tree View Demo\n\n"
                      "This represents a visual tree structure\n"
                      "with nodes connected in a hierarchical relationship.\n\n"
                      "Use the command line below to interact with the view."))
        self.setStyleSheet("color: white; background-color: #2a3142; padding: 20px;")
        

class ThreeDViewWidget(QWidget):
    """Widget for 3D visualization of TreeLine data.
    """
    def __init__(self, model, parent=None):
        """Initialize the 3D view widget.
        
        Arguments:
            model -- the TreeLine model
            parent -- the parent widget, set by tree window
        """
        super().__init__(parent)
        self.model = model
        self.windowTitle = _('3D View')
        
        # Use basic layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Create title
        title = QLabel(_('TreeLine 3D Visualization'))
        title.setAlignment(Qt.AlignCenter)
        font = title.font()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        self.layout.addWidget(title)
        
        # Add static tree image
        self.tree_view = DemoTreeImage(self)
        self.layout.addWidget(self.tree_view)
        
        # Controls
        controls = QHBoxLayout()
        
        self.demo_button = QPushButton(_('Demo'))
        self.demo_button.clicked.connect(self.show_demo)
        controls.addWidget(self.demo_button)
        
        self.reset_button = QPushButton(_('Reset'))
        self.reset_button.clicked.connect(self.reset_view)
        controls.addWidget(self.reset_button)
        
        self.clear_button = QPushButton(_('Clear Log'))
        self.clear_button.clicked.connect(self.clear_log)
        controls.addWidget(self.clear_button)
        
        self.layout.addLayout(controls)
        
        # Log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(80)
        self.log_area.setPlaceholderText(_("Status log will appear here"))
        self.layout.addWidget(self.log_area)
        
        # Command line
        cmd_layout = QGridLayout()
        self.layout.addLayout(cmd_layout)
        
        self.cmd_label = QLabel(_('Command:'))
        cmd_layout.addWidget(self.cmd_label, 0, 0)
        
        self.cmd_entry = QLineEdit()
        self.cmd_entry.returnPressed.connect(self.execute_command)
        cmd_layout.addWidget(self.cmd_entry, 0, 1)
        
        self.exec_button = QPushButton(_('Execute'))
        self.exec_button.clicked.connect(self.execute_command)
        cmd_layout.addWidget(self.exec_button, 0, 2)
        
        # Add initial log message
        self.log_message(_("3D View initialized. Type 'help' for commands."))
    
    def log_message(self, message):
        """Add a message to the log area.
        
        Arguments:
            message -- the message to log
        """
        self.log_area.append(message)
    
    def show_demo(self):
        """Show a demo visualization.
        """
        self.log_message(_("Demo mode activated"))
        
        # Change the view styling
        self.tree_view.setStyleSheet("color: white; background-color: #30548a; padding: 20px;")
        
        # Update the demo text
        self.tree_view.setText(_("3D Tree View Demo\n\n"
                               "Root Node\n"
                               "├── Documents\n"
                               "│   ├── Document 1\n"
                               "│   └── Document 2\n"
                               "├── Projects\n"
                               "│   ├── Project 1\n"
                               "│   └── Project 2\n"
                               "└── Settings"))
    
    def reset_view(self):
        """Reset the view to default.
        """
        self.log_message(_("View reset to default"))
        
        # Reset the view styling
        self.tree_view.setStyleSheet("color: white; background-color: #2a3142; padding: 20px;")
        
        # Reset the demo text
        self.tree_view.setText(_("3D Tree View Demo\n\n"
                               "This represents a visual tree structure\n"
                               "with nodes connected in a hierarchical relationship.\n\n"
                               "Use the command line below to interact with the view."))
    
    def clear_log(self):
        """Clear the log area.
        """
        self.log_area.clear()
    
    def execute_command(self):
        """Execute a command from the command line.
        """
        command = self.cmd_entry.text().strip().lower()
        self.cmd_entry.clear()
        
        if not command:
            return
            
        self.log_message(f"> {command}")
        
        if command == 'help':
            self.log_message(_("Available commands: help, demo, reset, clear"))
        elif command == 'demo':
            self.show_demo()
        elif command == 'reset':
            self.reset_view()
        elif command == 'clear':
            self.clear_log()
        else:
            self.log_message(_("Unknown command. Type 'help' for available commands."))
    
    def update_scene(self, *args):
        """Placeholder for scene updates.
        
        Arguments:
            *args -- dummy arguments to collect args from signals
        """
        # This fallback version doesn't react to model changes
        pass