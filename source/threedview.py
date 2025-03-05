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

from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QModelIndex
from PyQt5.QtGui import QColor, QPixmap, QPainter, QFont, QIcon, QPen, QBrush, QLinearGradient
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout,
                            QLineEdit, QPushButton, QTextEdit, QGridLayout,
                            QScrollArea, QFrame, QSlider, QComboBox)

import globalref
import math
import random

class TreeNode3D:
    """Represents a node in 3D space with position and connections.
    """
    def __init__(self, title, node_id, parent_id=None):
        """Initialize the 3D node.
        
        Arguments:
            title -- node title/name
            node_id -- unique identifier
            parent_id -- parent node id
        """
        self.title = title
        self.name = ""  # Specific Name field
        self.node_id = node_id
        self.parent_id = parent_id
        self.description = ""  # Store description for hover display
        self.text = ""  # Additional text for hover display
        
        # Initial coordinates in 3D space - will be saved with the data
        self.x = random.uniform(-300, 300)
        self.y = random.uniform(-200, 200)
        self.z = random.uniform(-300, 300)
        
        # Projected coordinates (2D)
        self.px = 0
        self.py = 0
        
        # Node color - use HSV color space for better differentiation
        hue = random.uniform(0, 360)
        self.color = QColor.fromHsv(
            int(hue),  # Hue
            random.randint(180, 255),  # Saturation
            random.randint(180, 255)   # Value
        )
        
        # Node dimensions (width, height, depth)
        self.width = random.uniform(40, 80)
        self.height = random.uniform(20, 40)
        self.depth = random.uniform(10, 30)
        
        # Default level in the tree
        self.level = 0
        
        # Interaction state
        self.hovered = False
        self.dragging = False
        
        # Original position before dragging
        self.orig_x = self.x
        self.orig_y = self.y
        self.orig_z = self.z
        
    def set_position(self, x, y, z):
        """Set the 3D position of this node.
        
        Arguments:
            x, y, z -- coordinates in 3D space
        """
        self.x = x
        self.y = y
        self.z = z
        
    def store_original_position(self):
        """Store current position as original position for drag operations.
        """
        self.orig_x = self.x
        self.orig_y = self.y
        self.orig_z = self.z
        
    def update_position_by_offset(self, dx, dy, dz):
        """Update position by adding offsets to original position.
        
        Arguments:
            dx, dy, dz -- offsets from original position
        """
        self.x = self.orig_x + dx
        self.y = self.orig_y + dy
        self.z = self.orig_z + dz

