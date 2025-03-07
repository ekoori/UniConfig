#!/usr/bin/env python3

"""
AI agent interface for TreeLine.
Provides capabilities for an AI agent to modify and interact with the TreeLine data structure.
"""

import json
import sys
import os
import uuid
import pathlib
import anthropic
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QSettings
from PyQt5.QtGui import QTextCursor, QIcon, QTextCharFormat, QColor
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QTextEdit, QLineEdit, QProgressBar,
                           QSplitter, QApplication, QMessageBox, QInputDialog)

import globalref
import optiondefaults
import treestructure
import treenode
import treemodel
import treespot
import treespotlist
from treeselection import TreeSelection


class AgentInterface:
    """Interface for AI agent to interact with TreeLine data structure."""
    
    def __init__(self, local_control):
        """Initialize the agent interface with reference to local control.
        
        Args:
            local_control: Reference to TreeLocalControl for the active window
        """
        self.local_control = local_control
        self.tree_structure = local_control.structure
        self.tree_model = local_control.model
        self.tree_view = local_control.activeWindow.treeView
        self.selection = local_control.activeWindow.treeView.selectionModel()
        self.client = None
        self._initialize_anthropic_client()
        
        # Keep track of recent actions and context
        self.message_history = []
        self.action_results = {}
        self.last_created_node_id = None
        self.last_api_request_log = ""
        self.debug_node_titles = []
    
    def _initialize_anthropic_client(self):
        """Initialize the Anthropic API client if API key is available."""
        api_key = self._get_api_key()
        if api_key:
            try:
                self.client = anthropic.Anthropic(api_key=api_key)
            except Exception as e:
                print(f"Error initializing Anthropic client: {e}")
    
    def _get_api_key(self):
        """Get Anthropic API key from environment variable or settings."""
        # Try environment variable first
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        
        # If not in environment, try settings
        if not api_key:
            settings = QSettings(QSettings.IniFormat, QSettings.UserScope,
                               'TreeLine', 'TreeLine')
            api_key = settings.value('AgentApiKey', '')
            
        return api_key
    
    def set_api_key(self, api_key):
        """Set and save API key for Anthropic API.
        
        Args:
            api_key: Anthropic API key
        """
        settings = QSettings(QSettings.IniFormat, QSettings.UserScope,
                           'TreeLine', 'TreeLine')
        settings.setValue('AgentApiKey', api_key)
        self._initialize_anthropic_client()
    
    def get_tree_json(self, node=None):
        """Get JSON representation of the tree or a specific node.
        
        Args:
            node: Optional node to get data for. If None, gets data for selected nodes.
            
        Returns:
            JSON string representing the tree or node structure
        """
        if node is None:
            # Get currently selected node(s)
            selection = self.selection
            if selection.hasSelection():
                selected_indexes = selection.selectedIndexes()
                if selected_indexes:
                    node = selected_indexes[0].internalPointer().nodeRef
        
        if node is None:
            # Fall back to first node in tree if nothing selected
            if self.tree_structure.childList:
                node = self.tree_structure.childList[0]
            else:
                # Empty tree - return empty structure
                empty_data = {
                    "message": "Tree structure is empty - no nodes found",
                    "available_formats": [f for f in self.tree_structure.treeFormats]
                }
                return json.dumps(empty_data, indent=2)
        
        # Get node data in a dict format
        node_data = self._get_node_data_dict(node)
        
        # Make sure data is JSON serializable
        def sanitize_for_json(obj):
            if isinstance(obj, dict):
                return {k: sanitize_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_for_json(item) for item in obj]
            elif isinstance(obj, (int, float, str, bool)) or obj is None:
                return obj
            else:
                return str(obj)
                
        sanitized_data = sanitize_for_json(node_data)
        return json.dumps(sanitized_data, indent=2)
        
    def get_node_by_title(self, title):
        """Find a node by its title.
        
        Args:
            title: The title to search for
            
        Returns:
            TreeNode or None if not found
        """
        if not title or not isinstance(title, str):
            return None
            
        # Log node titles for debugging
        self.debug_node_titles = []
        for node_id, node in self.tree_structure.nodeDict.items():
            node_title = node.title()
            self.debug_node_titles.append(f"Node {node_id}: '{node_title}'")
            if node_title == title:
                return node
                
        # Case-insensitive search as fallback
        for node_id, node in self.tree_structure.nodeDict.items():
            if node.title().lower() == title.lower():
                return node
        return None
        
    def get_debug_log(self):
        """Get the last API request log for debugging.
        
        Returns:
            String with debug information
        """
        debug_info = ""
        
        # Node titles for debugging
        if hasattr(self, 'debug_node_titles') and self.debug_node_titles:
            debug_info += "Node Title Mapping:\n"
            debug_info += "\n".join(self.debug_node_titles)
            debug_info += "\n\n"
            
        # Add API request log
        debug_info += "API Request Log:\n"
        debug_info += self.last_api_request_log
        
        return debug_info
    
    def _get_node_data_dict(self, node, depth=2):
        """Get node data as a dictionary.
        
        Args:
            node: The node to get data for
            depth: How many levels of children to include
            
        Returns:
            Dictionary with node data
        """
        # Make a serializable copy of the data
        data_copy = {}
        for key, value in node.data.items():
            if hasattr(value, '__call__'):  # Check if it's a method
                data_copy[key] = str(value)
            else:
                data_copy[key] = value
                
        result = {
            'id': str(node.uId),
            'title': node.title(),
            'data': data_copy,
            'format_type': node.formatRef.name,
            'children': []
        }
        
        # Add children if depth allows
        if depth > 0:
            for child in node.childList:
                result['children'].append(self._get_node_data_dict(child, depth-1))
        elif node.childList:
            # Indicate there are more children without including them
            result['has_more_children'] = True
            
        return result
    
    def execute_action(self, action_type, **kwargs):
        """Execute an action on the tree structure.
        
        Args:
            action_type: Type of action to perform (add_node, edit_node, etc.)
            **kwargs: Action-specific parameters
            
        Returns:
            Dictionary with result status and data
        """
        action_handlers = {
            'add_node': self._action_add_node,
            'edit_node': self._action_edit_node,
            'delete_node': self._action_delete_node,
            'move_node': self._action_move_node,
            'get_node': self._action_get_node,
            'search_nodes': self._action_search_nodes,
            'get_format_types': self._action_get_format_types,
            'create_format_type': self._action_create_format_type,
            'get_tree_structure': self._action_get_tree_structure,
            'get_node_path': self._action_get_node_path,
            'get_node_children': self._action_get_node_children,
            'get_node_siblings': self._action_get_node_siblings,
            'find_node_by_title': self._action_find_node_by_title
        }
        
        handler = action_handlers.get(action_type)
        if handler:
            try:
                return handler(**kwargs)
            except Exception as e:
                return {'status': 'error', 'message': str(e)}
        else:
            return {'status': 'error', 'message': f'Unknown action type: {action_type}'}
    
    def _action_add_node(self, parent_id=None, title='', data=None, format_type=None, position=None):
        """Add a new node to the tree.
        
        Args:
            parent_id: ID of parent node. If None, adds to the root of the tree.
            title: Title for the new node
            data: Dictionary of field data
            format_type: Type name for the node
            position: Position to insert at (None for end)
            
        Returns:
            Dictionary with result status and new node ID
        """
        # When parent_id is explicitly None, we'll add a root-level node
        if parent_id is None:
            # Create a new node with the specified format type
            if format_type and format_type in self.tree_structure.treeFormats:
                format_ref = self.tree_structure.treeFormats[format_type]
            else:
                # Default to first format if none specified
                format_names = self.tree_structure.treeFormats.typeNames()
                if format_names:
                    format_ref = self.tree_structure.treeFormats[format_names[0]]
                    format_type = format_names[0]  # Save for verification below
                else:
                    return {'status': 'error', 'message': 'No format types available'}
                    
            # Verify data is provided and has the required fields for this format type
            if not data:
                # Create default data based on format type
                data = {}
                if format_type == "HEADINGS":
                    data["Heading"] = title or "New Heading"
                elif format_type == "BULLETS":
                    data["Text"] = "New bullet item"
                elif format_type == "HEAD_PARA":
                    data["Heading"] = title or "New Heading"
                    data["Text"] = "New paragraph text"
                
                # Log a warning
                print(f"Warning: No data provided for node with format_type: {format_type}. Using default values.")
            
            # Create the new node
            new_node = treenode.TreeNode(format_ref)
            new_node.setInitDefaultData()
            
            # Set title if provided
            if title:
                new_node.setTitle(title)
                
            # Add as root node to the tree structure
            self.tree_structure.childList.append(new_node)
            self.tree_structure.addNodeDictRef(new_node)
            
            # Properly generate spots for the new node
            new_node.generateSpots(self.tree_structure.structSpot())
            
            # Skip the rest of the method that's for adding child nodes
            parent_node = None
        else:
            # Find parent node - try by ID first, then by title if ID fails
            parent_node = self._get_node_by_id(parent_id)
            
            # If not found and parent_id is a string that could be a title, try to find by title
            if not parent_node and isinstance(parent_id, str) and not parent_id.startswith("parent_"):
                parent_node = self.get_node_by_title(parent_id)
                
            if not parent_node:
                return {'status': 'error', 'message': f'Parent node not found: {parent_id}'}
        
        # Only add a child node if parent_node is not None (means we're not adding a root node)
        if parent_node is not None:
            # Determine position
            if position is not None:
                # If position is specified, find the reference node
                if position < len(parent_node.childList):
                    pos_ref_node = parent_node.childList[position]
                    insert_before = True
                else:
                    pos_ref_node = None
                    insert_before = True
            else:
                pos_ref_node = None
                insert_before = True
            
            # Add new node with default format (will be based on parent's childType or parent's format)
            new_node = parent_node.addNewChild(self.tree_structure, 
                                             pos_ref_node, 
                                             insert_before,
                                             title)
            
            # Override format if specified after creation
            if format_type and format_type in self.tree_structure.treeFormats:
                new_format = self.tree_structure.treeFormats[format_type]
                new_node.changeDataType(new_format)
        
        # Set additional data if provided (for both root and child nodes)
        if data:
            for field_name, value in data.items():
                if field_name in new_node.formatRef.fieldDict:
                    field = new_node.formatRef.fieldDict[field_name]
                    try:
                        new_node.setData(field, value)
                    except ValueError:
                        # If validation fails, we still continue with other fields
                        pass
                    
        # Update UI
        self.local_control.updateAll()
        
        return {
            'status': 'success', 
            'message': 'Node added',
            'node_id': str(new_node.uId)
        }
    
    def _action_edit_node(self, node_id=None, title=None, data=None, format_type=None):
        """Edit an existing node.
        
        Args:
            node_id: ID of node to edit. If None, uses selected node.
            title: New title for the node
            data: Dictionary of field data to update
            format_type: New format type for the node
            
        Returns:
            Dictionary with result status
        """
        # Find node - try by ID first, then by title
        node = self._get_node_by_id(node_id)
        
        # If not found and node_id is a string that could be a title, try to find by title
        if not node and isinstance(node_id, str) and not node_id.startswith("node_"):
            node = self.get_node_by_title(node_id)
            
        if not node:
            return {'status': 'error', 'message': f'Node not found: {node_id}'}
        
        # Update format if specified
        if format_type and format_type in self.tree_structure.treeFormats:
            old_format = node.formatRef
            new_format = self.tree_structure.treeFormats[format_type]
            if old_format != new_format:
                # Change the data type directly on the node
                node.changeDataType(new_format)
        
        # Update title if specified (updates the first field of the node)
        if title is not None:
            first_field = node.formatRef.fieldNames[0]
            # Use model setData to properly handle undo
            model_index = self.tree_model.createIndex(0, 0, node)
            self.tree_model.setData(model_index, title, Qt.EditRole, True)
        
        # Update data fields if specified
        if data:
            for field_name, value in data.items():
                if field_name in node.formatRef.fieldDict:
                    field = node.formatRef.fieldDict[field_name]
                    try:
                        node.setData(field, value)
                    except ValueError:
                        # If validation fails, we still continue with other fields
                        pass
        
        # Update UI to reflect changes
        self.local_control.updateTreeNode(node)
        
        return {'status': 'success', 'message': 'Node updated'}
    
    def _action_delete_node(self, node_id=None):
        """Delete a node from the tree.
        
        Args:
            node_id: ID of node to delete. If None, uses selected node.
            
        Returns:
            Dictionary with result status
        """
        # Find node - try by ID first, then by title
        node = self._get_node_by_id(node_id)
        
        # If not found and node_id is a string that could be a title, try to find by title
        if not node and isinstance(node_id, str) and not node_id.startswith("node_"):
            node = self.get_node_by_title(node_id)
            
        if not node:
            return {'status': 'error', 'message': f'Node not found: {node_id}'}
        
        # Get parent for selection after delete
        parent = node.parent
        
        # Use TreeLocalControl's delete command (handles undo/redo)
        spot = self.tree_structure.nodeDict.get(node.uId)
        self.local_control.deleteNode(spot)
        
        return {'status': 'success', 'message': 'Node deleted'}
    
    def _action_move_node(self, node_id=None, target_parent_id=None, position=None):
        """Move a node to a new parent or position.
        
        Args:
            node_id: ID of node to move. If None, uses selected node.
            target_parent_id: ID of new parent. If None, keeps same parent.
            position: Position in the parent's children list
            
        Returns:
            Dictionary with result status
        """
        # Find nodes - try by ID first, then by title
        node = self._get_node_by_id(node_id)
        if not node and isinstance(node_id, str) and not node_id.startswith("node_"):
            node = self.get_node_by_title(node_id)
        
        if not node:
            return {'status': 'error', 'message': f'Node not found: {node_id}'}
            
        # If no target parent specified, use current parent
        if target_parent_id:
            target_parent = self._get_node_by_id(target_parent_id)
            if not target_parent and isinstance(target_parent_id, str) and not target_parent_id.startswith("node_"):
                target_parent = self.get_node_by_title(target_parent_id)
                
            if not target_parent:
                return {'status': 'error', 'message': f'Target parent node not found: {target_parent_id}'}
        else:
            target_parent = node.parent
            
        # Get positions
        old_parent_spot = self.tree_structure.nodeDict.get(node.parent.uId)
        new_parent_spot = self.tree_structure.nodeDict.get(target_parent.uId)
        
        if position is None:
            position = len(target_parent.childList)
            
        # Use TreeLocalControl's move command (handles undo/redo)
        self.local_control.moveNode(node, old_parent_spot, new_parent_spot, position)
        
        return {'status': 'success', 'message': 'Node moved'}
    
    def _action_get_node(self, node_id=None, include_children=False, depth=1):
        """Get data for a specific node.
        
        Args:
            node_id: ID of node to get. If None, uses selected node.
            include_children: Whether to include children nodes
            depth: How many levels of children to include
            
        Returns:
            Dictionary with node data
        """
        # Find node - try by ID first, then by title
        node = self._get_node_by_id(node_id)
        
        # If not found and node_id is a string that could be a title, try to find by title
        if not node and isinstance(node_id, str) and not node_id.startswith("node_"):
            node = self.get_node_by_title(node_id)
            
        if not node:
            return {'status': 'error', 'message': f'Node not found: {node_id}'}
            
        node_data = self._get_node_data_dict(node, depth if include_children else 0)
        return {'status': 'success', 'data': node_data}
    
    def _action_search_nodes(self, search_text, title_only=False, exact_match=False, return_nodes=False):
        """Search for nodes containing specific text.
        
        Args:
            search_text: Text to search for
            title_only: If True, only search in node titles
            exact_match: If True, requires exact match rather than word-by-word
            return_nodes: If True, returns full node data rather than just metadata
            
        Returns:
            Dictionary with search results
        """
        results = []
        words = search_text.split()
        
        # Search in entire tree
        for node in self.tree_structure.nodeDict.values():
            # First handle exact match case if requested
            if exact_match:
                title = node.title()
                if (title_only and title == search_text) or \
                   (not title_only and any(value == search_text for value in node.data.values())):
                    if return_nodes:
                        results.append(self._get_node_data_dict(node, depth=1))
                    else:
                        results.append({
                            'id': str(node.uId),
                            'title': title,
                            'matches': ['exact_match']
                        })
                    continue
            
            # Otherwise do regular word search
            matches = node.wordSearch(words, title_only)
            if matches:
                if return_nodes:
                    results.append(self._get_node_data_dict(node, depth=1))
                else:
                    results.append({
                        'id': str(node.uId),
                        'title': node.title(),
                        'matches': matches
                    })
                
        return {
            'status': 'success', 
            'count': len(results),
            'results': results
        }
    
    def _action_get_format_types(self):
        """Get all available format types.
        
        Returns:
            Dictionary with format types information
        """
        formats = self.tree_structure.treeFormats
        format_data = {}
        
        for name, format_obj in formats.items():
            format_data[name] = {
                'name': name,
                'fields': format_obj.fieldNames,
                'icon_name': format_obj.iconName
            }
            
        return {
            'status': 'success',
            'formats': format_data
        }
    
    def _action_create_format_type(self, name, fields):
        """Create a new format type.
        
        Args:
            name: Name for the format type
            fields: List of field names
            
        Returns:
            Dictionary with result status
        """
        # Check if format already exists
        if name in self.tree_structure.treeFormats:
            return {'status': 'error', 'message': 'Format type already exists'}
            
        # Create new format through TreeLocalControl (handles undo/redo)
        self.local_control.createNewFormat(name, fields)
        
        return {'status': 'success', 'message': 'Format type created'}
    
    def _action_get_tree_structure(self, max_depth=3):
        """Get the overall tree structure.
        
        Args:
            max_depth: Maximum depth to include
            
        Returns:
            Dictionary with tree structure
        """
        # TreeStructure stores top-level nodes in its childList
        if not self.tree_structure.childList:
            # Return an empty tree structure but still success
            return {
                'status': 'success',
                'message': 'Tree structure is empty - no nodes found',
                'tree': {},
                'format_types': self._action_get_format_types()['formats']
            }
            
        # Get all root nodes and their data
        root_nodes = []
        for node in self.tree_structure.childList:
            root_nodes.append(self._get_node_data_dict(node, max_depth))
            
        # If there's only one root node, return it directly
        if len(root_nodes) == 1:
            tree_data = root_nodes[0]
        else:
            # If there are multiple root nodes, return them all in a list
            tree_data = {'root_nodes': root_nodes}
        
        return {
            'status': 'success',
            'tree': tree_data,
            'format_types': self._action_get_format_types()['formats']
        }
        
    def _action_get_node_path(self, node_id=None):
        """Get the path from root to the specified node.
        
        Args:
            node_id: ID of node or node title. If None, uses selected node.
            
        Returns:
            Dictionary with path information
        """
        # Find node - try by ID first, then by title
        node = self._get_node_by_id(node_id)
        if not node and isinstance(node_id, str) and not node_id.startswith("node_"):
            node = self.get_node_by_title(node_id)
            
        if not node:
            return {'status': 'error', 'message': f'Node not found: {node_id}'}
        
        # Build path from root to this node
        path = []
        current = node
        
        # Go up the tree to find ancestors
        while current and current.parent:  # Stop when we reach a root node
            parent = current.parent
            if not parent:
                break
                
            # Find position of this node in parent's children
            try:
                position = parent.childList.index(current)
            except ValueError:
                position = -1
                
            path.insert(0, {
                'id': str(current.uId),
                'title': current.title(),
                'parent_id': str(parent.uId),
                'position': position
            })
            
            current = parent
            
        # Add first root node if the current node is a top-level node
        if current in self.tree_structure.childList and node != current:
            path.insert(0, {
                'id': str(current.uId),
                'title': current.title(),
                'parent_id': None,
                'position': 0
            })
            
        return {
            'status': 'success',
            'path': path,
            'node': {
                'id': str(node.uId),
                'title': node.title()
            }
        }
        
    def _action_get_node_children(self, node_id=None, include_data=False):
        """Get all immediate children of a node.
        
        Args:
            node_id: ID of node or node title. If None, uses selected node.
            include_data: If True, includes full node data
            
        Returns:
            Dictionary with children information
        """
        # Find node - try by ID first, then by title
        node = self._get_node_by_id(node_id)
        if not node and isinstance(node_id, str) and not node_id.startswith("node_"):
            node = self.get_node_by_title(node_id)
            
        if not node:
            return {'status': 'error', 'message': f'Node not found: {node_id}'}
            
        # Get children
        children = []
        for index, child in enumerate(node.childList):
            if include_data:
                child_data = self._get_node_data_dict(child, depth=0)
                child_data['position'] = index
                children.append(child_data)
            else:
                children.append({
                    'id': str(child.uId),
                    'title': child.title(),
                    'position': index
                })
                
        return {
            'status': 'success',
            'parent': {
                'id': str(node.uId),
                'title': node.title()
            },
            'children': children,
            'count': len(children)
        }
        
    def _action_get_node_siblings(self, node_id=None, include_data=False):
        """Get all siblings of a node (nodes with the same parent).
        
        Args:
            node_id: ID of node or node title. If None, uses selected node.
            include_data: If True, includes full node data
            
        Returns:
            Dictionary with sibling information
        """
        # Find node - try by ID first, then by title
        node = self._get_node_by_id(node_id)
        if not node and isinstance(node_id, str) and not node_id.startswith("node_"):
            node = self.get_node_by_title(node_id)
            
        if not node:
            return {'status': 'error', 'message': f'Node not found: {node_id}'}
            
        # Get parent
        parent = node.parent
        if not parent:
            return {
                'status': 'success',
                'message': 'Node is root with no siblings',
                'siblings': []
            }
            
        # Get siblings
        siblings = []
        current_index = -1
        
        for index, sibling in enumerate(parent.childList):
            # Track the current node's position
            if sibling == node:
                current_index = index
                continue
                
            if include_data:
                sibling_data = self._get_node_data_dict(sibling, depth=0)
                sibling_data['position'] = index
                siblings.append(sibling_data)
            else:
                siblings.append({
                    'id': str(sibling.uId),
                    'title': sibling.title(),
                    'position': index
                })
                
        return {
            'status': 'success',
            'parent': {
                'id': str(parent.uId),
                'title': parent.title()
            },
            'node': {
                'id': str(node.uId),
                'title': node.title(),
                'position': current_index
            },
            'siblings': siblings,
            'count': len(siblings)
        }
        
    def _action_find_node_by_title(self, title, include_data=False):
        """Find a node by its exact title.
        
        Args:
            title: The title to search for
            include_data: If True, includes full node data
            
        Returns:
            Dictionary with node information if found
        """
        node = self.get_node_by_title(title)
        
        if not node:
            # Try case-insensitive search as fallback
            for node_id, n in self.tree_structure.nodeDict.items():
                if n.title().lower() == title.lower():
                    node = n
                    break
                    
        if not node:
            return {
                'status': 'error',
                'message': f'No node found with title: {title}'
            }
            
        # Return the node data
        if include_data:
            node_data = self._get_node_data_dict(node, depth=1)
            return {
                'status': 'success',
                'node': node_data
            }
        else:
            return {
                'status': 'success',
                'node': {
                    'id': str(node.uId),
                    'title': node.title(),
                    'format_type': node.formatRef.name
                }
            }
    
    def _get_node_by_id(self, node_id=None):
        """Helper to get a node by ID or selected node.
        
        Args:
            node_id: ID of node to get. If None, gets selected node.
            
        Returns:
            TreeNode instance or None if not found
        """
        if node_id:
            # Try to find by ID
            try:
                # Try parsing as UUID if it looks like a UUID
                if isinstance(node_id, str) and len(node_id) > 30 and '-' in node_id:
                    uid = uuid.UUID(node_id)
                    return self.tree_structure.nodeDict.get(uid)
                # If it's already a UUID object
                elif isinstance(node_id, uuid.UUID):
                    return self.tree_structure.nodeDict.get(node_id)
                # String but not a UUID - try iterating through nodes to find match
                else:
                    for node_uid, node in self.tree_structure.nodeDict.items():
                        if str(node_uid) == node_id:
                            return node
                    return None
            except (ValueError, TypeError):
                # Not a valid UUID, return None
                return None
        else:
            # Get selected node
            selection = self.selection
            if selection.hasSelection():
                selected_indexes = selection.selectedIndexes()
                if selected_indexes:
                    return selected_indexes[0].internalPointer().nodeRef
        
        # Fall back to first node in tree if nothing found/selected
        if self.tree_structure.childList:
            return self.tree_structure.childList[0]
        return None
    
    def process_agent_request(self, prompt):
        """Process a request from the user through the Anthropic API.
        
        Args:
            prompt: User's request text
            
        Returns:
            Dictionary with response from the agent
        """
        if not self.client:
            return {
                'status': 'error',
                'message': 'Anthropic API client not initialized. Please set API key.'
            }
        
        # Add user message to history
        self.message_history.append({"role": "user", "content": prompt})
            
        # Get current tree context
        tree_json = self.get_tree_json()
        format_types = self._action_get_format_types()['formats']
        
        # Make sure data is JSON serializable
        def sanitize_for_json(obj):
            if isinstance(obj, dict):
                return {k: sanitize_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_for_json(item) for item in obj]
            elif isinstance(obj, (int, float, str, bool)) or obj is None:
                return obj
            else:
                return str(obj)
        
        # Create conversation context from message history
        conversation_context = ""
        if len(self.message_history) > 1:
            conversation_context += "Recent conversation history:\n"
            # Include up to 10 recent messages
            for msg in self.message_history[-10:]:
                role_prefix = "USER" if msg["role"] == "user" else "ASSISTANT"
                conversation_context += f"[{role_prefix}] {msg['content']}\n"
            
            # Include recent action results
            if self.action_results:
                conversation_context += "\nRecent action results:\n"
                for action, result in self.action_results.items():
                    status = result.get('status', '')
                    message = result.get('message', '')
                    conversation_context += f"[ACTION] {action}: {status} - {message}\n"
                
            # Include last created node context
            if self.last_created_node_id:
                node_info = self._action_get_node(self.last_created_node_id)
                if node_info['status'] == 'success':
                    conversation_context += f"\nLast created/modified node:\n"
                    conversation_context += f"ID: {self.last_created_node_id}\n"
                    conversation_context += f"Title: {node_info['data'].get('title', '')}\n"
                
        # Load system prompt from SYS_PROMPT.md
        sys_prompt_path = pathlib.Path(__file__).parent / "SYS_PROMPT.md"
        try:
            with open(sys_prompt_path, 'r', encoding='utf-8') as f:
                sys_prompt_content = f.read()
        except FileNotFoundError:
            # Fallback to embedded system prompt if file not found
            sys_prompt_content = """
            # TreeLine AI Assistant System Prompt

            You are an AI assistant that helps modify a tree structure in the TreeLine application.
            
            You can perform actions like adding nodes, editing nodes, searching for nodes, etc.
            
            IMPORTANT GUIDELINES:
            
            1. When referring to nodes, use their TITLE rather than their ID
            2. Always specify the format_type when creating nodes
            3. For EVERY format_type, you MUST include a data object with field values
               - For HEADINGS: data: {"Heading": "Your title here"}
               - For BULLETS: data: {"Text": "Your bullet text here"}
               - For HEAD_PARA: data: {"Heading": "Your title", "Text": "Your paragraph text"}
            4. The data parameter is ALWAYS required when creating or modifying nodes
            
            When adding a root node, always use this pattern:
            ```json
            {
              "action": "add_node",
              "parameters": {
                "parent_id": null,
                "title": "My Root Node",
                "format_type": "HEADINGS",
                "data": {"Heading": "My Root Node"}
              }
            }
            ```
            """
        
        # Create system message using concatenation instead of f-strings
        system_message = """
        """ + sys_prompt_content + """
        
        Current tree structure:
        """ + tree_json + """
        
        Available node format types:
        """ + json.dumps(sanitize_for_json(format_types), indent=2) + """
        
        """ + conversation_context + """
        
        Respond with a JSON object that includes:
        - A friendly response to the user explaining what you will do or have done
        - The action you performed or want to perform
        - Required parameters for that action
        
        Your actions will be executed automatically. Make sure your JSON is
        correctly formatted with all required parameters for the action to succeed.
        
        If you need more information before performing an action, ask the user.
        If no action is needed, just respond with a helpful message.
        """
        
        try:
            # Prepare messages for API with history
            api_messages = []
            
            # Include up to 10 most recent messages, but skip the current one (added at the end)
            if len(self.message_history) > 1:
                for msg in self.message_history[:-1][-9:]:  # Last 9 messages excluding current
                    api_messages.append({"role": msg["role"], "content": msg["content"]})
            
            # Add current message
            api_messages.append({"role": "user", "content": prompt})
            
            # Log what we're sending
            try:
                # Avoid including the full system message which might have format specifiers
                log_data = {
                    "messages": api_messages,
                    "format_types": sanitize_for_json(format_types),
                    "last_created_node": self.last_created_node_id
                }
                
                # Try to include tree structure if valid
                try:
                    if isinstance(tree_json, str):
                        log_data["tree_structure"] = json.loads(tree_json)
                except:
                    log_data["tree_structure"] = "Error parsing tree structure"
                
                # Store log data for debugging
                self.last_api_request_log = json.dumps(log_data, indent=2)
            except Exception as e:
                self.last_api_request_log = f"Error creating log data: {str(e)}"
            
            # Send request to Anthropic API
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1024,
                temperature=0,
                system=system_message,
                messages=api_messages
            )
            
            # Parse response to extract action
            message_content = response.content[0].text
            
            # Try to parse JSON from the response
            try:
                # Check if the message contains JSON wrapped in ``` or not
                if "```json" in message_content:
                    parts = message_content.split("```json", 1)
                    if len(parts) > 1:
                        json_blocks = parts[1].split("```", 1)
                        if len(json_blocks) > 0:
                            json_str = json_blocks[0].strip()
                            action_data = json.loads(json_str)
                elif "```" in message_content:
                    parts = message_content.split("```", 1)
                    if len(parts) > 1:
                        json_blocks = parts[1].split("```", 1)
                        if len(json_blocks) > 0:
                            json_str = json_blocks[0].strip()
                            action_data = json.loads(json_str)
                else:
                    # Try to parse the entire message as JSON
                    action_data = json.loads(message_content)
                
                # Handle case where agent wants to perform multiple actions in sequence
                if 'actions' in action_data and isinstance(action_data['actions'], list):
                    # Execute each action in the list
                    action_results = []
                    
                    for action_item in action_data['actions']:
                        if 'action' in action_item and 'parameters' in action_item:
                            action_result = self.execute_action(
                                action_item['action'], 
                                **action_item['parameters']
                            )
                            
                            # Store result
                            action_item['action_result'] = action_result
                            action_results.append(action_result)
                            
                            # Track node creation
                            if action_item['action'] == 'add_node' and action_result['status'] == 'success':
                                self.last_created_node_id = action_result.get('node_id')
                                
                            # Store in context
                            self.action_results[action_item['action']] = action_result
                            
                    # Add all results to response
                    action_data['action_results'] = action_results
                    
                    # Print detailed execution information
                    print("AUTO-EXECUTING MULTIPLE ACTIONS:")
                    for i, (action_item, result) in enumerate(zip(action_data['actions'], action_results)):
                        action_name = action_item.get('action', 'unknown')
                        status = result.get('status', 'unknown')
                        message = result.get('message', 'No message')
                        print(f"  Action {i+1}: [{action_name}] {status} - {message}")
                            
                # Handle single action case
                elif 'action' in action_data and 'parameters' in action_data:
                    print(f"AUTO-EXECUTING ACTION: {action_data['action']}")
                    print(f"  Parameters: {action_data['parameters']}")
                    
                    action_result = self.execute_action(
                        action_data['action'], 
                        **action_data['parameters']
                    )
                    
                    # Add the action result to the response
                    action_data['action_result'] = action_result
                    
                    # Store the action result for context
                    self.action_results[action_data['action']] = action_result
                    
                    # Store the node ID if a node was created
                    if action_data['action'] == 'add_node' and action_result['status'] == 'success':
                        self.last_created_node_id = action_result.get('node_id')
                        print(f"  Created node with ID: {action_result.get('node_id')}")
                    
                    print(f"  Result: [{action_result.get('status', 'unknown')}] {action_result.get('message', 'No message')}")
                
                # Store assistant's response in history
                assistant_response = action_data.get('response', '')
                self.message_history.append({"role": "assistant", "content": assistant_response})
                
                return {
                    'status': 'success',
                    'response': assistant_response,
                    'data': action_data
                }
                
            except json.JSONDecodeError:
                # If not valid JSON, just return the text response
                self.message_history.append({"role": "assistant", "content": message_content})
                return {
                    'status': 'success',
                    'response': message_content,
                    'data': {'response': message_content}
                }
                
        except Exception as e:
            error_message = f'Error processing request: {str(e)}'
            # Store error in history for context
            self.message_history.append({"role": "assistant", "content": f"[ERROR] {error_message}"})
            return {
                'status': 'error',
                'message': error_message
            }


class AgentDialog(QDialog):
    """Dialog for interacting with the AI agent."""
    
    dialogShown = pyqtSignal(bool)
    
    def __init__(self, local_control, parent=None):
        """Initialize the agent dialog.
        
        Args:
            local_control: Reference to TreeLocalControl
            parent: Parent widget
        """
        super().__init__(parent)
        self.local_control = local_control
        self.agent_interface = AgentInterface(local_control)
        
        self.setWindowTitle(_('AI Assistant'))
        self.resize(800, 600)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface components."""
        main_layout = QVBoxLayout(self)
        
        # Log view for agent responses and system messages
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        
        # Input area for user prompts
        input_layout = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText(_("Enter your request for the AI assistant..."))
        self.prompt_input.returnPressed.connect(self.send_prompt)
        
        self.send_button = QPushButton(_("Send"))
        self.send_button.clicked.connect(self.send_prompt)
        
        input_layout.addWidget(self.prompt_input)
        input_layout.addWidget(self.send_button)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Auto-execution is now built-in, so this button is no longer needed
        # We'll add a status indicator instead
        self.status_indicator = QLabel(_("✓ Auto-execution enabled"))
        self.status_indicator.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.status_indicator.setToolTip(_("Agent actions are executed automatically"))
        button_layout.addWidget(self.status_indicator)
        
        # Debug button
        self.debug_button = QPushButton(_("Debug Info"))
        self.debug_button.clicked.connect(self.show_debug_info)
        button_layout.addWidget(self.debug_button)
        
        # Dump Tree button
        self.dump_button = QPushButton(_("Dump Tree"))
        self.dump_button.clicked.connect(self.dump_tree_info)
        button_layout.addWidget(self.dump_button)
        
        # API key configuration button
        self.api_key_button = QPushButton(_("Set API Key"))
        self.api_key_button.clicked.connect(self.configure_api_key)
        button_layout.addWidget(self.api_key_button)
        
        # Find by title button
        self.find_title_button = QPushButton(_("Find Node by Title"))
        self.find_title_button.clicked.connect(self.find_node_by_title)
        button_layout.addWidget(self.find_title_button)
        
        # Add node button
        self.add_node_button = QPushButton(_("Add Node"))
        self.add_node_button.clicked.connect(self.add_node_manually)
        button_layout.addWidget(self.add_node_button)
        
        # Show node structure button
        self.show_structure_button = QPushButton(_("Show Structure"))
        self.show_structure_button.clicked.connect(self.show_node_structure)
        button_layout.addWidget(self.show_structure_button)
        
        # Status bar and progress
        status_layout = QHBoxLayout()
        self.status_label = QLabel(_("Ready"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        
        # Add components to main layout
        main_layout.addWidget(self.log_view)
        main_layout.addLayout(input_layout)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(status_layout)
        
        # Initial log message
        self.log_system_message(_("Welcome to the TreeLine AI Assistant. Enter a request to get started."))
        
        # Check if API key is configured
        if not self.agent_interface._get_api_key():
            self.log_system_message(_("Please configure your Anthropic API key to use the assistant."), "error")
    
    def log_system_message(self, message, level="info"):
        """Add a system message to the log.
        
        Args:
            message: Message text
            level: Message level (info, warning, error)
        """
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Format based on level
        format = QTextCharFormat()
        if level == "error":
            format.setForeground(QColor(200, 0, 0))
        elif level == "warning":
            format.setForeground(QColor(200, 150, 0))
        else:
            format.setForeground(QColor(100, 100, 100))
            
        # Add timestamp and level
        self.log_view.setTextCursor(cursor)
        cursor.insertText(f"[SYSTEM] ", format)
        cursor.insertText(f"{message}\n")
        
        # Scroll to bottom
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)
    
    def log_user_message(self, message):
        """Add a user message to the log.
        
        Args:
            message: Message text
        """
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        format = QTextCharFormat()
        format.setForeground(QColor(0, 100, 200))
        
        self.log_view.setTextCursor(cursor)
        cursor.insertText(f"[USER] ", format)
        cursor.insertText(f"{message}\n")
        
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)
    
    def log_agent_message(self, message):
        """Add an agent message to the log.
        
        Args:
            message: Message text
        """
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        format = QTextCharFormat()
        format.setForeground(QColor(0, 150, 0))
        
        self.log_view.setTextCursor(cursor)
        cursor.insertText(f"[ASSISTANT] ", format)
        cursor.insertText(f"{message}\n")
        
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)
    
    def log_action_result(self, result):
        """Add an action result to the log.
        
        Args:
            result: Result data
        """
        level = "info" if result.get('status') == 'success' else "error"
        message = result.get('message', str(result))
        
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        format = QTextCharFormat()
        if level == "error":
            format.setForeground(QColor(200, 0, 0))
        else:
            format.setForeground(QColor(100, 150, 100))
            
        self.log_view.setTextCursor(cursor)
        cursor.insertText(f"[ACTION] ", format)
        cursor.insertText(f"{message}\n")
        
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)
    
    def send_prompt(self):
        """Send the current prompt to the agent."""
        prompt = self.prompt_input.text().strip()
        if not prompt:
            return
            
        # Log user message
        self.log_user_message(prompt)
        
        # Clear input
        self.prompt_input.clear()
        
        # Check API key
        if not self.agent_interface._get_api_key():
            self.log_system_message(_("Please configure your Anthropic API key to use the assistant."), "error")
            return
            
        # Update UI state
        self.send_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText(_("Processing request..."))
        
        # Process request in background (simplified - would use QThread in full implementation)
        QApplication.processEvents()
        
        try:
            # Call agent interface
            result = self.agent_interface.process_agent_request(prompt)
            
            if result['status'] == 'success':
                # Log agent response
                self.log_agent_message(result['response'])
                
                # If multi-action was executed, log all results
                if 'data' in result and 'action_results' in result['data']:
                    self.log_system_message(_("Executed multiple actions:"))
                    for action_result in result['data']['action_results']:
                        self.log_action_result(action_result)
                        
                    # Add executed actions summary to agent's response
                    success_count = sum(1 for r in result['data']['action_results'] if r.get('status') == 'success')
                    error_count = len(result['data']['action_results']) - success_count
                    if error_count == 0:
                        self.log_agent_message(_("✅ Successfully executed all requested actions."))
                    else:
                        self.log_agent_message(_("⚠️ Executed {0} actions successfully, {1} actions failed.").format(
                            success_count, error_count))
                
                # If single action was executed, log the result
                elif 'data' in result and 'action_result' in result['data']:
                    self.log_system_message(_("Executed action:"))
                    action_result = result['data']['action_result']
                    self.log_action_result(action_result)
                    
                    # Add executed action summary to agent's response
                    if action_result.get('status') == 'success':
                        self.log_agent_message(_("✅ Successfully executed the requested action."))
                    else:
                        self.log_agent_message(_("❌ Failed to execute the requested action: {0}").format(
                            action_result.get('message', 'Unknown error')))
                    
                # Refresh tree view if data was modified
                self.local_control.updateAll()
                    
            else:
                # Log error
                self.log_system_message(result['message'], "error")
                
        except Exception as e:
            self.log_system_message(f"Error: {str(e)}", "error")
            
        # Restore UI state
        self.send_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(_("Ready"))
    
    def configure_api_key(self):
        """Show dialog to configure API key."""
        current_key = self.agent_interface._get_api_key()
        masked_key = '••••••••' + current_key[-4:] if current_key else ''
        
        # Simple input dialog
        new_key, ok = QInputDialog.getText(
            self, _("Configure API Key"),
            _("Enter your Anthropic API key:"),
            QLineEdit.Password, masked_key
        )
        
        if ok and new_key:
            # Save the new key
            self.agent_interface.set_api_key(new_key)
            self.log_system_message(_("API key configured successfully."))
        elif ok:
            # User clicked OK with empty key
            self.log_system_message(_("API key cannot be empty."), "warning")
            
    def show_debug_info(self):
        """Show debug information in a dialog."""
        debug_info = self.agent_interface.get_debug_log()
        if debug_info:
            debug_dialog = QDialog(self)
            debug_dialog.setWindowTitle(_("API Debug Information"))
            debug_dialog.resize(800, 800)
            
            layout = QVBoxLayout(debug_dialog)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setLineWrapMode(QTextEdit.NoWrap)
            text_edit.setPlainText(debug_info)
            
            close_button = QPushButton(_("Close"))
            close_button.clicked.connect(debug_dialog.accept)
            
            layout.addWidget(text_edit)
            layout.addWidget(close_button)
            
            debug_dialog.exec_()
        else:
            self.log_system_message(_("No debug information available yet."), "warning")
    
    def find_node_by_title(self):
        """Find a node by its title and show information about it."""
        title, ok = QInputDialog.getText(
            self, _("Find Node by Title"),
            _("Enter the node title to search for:"),
            QLineEdit.Normal, ""
        )
        
        if ok and title:
            node = self.agent_interface.get_node_by_title(title)
            if node:
                # Display node information
                node_info = self.agent_interface._get_node_data_dict(node)
                sanitized_info = {}
                for key, value in node_info.items():
                    if key != "children":  # Skip lengthy children info
                        sanitized_info[key] = value
                
                info_text = json.dumps(sanitized_info, indent=2)
                self.log_system_message(f"Found node with title '{title}':")
                self.log_system_message(info_text)
                
                # Select the node in the tree view
                for node_id, tree_node in self.agent_interface.tree_structure.nodeDict.items():
                    if tree_node == node:
                        self.log_system_message(f"Node ID: {node_id}")
                        break
            else:
                self.log_system_message(f"No node found with title '{title}'", "warning")
                
    def add_node_manually(self):
        """Add a node manually through a dialog."""
        # Get parent node title first
        parent_title, ok = QInputDialog.getText(
            self, _("Add Node - Step 1"),
            _("Enter the PARENT node title (leave empty for root):"),
            QLineEdit.Normal, ""
        )
        
        if not ok:
            return
            
        # Find parent node
        parent_node = None
        if parent_title:
            parent_node = self.agent_interface.get_node_by_title(parent_title)
            if not parent_node:
                self.log_system_message(f"Parent node with title '{parent_title}' not found", "error")
                return
        else:
            # Use root node
            parent_node = self.agent_interface.tree_structure.rootNode
            
        # Get new node title
        new_title, ok = QInputDialog.getText(
            self, _("Add Node - Step 2"),
            _("Enter the new node's title:"),
            QLineEdit.Normal, ""
        )
        
        if not ok or not new_title:
            return
            
        # Create the node
        result = self.agent_interface._action_add_node(
            parent_id=str(parent_node.uId) if parent_node else None,
            title=new_title
        )
        
        # Log the result
        if result['status'] == 'success':
            self.log_system_message(f"Successfully added node '{new_title}' under '{parent_node.title() if parent_node else 'root'}'")
            self.log_system_message(f"New node ID: {result.get('node_id')}")
        else:
            self.log_system_message(result.get('message', 'Unknown error'), "error")
            
    def show_node_structure(self):
        """Show the structure of all nodes in the tree."""
        try:
            # Get structure data
            structure_data = self.agent_interface._action_get_tree_structure()
            
            if structure_data['status'] == 'success':
                # Show structure in a dialog
                structure_dialog = QDialog(self)
                structure_dialog.setWindowTitle(_("Tree Structure"))
                structure_dialog.resize(800, 800)
                
                layout = QVBoxLayout(structure_dialog)
                
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                text_edit.setLineWrapMode(QTextEdit.NoWrap)
                
                # Create hierarchical view of node titles and IDs
                def format_structure(node, level=0):
                    node_text = "  " * level + f"- {node.get('title', 'Untitled')} (ID: {node.get('id', 'unknown')})\n"
                    child_text = ""
                    for child in node.get('children', []):
                        child_text += format_structure(child, level + 1)
                    return node_text + child_text
                    
                structure_text = format_structure(structure_data['tree'])
                text_edit.setPlainText(structure_text)
                
                # Log ID to title mapping
                mapping_button = QPushButton(_("Log ID->Title Mapping"))
                mapping_button.clicked.connect(self.log_node_id_mapping)
                
                close_button = QPushButton(_("Close"))
                close_button.clicked.connect(structure_dialog.accept)
                
                button_layout = QHBoxLayout()
                button_layout.addWidget(mapping_button)
                button_layout.addWidget(close_button)
                
                layout.addWidget(text_edit)
                layout.addLayout(button_layout)
                
                structure_dialog.exec_()
            else:
                self.log_system_message(f"Error getting tree structure: {structure_data.get('message', 'unknown error')}", "error")
        except Exception as e:
            self.log_system_message(f"Error displaying tree structure: {str(e)}", "error")
            
            # Add an alternative method to show nodes
            self.log_node_id_mapping()
            
    def log_node_id_mapping(self):
        """Log all node IDs and their titles for reference."""
        self.log_system_message(_("Node ID to Title Mapping:"))
        
        try:
            if not self.agent_interface.tree_structure.nodeDict:
                self.log_system_message("No nodes found in tree", level="warning")
                return
                
            for node_id, node in self.agent_interface.tree_structure.nodeDict.items():
                try:
                    title = node.title()
                    self.log_system_message(f"ID: {node_id} => Title: '{title}'", level="info")
                except Exception as e:
                    self.log_system_message(f"Error getting title for node {node_id}: {str(e)}", level="error")
        except Exception as e:
            self.log_system_message(f"Error mapping nodes: {str(e)}", level="error")
            
    def execute_actions_from_log(self):
        """Parse and execute JSON actions from the latest agent message in the log."""
        # Get all text from the log
        log_text = self.log_view.toPlainText()
        
        # Find the latest assistant message
        assistant_blocks = log_text.split("[ASSISTANT] ")
        if len(assistant_blocks) < 2:
            self.log_system_message(_("No assistant messages found in log."), "warning")
            return
            
        latest_message = assistant_blocks[-1].split("\n[")[0]
        
        # Find JSON in the message
        json_content = None
        
        # Check for code blocks
        if "```json" in latest_message:
            # Extract JSON from code block
            parts = latest_message.split("```json")
            if len(parts) > 1:
                # Get the content between ```json and the next ```
                json_block = parts[1].split("```", 1)[0].strip()
                try:
                    json_content = json.loads(json_block)
                except json.JSONDecodeError:
                    self.log_system_message(_("Failed to parse JSON from code block."), "error")
                    return
        elif "```" in latest_message:
            # Try regular code block
            parts = latest_message.split("```")
            if len(parts) > 1:
                # Get the content of the first code block
                json_block = parts[1].strip()
                try:
                    json_content = json.loads(json_block)
                except json.JSONDecodeError:
                    self.log_system_message(_("Failed to parse JSON from code block."), "error")
                    return
        else:
            # Try to find JSON-like content in the message (between { and })
            try:
                # Find all text between { and } with the most outer brackets
                import re
                json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', latest_message)
                if json_matches:
                    # Try parsing each match starting with the longest one
                    json_matches.sort(key=len, reverse=True)
                    for json_str in json_matches:
                        try:
                            json_content = json.loads(json_str)
                            if isinstance(json_content, dict) and ('action' in json_content or 'actions' in json_content):
                                break
                        except json.JSONDecodeError:
                            continue
            except:
                pass
                
        if not json_content:
            self.log_system_message(_("No JSON content found in the latest message."), "error")
            return
            
        # Process the JSON content
        action_results = []
        
        # Check for 'actions' list in the content
        if 'actions' in json_content and isinstance(json_content['actions'], list):
            self.log_system_message(_("Executing multiple actions..."))
            # Process each action in the list
            for action_item in json_content['actions']:
                if 'action' in action_item and 'parameters' in action_item:
                    action_name = action_item['action']
                    parameters = action_item['parameters']
                    
                    # Execute the action
                    try:
                        self.log_system_message(f"Executing action '{action_name}' with parameters: {parameters}")
                        result = self.agent_interface.execute_action(action_name, **parameters)
                        action_results.append(result)
                        self.log_action_result(result)
                        
                        # Special handling for node creation
                        if action_name == 'add_node' and result['status'] == 'success':
                            self.agent_interface.last_created_node_id = result.get('node_id')
                            self.log_system_message(f"Created node with ID: {result.get('node_id')}")
                            
                    except Exception as e:
                        import traceback
                        error_msg = f"Error executing action '{action_name}': {str(e)}"
                        self.log_system_message(error_msg, "error")
                        self.log_system_message(traceback.format_exc(), "error")
                        action_results.append({'status': 'error', 'message': error_msg})
                        
        # Check for single action
        elif 'action' in json_content and 'parameters' in json_content:
            self.log_system_message(_("Executing single action..."))
            action_name = json_content['action']
            parameters = json_content['parameters']
            
            # Execute the action
            try:
                self.log_system_message(f"Executing action '{action_name}' with parameters: {parameters}")
                result = self.agent_interface.execute_action(action_name, **parameters)
                action_results.append(result)
                self.log_action_result(result)
                
                # Special handling for node creation
                if action_name == 'add_node' and result['status'] == 'success':
                    self.agent_interface.last_created_node_id = result.get('node_id')
                    self.log_system_message(f"Created node with ID: {result.get('node_id')}")
            except Exception as e:
                import traceback
                error_msg = f"Error executing action '{action_name}': {str(e)}"
                self.log_system_message(error_msg, "error")
                self.log_system_message(traceback.format_exc(), "error")
                action_results.append({'status': 'error', 'message': error_msg})
                
        else:
            self.log_system_message(_("JSON content does not contain valid action definition."), "error")
            return
            
        # Update the UI
        self.log_system_message(_("Updating UI with tree changes..."))
        self.local_control.updateAll()
        
        # Summarize the results
        success_count = sum(1 for r in action_results if r.get('status') == 'success')
        error_count = sum(1 for r in action_results if r.get('status') == 'error')
        
        if error_count == 0:
            self.log_system_message(_("✅ All actions executed successfully."))
            
            # Print more details to console for debugging
            print(f"Successfully executed {len(action_results)} actions:")
            for i, result in enumerate(action_results):
                print(f"  Action {i+1}: {result.get('message', 'OK')}")
                
            # Show specific message for empty trees
            if not self.agent_interface.tree_structure.childList:
                self.log_system_message(_("Note: Tree is still empty. Make sure to include proper data fields when creating nodes."), "warning")
            else:
                # Log the structure change
                self.log_system_message(_("Tree structure now contains {} root nodes.").format(len(self.agent_interface.tree_structure.childList)))
        else:
            self.log_system_message(_("⚠️ {0} actions executed successfully, {1} actions failed.").format(success_count, error_count))
            
            # Print more details to console for debugging
            print(f"Action execution results: {success_count} succeeded, {error_count} failed")
            for i, result in enumerate(action_results):
                status = result.get('status', 'unknown')
                message = result.get('message', 'No message')
                print(f"  Action {i+1}: [{status}] {message}")
            
    def dump_tree_info(self):
        """Dump complete tree structure information for debugging."""
        self.log_system_message(_("Tree Structure Debug Info:"), level="info")
        
        try:
            # Check for empty tree
            if not hasattr(self.agent_interface.tree_structure, 'childList') or not self.agent_interface.tree_structure.childList:
                self.log_system_message("Tree has no root nodes", level="warning")
                return
                
            # Log root nodes
            self.log_system_message(f"Root nodes count: {len(self.agent_interface.tree_structure.childList)}", level="info")
            for i, node in enumerate(self.agent_interface.tree_structure.childList):
                try:
                    self.log_system_message(f"Root node {i}: {node.title()} (ID: {node.uId})", level="info")
                except Exception as e:
                    self.log_system_message(f"Error getting root node {i} info: {str(e)}", level="error")
            
            # Log total node count
            self.log_system_message(f"Total nodes in tree: {len(self.agent_interface.tree_structure.nodeDict)}", level="info")
            
            # Log available format types
            self.log_system_message("Available format types:", level="info")
            try:
                for name in self.agent_interface.tree_structure.treeFormats:
                    self.log_system_message(f"  - {name}", level="info")
            except Exception as e:
                self.log_system_message(f"Error getting format types: {str(e)}", level="error")
                
            # Log direct tree attributes
            self.log_system_message("TreeStructure attributes:", level="info")
            for attr in dir(self.agent_interface.tree_structure):
                if not attr.startswith('_') and attr not in ['nodeDict', 'childList', 'treeFormats']:
                    try:
                        value = getattr(self.agent_interface.tree_structure, attr)
                        if not callable(value):
                            self.log_system_message(f"  - {attr}: {value}", level="info")
                    except:
                        pass
            
        except Exception as e:
            self.log_system_message(f"Error dumping tree info: {str(e)}", level="error")
    
    def closeEvent(self, event):
        """Handle dialog close event.
        
        Args:
            event: Close event
        """
        self.dialogShown.emit(False)
        super().closeEvent(event)


def _(text):
    """Placeholder for translation function."""
    return text


# Testing code (remove in production)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    dialog = AgentDialog(None)
    dialog.show()
    sys.exit(app.exec_())