class TreeView3D(QWidget):
    """Widget for rendering the tree in 3D space.
    """
    def __init__(self, parent=None):
        """Initialize the 3D rendering widget.
        
        Arguments:
            parent -- parent widget
        """
        super().__init__(parent)
        self.setMinimumHeight(400)
        self.setMinimumWidth(600)
        
        # Visual settings
        self.background_color = QColor(22, 28, 38)
        self.line_color = QColor(80, 80, 100, 120)
        self.selected_color = QColor(255, 140, 0)
        self.highlight_color = QColor(255, 220, 120)
        
        # Camera and view settings
        self.camera_distance = 700
        self.rotation_x = 0.4  # Default slight tilt
        self.rotation_y = 0.2  # Default slight rotation
        self.rotation_z = 0
        self.scale = 1.0
        self.center_x = self.width() / 2
        self.center_y = self.height() / 2
        
        # Tree data
        self.nodes = {}
        self.connections = []
        self.selected_node = None
        self.hovered_node = None
        
        # Interaction state
        self.mouse_down = False
        self.last_mouse_pos = QPoint(0, 0)
        self.current_mouse_pos = QPoint(0, 0)
        
        # Set focus policy to receive key events
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Animation timer
        self.animation_active = False
        
        # Mouse tracking for hover effects
        self.setMouseTracking(True)
        
    def create_demo_tree(self):
        """Create a demo tree structure.
        """
        self.nodes.clear()
        self.connections.clear()
        
        # Create root node
        root = TreeNode3D("Root", "root")
        root.set_position(0, 0, 0)
        root.size = 25
        self.nodes["root"] = root
        
        # First level children
        categories = ["Documents", "Projects", "Settings"]
        category_ids = []
        
        for i, category in enumerate(categories):
            angle = 2 * math.pi * i / len(categories)
            node_id = f"cat_{i}"
            node = TreeNode3D(category, node_id, "root")
            radius = 120
            node.set_position(radius * math.sin(angle), 
                             -70, 
                             radius * math.cos(angle))
            node.size = 20
            self.nodes[node_id] = node
            category_ids.append(node_id)
            self.connections.append(("root", node_id))
        
        # Second level - documents
        docs = ["Document 1", "Document 2", "Document 3"]
        for i, doc in enumerate(docs):
            angle = 2 * math.pi * i / len(docs)
            node_id = f"doc_{i}"
            node = TreeNode3D(doc, node_id, category_ids[0])
            radius = 80
            x = self.nodes[category_ids[0]].x + radius * math.sin(angle)
            z = self.nodes[category_ids[0]].z + radius * math.cos(angle)
            y = self.nodes[category_ids[0]].y - 60
            node.set_position(x, y, z)
            node.size = 15
            self.nodes[node_id] = node
            self.connections.append((category_ids[0], node_id))
        
        # Projects
        projects = ["Project 1", "Project 2"]
        for i, project in enumerate(projects):
            angle = 2 * math.pi * i / len(projects)
            node_id = f"proj_{i}"
            node = TreeNode3D(project, node_id, category_ids[1])
            radius = 80
            x = self.nodes[category_ids[1]].x + radius * math.sin(angle)
            z = self.nodes[category_ids[1]].z + radius * math.cos(angle)
            y = self.nodes[category_ids[1]].y - 60
            node.set_position(x, y, z)
            node.size = 15
            self.nodes[node_id] = node
            self.connections.append((category_ids[1], node_id))
            
            # Add project items
            items = [f"Item {j+1}" for j in range(3)]
            for j, item in enumerate(items):
                item_angle = 2 * math.pi * j / len(items)
                item_id = f"item_{i}_{j}"
                item_node = TreeNode3D(item, item_id, node_id)
                item_radius = 50
                ix = node.x + item_radius * math.sin(item_angle)
                iz = node.z + item_radius * math.cos(item_angle)
                iy = node.y - 40
                item_node.set_position(ix, iy, iz)
                item_node.size = 10
                self.nodes[item_id] = item_node
                self.connections.append((node_id, item_id))
        
        # Settings
        settings = ["User Settings", "System Settings"]
        for i, setting in enumerate(settings):
            angle = 2 * math.pi * i / len(settings)
            node_id = f"set_{i}"
            node = TreeNode3D(setting, node_id, category_ids[2])
            radius = 80
            x = self.nodes[category_ids[2]].x + radius * math.sin(angle)
            z = self.nodes[category_ids[2]].z + radius * math.cos(angle)
            y = self.nodes[category_ids[2]].y - 60
            node.set_position(x, y, z)
            node.size = 15
            self.nodes[node_id] = node
            self.connections.append((category_ids[2], node_id))
            
        self.update()

    def create_tree_from_data(self, data, parent_id=None, level=0):
        """Create a tree structure from a dictionary representation.
        
        Arguments:
            data -- dict containing node data
            parent_id -- parent node ID
            level -- current depth level
        """
        if not data:
            return

        # Create node entries for each key in the data
        for i, (key, value) in enumerate(data.items()):
            node_id = f"data_{level}_{i}"
            
            # Create 3D node
            node = TreeNode3D(key, node_id, parent_id)
            node.size = max(8, 25 - (level * 3))
            
            # Initial position
            node.set_position(i * 50, level * -100, 0)
            
            # Store node
            self.nodes[node_id] = node
            
            # Create connection to parent
            if parent_id:
                self.connections.append((parent_id, node_id))
            
            # Process children if value is a dict
            if isinstance(value, dict):
                self.create_tree_from_data(value, node_id, level + 1)
    
    def load_tree_from_model(self, model):
        """Load tree data from the TreeLine model.
        
        Arguments:
            model -- TreeLine tree model
        """
        if not model:
            return False
            
        self.nodes.clear()
        self.connections.clear()
        
        try:
            # Create a simple tree structure from data
            # First create root node
            root_id = "root"
            root = TreeNode3D("Root", root_id)
            root.set_position(0, 0, 0)
            root.size = 25
            self.nodes[root_id] = root
            
            # Try to get the tree structure data or create a demo tree
            if hasattr(model, 'treeStructure'):
                # For top-level nodes
                categories = {}
                
                # Try to access nodes through the structure
                try:
                    # If treeStructure has nodes, use them
                    if hasattr(model.treeStructure, 'childList'):
                        for i, node in enumerate(model.treeStructure.childList):
                            if hasattr(node, 'data'):
                                # Get title from node data if available
                                title = node.data.get('Title', f"Node {i}")
                            else:
                                # Otherwise use a generic title
                                title = f"Node {i}"
                                
                            node_id = f"node_{i}"
                            categories[title] = {}
                            
                            # Create 3D node for this category
                            cat_node = TreeNode3D(title, node_id, root_id) 
                            cat_node.size = 20
                            self.nodes[node_id] = cat_node
                            
                            # Add connection from root
                            self.connections.append((root_id, node_id))
                            
                            # Process child nodes if they exist
                            if hasattr(node, 'childList'):
                                for j, child in enumerate(node.childList):
                                    if hasattr(child, 'data'):
                                        child_title = child.data.get('Title', f"Child {j}")
                                    else:
                                        child_title = f"Child {j}"
                                    
                                    child_node_id = f"node_{i}_{j}"
                                    categories[title][child_title] = {}
                                    
                                    # Create 3D node for this child
                                    child_node = TreeNode3D(child_title, child_node_id, node_id)
                                    child_node.size = 15
                                    self.nodes[child_node_id] = child_node
                                    
                                    # Add connection from parent
                                    self.connections.append((node_id, child_node_id))
                except Exception as e:
                    print(f"Error accessing nodes: {e}")
                
                # If no nodes were created through the direct method, create from the dictionary
                if len(self.nodes) <= 1:  # just the root node
                    self.create_tree_from_data(categories, root_id, 1)
            else:
                # Create a demo tree
                categories = {
                    "Documents": {
                        "Document 1": {},
                        "Document 2": {},
                    },
                    "Projects": {
                        "Project 1": {
                            "Task 1": {},
                            "Task 2": {},
                        },
                        "Project 2": {},
                    },
                    "Settings": {
                        "User Settings": {},
                        "System Settings": {},
                    }
                }
                
                # Create the tree structure using dictionary
                self.create_tree_from_data(categories, root_id, 1)
            
            # Calculate node positions
            self._layout_tree()
            
            self.update()
            return True
        except Exception as e:
            import traceback
            print(f"Error loading tree: {e}")
            print(traceback.format_exc())
            return False
            
    def _process_node(self, tree_node, parent_id, level, index):
        """Process a TreeLine node and create a 3D node.
        
        Arguments:
            tree_node -- TreeLine tree node
            parent_id -- parent 3D node ID
            level -- depth level in the tree
            index -- horizontal index at this level
        """
        if not tree_node:
            return
            
        # Create a unique ID for this node
        node_id = f"node_{id(tree_node)}"
        
        # Extract all relevant data from the tree node
        title = ""
        name = ""
        description = ""
        text = ""
        
        try:
            # Try different methods to get node data
            if hasattr(tree_node, 'data'):
                # Check if data is a dictionary with our fields
                if isinstance(tree_node.data, dict):
                    # Extract all possible fields
                    if 'Title' in tree_node.data:
                        title = tree_node.data['Title']
                    
                    if 'Name' in tree_node.data:
                        name = tree_node.data['Name']
                    
                    if 'Description' in tree_node.data:
                        description = tree_node.data['Description']
                    
                    if 'Text' in tree_node.data:
                        text = tree_node.data['Text']
                    
                    # Check for position data
                    pos_x = None
                    pos_y = None
                    pos_z = None
                    
                    if '3D_Position_X' in tree_node.data:
                        try:
                            pos_x = float(tree_node.data['3D_Position_X'])
                        except (ValueError, TypeError):
                            pass
                    
                    if '3D_Position_Y' in tree_node.data:
                        try:
                            pos_y = float(tree_node.data['3D_Position_Y'])
                        except (ValueError, TypeError):
                            pass
                    
                    if '3D_Position_Z' in tree_node.data:
                        try:
                            pos_z = float(tree_node.data['3D_Position_Z'])
                        except (ValueError, TypeError):
                            pass
            
            # If still no title, try other methods
            if not title:
                if hasattr(tree_node, 'title'):
                    if callable(tree_node.title):
                        title = tree_node.title()
                    else:
                        title = str(tree_node.title)
                else:
                    title = str(tree_node)
        except Exception as e:
            title = f"Node {node_id[-6:]}"
        
        # Create 3D node
        node = TreeNode3D(title, node_id, parent_id)
        node.name = name
        node.description = description
        node.text = text
        node.level = level
        
        # Scale dimensions based on level
        base_width = 60
        base_height = 40
        node.width = max(30, base_width + random.uniform(-10, 10))
        node.height = max(20, base_height + random.uniform(-5, 5))
        node.depth = max(10, 30 + random.uniform(-3, 3))
        
        # Create random coloring, not level-based
        hue = random.uniform(0, 360)
        saturation = 160 + random.randint(0, 95)
        value = 200 + random.randint(0, 55)
        node.color = QColor.fromHsv(int(hue), saturation, value)
        
        # Check if we have saved position data
        if pos_x is not None and pos_y is not None and pos_z is not None:
            node.set_position(pos_x, pos_y, pos_z)
        else:
            # Assign a random position in 3D space
            spread_factor = 150
            node.set_position(
                random.uniform(-spread_factor, spread_factor),
                random.uniform(-spread_factor, spread_factor),
                random.uniform(-spread_factor, spread_factor)
            )
        
        # Store node
        self.nodes[node_id] = node
        
        # No longer create connections - we'll just have floating nodes
        
        # Process children - continue through all levels
        try:
            # Try different methods to get children
            children = []
            
            if hasattr(tree_node, 'childCount') and callable(tree_node.childCount):
                child_count = tree_node.childCount()
                for i in range(child_count):
                    children.append(tree_node.child(i))
            elif hasattr(tree_node, 'children'):
                if callable(tree_node.children):
                    children = tree_node.children()
                else:
                    children = tree_node.children
            elif hasattr(tree_node, 'childList'):
                children = tree_node.childList
            
            # Process all children, not just the first few levels
            for i, child in enumerate(children):
                self._process_node(child, node_id, level + 1, i)
        except Exception as e:
            print(f"Error processing children: {e}")
    
    def _layout_tree(self):
        """Arrange nodes in 3D space using a force-directed algorithm.
        """
        # Find the root node (node without a parent)
        root_id = None
        for node_id, node in self.nodes.items():
            if node.parent_id is None:
                root_id = node_id
                break
        
        if not root_id:
            return
        
        # Place root at center
        root_node = self.nodes[root_id]
        root_node.set_position(0, 0, 0)
        
        # Layout by level
        self._layout_level(root_id, 0)
        
    def _layout_level(self, node_id, level):
        """Recursively layout a level of the tree.
        
        Arguments:
            node_id -- ID of the parent node
            level -- current depth level
        """
        # Find children
        children = []
        for src, dest in self.connections:
            if src == node_id:
                children.append(dest)
        
        if not children:
            return
            
        # Calculate positions for children
        parent = self.nodes[node_id]
        radius = 120 / (level + 1)
        
        for i, child_id in enumerate(children):
            child = self.nodes[child_id]
            angle = 2 * math.pi * i / len(children)
            
            # Position relative to parent
            x = parent.x + radius * math.sin(angle)
            z = parent.z + radius * math.cos(angle)
            y = parent.y - 60 - (level * 20)
            
            child.set_position(x, y, z)
            
            # Recursively layout children
            self._layout_level(child_id, level + 1)
    
    def project_point(self, x, y, z):
        """Project a 3D point onto the 2D screen.
        
        Arguments:
            x, y, z -- 3D coordinates
        Returns:
            tuple of 2D (x, y) screen coordinates
        """
        # Apply rotation around X axis
        y2 = y * math.cos(self.rotation_x) - z * math.sin(self.rotation_x)
        z2 = y * math.sin(self.rotation_x) + z * math.cos(self.rotation_x)
        
        # Apply rotation around Y axis
        x3 = x * math.cos(self.rotation_y) + z2 * math.sin(self.rotation_y)
        z3 = -x * math.sin(self.rotation_y) + z2 * math.cos(self.rotation_y)
        
        # Apply rotation around Z axis
        x4 = x3 * math.cos(self.rotation_z) - y2 * math.sin(self.rotation_z)
        y4 = x3 * math.sin(self.rotation_z) + y2 * math.cos(self.rotation_z)
        
        # Calculate perspective projection
        f = 1000  # focal length
        if z3 + self.camera_distance <= 0:
            # Avoid division by zero - point is behind camera
            return (self.center_x, self.center_y)
            
        # Project the 3D point to 2D
        scale_factor = f / (z3 + self.camera_distance) * self.scale
        px = x4 * scale_factor + self.center_x
        py = y4 * scale_factor + self.center_y
        
        return (px, py)
    
    def paintEvent(self, event):
        """Paint the 3D visualization.
        
        Arguments:
            event -- paint event
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Update center coordinates based on current size
        self.center_x = self.width() / 2
        self.center_y = self.height() / 2
        
        # Draw background
        painter.fillRect(event.rect(), self.background_color)
        
        # Project all nodes to 2D
        for node_id, node in self.nodes.items():
            px, py = self.project_point(node.x, node.y, node.z)
            node.px = px
            node.py = py
        
        # Create a list of selected nodes and their children for highlighting
        highlighted_nodes = set()
        if self.selected_node:
            highlighted_nodes.add(self.selected_node)
            self._add_children_recursive(self.selected_node, highlighted_nodes)
        
        # Sort nodes by Z distance for proper rendering (back to front)
        sorted_nodes = sorted(
            self.nodes.values(), 
            key=lambda node: node.z + self.camera_distance, 
            reverse=True
        )
        
        # We no longer draw connections between nodes
        
        # Draw nodes as rectangles
        for node in sorted_nodes:
            # Calculate depth factor for scaling and opacity
            z_factor = 800 / (node.z + self.camera_distance + 800)
            width = node.width * z_factor * self.scale
            height = node.height * z_factor * self.scale
            depth = node.depth * z_factor * self.scale
            opacity = min(255, max(50, int(255 * z_factor)))
            
            # Determine if node is highlighted (selected or child of selected)
            is_highlighted = node.node_id in highlighted_nodes
            is_hovered = node.node_id == self.hovered_node
            
            # Create 3D effect with offset rectangles
            offset_x = int(depth * 0.3)
            offset_y = int(depth * 0.3)
            
            # Calculate rectangle position
            rect_x = int(node.px - width/2)
            rect_y = int(node.py - height/2)
            
            # Create gradients for main face and sides
            if is_highlighted:
                # Use highlight colors for selected nodes
                base_color = self.highlight_color
                edge_color = QColor(
                    min(255, base_color.red() + 20),
                    min(255, base_color.green() + 20),
                    min(255, base_color.blue() - 40),
                    opacity
                )
            elif is_hovered:
                # Special hover color
                base_color = QColor(255, 255, 200, opacity)
                edge_color = QColor(200, 200, 150, opacity)
            else:
                # Use node's own color
                base_color = QColor(
                    node.color.red(),
                    node.color.green(),
                    node.color.blue(),
                    opacity
                )
                edge_color = QColor(
                    max(0, node.color.red() - 40),
                    max(0, node.color.green() - 40),
                    max(0, node.color.blue() - 40),
                    opacity
                )
            
            # Draw the 3D box sides first (if visible and large enough)
            if depth > 3 and width > 5 and height > 5:
                # Right side
                side_gradient = QLinearGradient(
                    rect_x + width, rect_y,
                    rect_x + width + offset_x, rect_y + offset_y
                )
                side_gradient.setColorAt(0, base_color)
                side_gradient.setColorAt(1, edge_color)
                painter.setBrush(QBrush(side_gradient))
                painter.setPen(Qt.NoPen)
                painter.drawPolygon([
                    QPoint(int(rect_x + width), int(rect_y)),
                    QPoint(int(rect_x + width + offset_x), int(rect_y + offset_y)),
                    QPoint(int(rect_x + width + offset_x), int(rect_y + height + offset_y)),
                    QPoint(int(rect_x + width), int(rect_y + height))
                ])
                
                # Bottom side
                bottom_gradient = QLinearGradient(
                    rect_x, rect_y + height,
                    rect_x + offset_x, rect_y + height + offset_y
                )
                bottom_gradient.setColorAt(0, base_color)
                bottom_gradient.setColorAt(1, edge_color)
                painter.setBrush(QBrush(bottom_gradient))
                painter.drawPolygon([
                    QPoint(int(rect_x), int(rect_y + height)),
                    QPoint(int(rect_x + offset_x), int(rect_y + height + offset_y)),
                    QPoint(int(rect_x + width + offset_x), int(rect_y + height + offset_y)),
                    QPoint(int(rect_x + width), int(rect_y + height))
                ])
            
            # Draw main rectangle face
            main_gradient = QLinearGradient(
                rect_x, rect_y,
                rect_x + width, rect_y + height
            )
            main_gradient.setColorAt(0, QColor(
                min(255, base_color.red() + 30),
                min(255, base_color.green() + 30),
                min(255, base_color.blue() + 30),
                opacity
            ))
            main_gradient.setColorAt(1, base_color)
            
            # Draw the main rectangle with a thin border
            painter.setBrush(QBrush(main_gradient))
            border_color = QColor(30, 30, 30, min(200, opacity))
            border_width = 1 if not is_highlighted else 2
            painter.setPen(QPen(border_color, border_width))
            painter.drawRect(rect_x, rect_y, int(width), int(height))
            
            # Draw the Name field on the face of the rectangle
            if node.name and width > 15 and height > 10:
                # Draw name text directly on the rectangle
                font = painter.font()
                font.setPointSize(max(7, min(9, int((width + height) / 18))))
                painter.setFont(font)
                
                # Text color - white or black depending on background brightness
                brightness = (base_color.red() * 299 + base_color.green() * 587 + base_color.blue() * 114) / 1000
                if brightness > 128:
                    text_color = QColor(0, 0, 0, min(255, int(opacity * 1.2)))
                else:
                    text_color = QColor(255, 255, 255, min(255, int(opacity * 1.2)))
                
                painter.setPen(QPen(text_color))
                
                # Center the name on the rectangle
                name_rect = QRect(
                    rect_x, 
                    rect_y, 
                    int(width), 
                    int(height)
                )
                
                # Make the text fit within the box
                displayed_name = node.name
                if font.pointSize() > 7:
                    metrics = painter.fontMetrics()
                    if metrics.width(displayed_name) > width - 8:
                        # Truncate with ellipsis if too long
                        displayed_name = metrics.elidedText(displayed_name, Qt.ElideRight, int(width) - 8)
                
                painter.drawText(name_rect, Qt.AlignCenter, displayed_name)
            
            # Draw hover hint (text or description)
            if is_hovered:
                # If we have a text field or description, show it
                hover_text = node.text if node.text else node.description
                
                if hover_text:
                    # Position hover text above the node
                    hint_rect = QRect(
                        int(node.px - 150),
                        int(node.py - height/2 - 50),
                        300,
                        40
                    )
                    
                    # Draw a semi-transparent background for better readability
                    painter.fillRect(hint_rect, QColor(0, 0, 0, 180))
                    
                    # Draw hover text
                    font = painter.font()
                    font.setPointSize(9)
                    painter.setFont(font)
                    painter.setPen(QPen(QColor(255, 255, 220)))
                    
                    # If text is too long, truncate it
                    metrics = painter.fontMetrics()
                    elided_text = metrics.elidedText(hover_text, Qt.ElideRight, 290)
                    painter.drawText(hint_rect, Qt.AlignCenter, elided_text)
    
    def _add_children_recursive(self, node_id, highlighted_set):
        """Add all children of a node to the highlighted set recursively.
        
        Arguments:
            node_id -- the parent node ID
            highlighted_set -- set to add child node IDs to
        """
        for src, dest in self.connections:
            if src == node_id:
                highlighted_set.add(dest)
                self._add_children_recursive(dest, highlighted_set)
    
    def mousePressEvent(self, event):
        """Handle mouse press events.
        
        Arguments:
            event -- mouse event
        """
        self.mouse_down = True
        self.last_mouse_pos = event.pos()
        
        # Check for node selection - rectangle hit testing
        selected = self._find_node_at_position(event.x(), event.y())
        
        if selected != self.selected_node:
            self.selected_node = selected
            # If a node is selected, prepare it for dragging
            if selected and selected in self.nodes:
                self.nodes[selected].dragging = True
                self.nodes[selected].store_original_position()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events.
        
        Arguments:
            event -- mouse event
        """
        self.mouse_down = False
        
        # Reset dragging state for all nodes
        for node in self.nodes.values():
            if node.dragging:
                node.dragging = False
                # Here we would save the position to the TreeLine data
                # self._save_node_position(node) - implemented later
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for rotation and hover/drag effects.
        
        Arguments:
            event -- mouse event
        """
        self.current_mouse_pos = event.pos()
        
        # Handle node dragging or view rotation
        if self.mouse_down:
            dx = event.x() - self.last_mouse_pos.x()
            dy = event.y() - self.last_mouse_pos.y()
            
            # Check if we're dragging a node
            dragging_node = None
            if self.selected_node and self.selected_node in self.nodes:
                node = self.nodes[self.selected_node]
                if node.dragging:
                    dragging_node = node
            
            if dragging_node:
                # Calculate 3D movement based on the 2D mouse movement and current rotation
                # This is a simplified calculation and could be improved
                # Movement in the XZ plane, keeping Y constant for simplicity
                
                # Adjust sensitivity based on distance (further = more movement)
                z_factor = 800 / (dragging_node.z + self.camera_distance + 800)
                sensitivity = 2.0 / (z_factor * self.scale)
                
                # Apply rotation matrix inverse to determine 3D movement
                # These calculations counteract the camera rotation to move in world space
                cos_y = math.cos(-self.rotation_y)
                sin_y = math.sin(-self.rotation_y)
                
                # Calculate world space movement
                world_dx = (dx * cos_y - dy * sin_y) * sensitivity
                world_dz = (dx * sin_y + dy * cos_y) * sensitivity
                
                # Update the node position
                dragging_node.update_position_by_offset(world_dx, 0, world_dz)
                
                self.update()
            else:
                # Not dragging a node, so rotate the view
                sensitivity = 0.01
                self.rotation_y += dx * sensitivity
                self.rotation_x += dy * sensitivity
                self.update()
                
            self.last_mouse_pos = event.pos()
        else:
            # Check for node hover when not dragging
            hovered = self._find_node_at_position(event.x(), event.y())
            
            if hovered != self.hovered_node:
                self.hovered_node = hovered
                self.update()
                
    def _save_node_position(self, node):
        """Save the node position to the TreeLine data.
        
        This is a placeholder for the implementation that would actually
        save the position to the TreeLine data model.
        
        Arguments:
            node -- the 3D node to save position for
        """
        # To be implemented - save position to node data
        # This would require access to the TreeLine data structures
        print(f"Would save position for node {node.node_id}: ({node.x}, {node.y}, {node.z})")
    
    def _find_node_at_position(self, x, y):
        """Find a node at the given screen position.
        
        Arguments:
            x, y -- screen coordinates
            
        Returns:
            node_id or None if no node at position
        """
        # Process nodes from front to back for proper hit testing
        sorted_nodes = sorted(
            self.nodes.values(), 
            key=lambda node: node.z + self.camera_distance
        )
        
        for node in sorted_nodes:
            # Calculate node rectangle dimensions
            z_factor = 800 / (node.z + self.camera_distance + 800)
            width = node.width * z_factor * self.scale
            height = node.height * z_factor * self.scale
            
            # Calculate rectangle position
            rect_x = int(node.px - width/2)
            rect_y = int(node.py - height/2)
            
            # Hit testing with rectangle
            if (x >= rect_x and x <= rect_x + width and
                y >= rect_y and y <= rect_y + height):
                return node.node_id
                
        return None
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for zoom.
        
        Arguments:
            event -- wheel event
        """
        # Zoom in/out with mouse wheel
        delta = event.angleDelta().y()
        zoom_factor = 1.0 + (delta / 1000.0)
        self.scale *= zoom_factor
        
        # Clamp scale
        self.scale = max(0.1, min(3.0, self.scale))
        
        self.update()

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
        
        # Add 3D view in a scroll area for safety
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Create the 3D view
        self.tree_view = TreeView3D(self)
        self.scroll_area.setWidget(self.tree_view)
        self.layout.addWidget(self.scroll_area)
        
        # Controls
        controls = QHBoxLayout()
        
        self.load_button = QPushButton(_('Load Tree'))
        self.load_button.clicked.connect(self.load_tree)
        controls.addWidget(self.load_button)
        
        self.demo_button = QPushButton(_('Demo'))
        self.demo_button.clicked.connect(self.show_demo)
        controls.addWidget(self.demo_button)
        
        self.reset_button = QPushButton(_('Reset View'))
        self.reset_button.clicked.connect(self.reset_view)
        controls.addWidget(self.reset_button)
        
        self.save_pos_button = QPushButton(_('Save Positions'))
        self.save_pos_button.clicked.connect(self.save_all_positions)
        controls.addWidget(self.save_pos_button)
        
        self.layout.addLayout(controls)
        
        # Add sliders for rotation
        slider_layout = QGridLayout()
        
        # X rotation
        slider_layout.addWidget(QLabel(_("X Rotation:")), 0, 0)
        self.x_slider = QSlider(Qt.Horizontal)
        self.x_slider.setRange(-100, 100)
        self.x_slider.setValue(40)  # Default tilt
        self.x_slider.valueChanged.connect(self.update_rotation)
        slider_layout.addWidget(self.x_slider, 0, 1)
        
        # Y rotation
        slider_layout.addWidget(QLabel(_("Y Rotation:")), 1, 0)
        self.y_slider = QSlider(Qt.Horizontal)
        self.y_slider.setRange(-100, 100)
        self.y_slider.setValue(20)  # Default rotation
        self.y_slider.valueChanged.connect(self.update_rotation)
        slider_layout.addWidget(self.y_slider, 1, 1)
        
        # Zoom
        slider_layout.addWidget(QLabel(_("Zoom:")), 2, 0)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.update_zoom)
        slider_layout.addWidget(self.zoom_slider, 2, 1)
        
        self.layout.addLayout(slider_layout)
        
        # Log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(80)
        self.log_area.setPlaceholderText(_("Status log will appear here"))
        self.layout.addWidget(self.log_area)
        
        # Add initial log message
        self.log_message(_("3D View initialized. Use mouse to rotate, wheel to zoom."))
    
    def log_message(self, message):
        """Add a message to the log area.
        
        Arguments:
            message -- the message to log
        """
        self.log_area.append(message)
    
    def show_demo(self):
        """Show a demo visualization.
        """
        self.log_message(_("Creating demo tree visualization"))
        self.tree_view.create_demo_tree()
        self.reset_view()
    
    def load_tree(self):
        """Load the actual TreeLine tree.
        """
        try:
            self.log_message(_("Loading TreeLine tree data..."))
            
            # Debug model structure
            if self.model:
                self.log_message(f"Model type: {type(self.model)}")
                if hasattr(self.model, 'treeStructure'):
                    self.log_message("Model has treeStructure")
                    if hasattr(self.model.treeStructure, 'rootNode'):
                        self.log_message("treeStructure has rootNode")
            
            if self.tree_view.load_tree_from_model(self.model):
                self.log_message(_("Tree data loaded successfully"))
                self.reset_view()
            else:
                self.log_message(_("Failed to load tree data. Using demo instead."))
                self.show_demo()
        except Exception as e:
            self.log_message(_("Error: {0}").format(str(e)))
            import traceback
            self.log_message(traceback.format_exc())
            self.show_demo()
    
    def reset_view(self):
        """Reset the view to default.
        """
        self.log_message(_("View reset to default"))
        
        # Reset sliders
        self.x_slider.setValue(0)
        self.y_slider.setValue(0)
        self.zoom_slider.setValue(100)
        
        # Reset 3D view parameters
        self.tree_view.rotation_x = 0
        self.tree_view.rotation_y = 0
        self.tree_view.rotation_z = 0
        self.tree_view.scale = 1.0
        self.tree_view.camera_distance = 500
        
        # Update view
        self.tree_view.update()
    
    def update_rotation(self):
        """Update rotation based on slider values.
        """
        # Convert slider values to radians
        self.tree_view.rotation_x = self.x_slider.value() / 100.0 * math.pi
        self.tree_view.rotation_y = self.y_slider.value() / 100.0 * math.pi
        
        # Update view
        self.tree_view.update()
    
    def update_zoom(self):
        """Update zoom based on slider value.
        """
        # Scale based on slider
        self.tree_view.scale = self.zoom_slider.value() / 100.0
        
        # Update view
        self.tree_view.update()
    
    def update_scene(self, *args):
        """Update scene when model changes.
        
        Arguments:
            *args -- dummy arguments to collect args from signals
        """
        try:
            if self.isVisible():
                self.load_tree()
        except Exception as e:
            self.log_message(f"Update error: {e}")
            
    def save_all_positions(self):
        """Save all node positions to the TreeLine data.
        
        This function would be called when the user wants to
        save all current positions to the data model.
        """
        self.log_message(_("Saving node positions..."))
        
        # Implementation would require access to TreeLine data model
        # For now, just log the positions we would save
        for node_id, node in self.tree_view.nodes.items():
            x, y, z = node.x, node.y, node.z
            self.log_message(f"Node {node_id}: Position ({x:.1f}, {y:.1f}, {z:.1f})")
        
        self.log_message(_("Positions saved (simulated)"))