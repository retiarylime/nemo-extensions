#!/usr/bin/python3
# -*- coding: UTF-8 -*-

############################################################################
##                                                                        ##
## Nemo Restore Tabs - Automatically save and restore opened tabs        ##
##                                                                        ##
## Copyright (C) 2025  Linux Mint                                         ##
##                                                                        ##
## This program is free software: you can redistribute it and/or modify   ##
## it under the terms of the GNU General Public License as published by   ##
## the Free Software Foundation, either version 3 of the License, or      ##
## (at your option) any later version.                                    ##
##                                                                        ##
## This program is distributed in the hope that it will be useful,        ##
## but WITHOUT ANY WARRANTY; without even the implied warranty of         ##
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          ##
## GNU General Public License for more details.                           ##
##                                                                        ##
## You should have received a copy of the GNU General Public License      ##
## along with this program.  If not, see <http://www.gnu.org/licenses/>.  ##
##                                                                        ##
############################################################################

"""Nemo extension to automatically save and restore opened tabs."""

import os
import json
import time
import subprocess
from urllib.parse import unquote

import gi
gi.require_version('Nemo', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import GObject, Nemo, Gtk, Gio, GLib

TABS_STORAGE_FILE = os.path.expanduser("~/.config/nemo/restore-tabs.json")

class TabsManager:
    """Manages saving and restoring of tab information."""
    
    @staticmethod
    def save_tabs(tabs_data):
        """Save tabs data to storage file."""
        try:
            os.makedirs(os.path.dirname(TABS_STORAGE_FILE), exist_ok=True)
            with open(TABS_STORAGE_FILE, 'w') as f:
                json.dump({
                    'tabs': tabs_data,
                    'timestamp': time.time(),
                    'version': '1.0'
                }, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving tabs: {e}")
            return False
    
    @staticmethod
    def load_tabs():
        """Load tabs data from storage file."""
        try:
            if os.path.exists(TABS_STORAGE_FILE):
                with open(TABS_STORAGE_FILE, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data  # Old format
                    return data.get('tabs', [])  # New format
        except Exception as e:
            print(f"Error loading tabs: {e}")
        return []
    
    @staticmethod
    def get_current_directory():
        """Get the current directory of the active Nemo window."""
        try:
            result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                window_title = result.stdout.strip()
                print(f"Current window title: {window_title}")
        except Exception as e:
            print(f"Error getting current directory: {e}")
        return None

class NemoRestoreTabsExtension(GObject.GObject, Nemo.MenuProvider, Nemo.NameAndDescProvider):
    """Main extension class for tab saving and restoration."""
    
    def __init__(self):
        """Initialize the extension."""
        super().__init__()
        self.windows = {}  # Track windows for monitoring
        print("Nemo Restore Tabs extension initialized")
    
    def get_background_items(self, window, current_folder):
        """Return context menu items for background clicks."""
        if not current_folder or current_folder.get_uri_scheme() != 'file':
            return []
        
        items = []
        
        # Manual save option
        save_item = Nemo.MenuItem(
            name='NemoRestoreTabs::manual_save',
            label='Save Current Tabs Now',
            tip='Manually save all currently open tabs'
        )
        save_item.connect('activate', self._manual_save_tabs, window)
        items.append(save_item)
        
        # Manual restore option
        saved_tabs = TabsManager.load_tabs()
        if saved_tabs:
            restore_item = Nemo.MenuItem(
                name='NemoRestoreTabs::manual_restore',
                label=f'Restore Saved Tabs ({len(saved_tabs)})',
                tip=f'Manually restore {len(saved_tabs)} saved tabs'
            )
            restore_item.connect('activate', self._manual_restore_tabs, window)
            items.append(restore_item)
        
        return items
    
    def get_file_items(self, window, files):
        """Return context menu items for file selections."""
        return []
    
    def get_name_and_desc(self):
        """Return plugin name and description."""
        return [("nemo-restore-tabs:::Automatically saves and restores previously opened tabs")]
    
    def _manual_save_tabs(self, menu_item, window):
        """Manually save current tabs."""
        try:
            # For now, just save the current location
            current_slot = window.get_active_slot()
            if current_slot:
                current_location = current_slot.get_current_location()
                if current_location:
                    path = unquote(current_location.get_uri())
                    if path.startswith('file://'):
                        path = path[7:]
                        tabs_data = [{
                            'path': path,
                            'timestamp': time.time(),
                            'active': True
                        }]
                        
                        if TabsManager.save_tabs(tabs_data):
                            print(f"Saved current location: {path}")
                        else:
                            print("Failed to save tabs")
        except Exception as e:
            print(f"Error in manual save: {e}")
    
    def _manual_restore_tabs(self, menu_item, window):
        """Manually restore saved tabs."""
        try:
            saved_tabs = TabsManager.load_tabs()
            if saved_tabs:
                print(f"Would restore {len(saved_tabs)} tabs")
                # For now, just print the tabs
                for tab in saved_tabs:
                    print(f"  - {tab.get('path', 'Unknown')}")
        except Exception as e:
            print(f"Error in manual restore: {e}")
    
    def _global_restore_check(self):
        """Check if we should perform global restoration."""
        try:
            # This is a fallback method to try restoration without a specific window
            saved_tabs = TabsManager.load_tabs()
            if saved_tabs:
                print(f"Global restore check: found {len(saved_tabs)} saved tabs")
                # Try to open tabs using subprocess as a fallback
                self._restore_via_subprocess(saved_tabs)
        except Exception as e:
            print(f"Error in global restore check: {e}")
        return False  # Don't repeat
    
    def _restore_via_subprocess(self, tabs_data):
        """Restore tabs by launching new Nemo instances."""
        try:
            import subprocess
            for tab_data in tabs_data:
                path = tab_data.get('path', '')
                if path and os.path.exists(path):
                    print(f"Opening Nemo for path: {path}")
                    subprocess.Popen(['nemo', path], 
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Error in subprocess restore: {e}")
    
    def get_background_items(self, window, current_folder):
        """Return context menu items for background clicks."""
        if not current_folder or current_folder.get_uri_scheme() != 'file':
            return []
        
        # This method is called when the user right-clicks, but we can use it
        # to trigger our initialization logic
        self._ensure_window_setup(window)
        
        # Optional: Still provide manual menu items for power users
        items = []
        
        # Manual save option (optional)
        save_item = Nemo.MenuItem(
            name='NemoRestoreTabs::manual_save',
            label=_('Save Current Tabs Now'),
            tip=_('Manually save currently open tabs')
        )
        save_item.connect('activate', self._manual_save_tabs, window)
        items.append(save_item)
        
        # Show restore status
        saved_tabs = TabsManager.load_tabs()
        if saved_tabs:
            info_item = Nemo.MenuItem(
                name='NemoRestoreTabs::info',
                label=_('Auto-Restore: {} saved tabs').format(len(saved_tabs)),
                tip=_('Tabs are automatically saved and restored')
            )
            # Make it non-clickable by not connecting any handler
            items.append(info_item)
            
            # Add a manual restore option for testing
            restore_item = Nemo.MenuItem(
                name='NemoRestoreTabs::manual_restore',
                label=_('Restore Saved Tabs Now'),
                tip=_('Manually restore saved tabs')
            )
            restore_item.connect('activate', self._manual_restore_tabs, window)
            items.append(restore_item)
        
        return items
    
    def get_file_items(self, window, files):
        """Return context menu items for file selections."""
        # Use this opportunity to set up the window if we haven't already
        self._ensure_window_setup(window)
        return []  # No items for file selections
    
    def _ensure_window_setup(self, window):
        """Ensure window is properly set up with monitoring and restoration."""
        window_id = id(window)
        
        if window_id not in self.windows:
            print(f"Setting up new window {window_id}")
            self._setup_window_monitoring(window)
            
            # Auto-restore tabs if this is a new window and we haven't restored yet
            if window_id not in self.restored_windows:
                print(f"Auto-restoring tabs for window {window_id}")
                # Use a small delay to ensure window is fully loaded
                GLib.timeout_add(100, self._auto_restore_tabs, window)
                self.restored_windows.add(window_id)
    
    def _setup_window_monitoring(self, window):
        """Set up automatic monitoring for a window."""
        window_id = id(window)
        
        if window_id not in self.windows:
            # Set up monitoring for this window
            self.windows[window_id] = {
                'window': window,
                'save_timer': None,
                'last_save_time': 0
            }
            
            print(f"Monitoring window {window_id}")
            
            # Connect to window signals for tab changes
            try:
                # Monitor location changes (when user navigates)
                if hasattr(window, 'connect'):
                    # Try to connect to relevant signals
                    try:
                        window.connect('tab-added', self._on_tab_changed)
                        print("Connected to tab-added signal")
                    except:
                        pass
                    try:
                        window.connect('tab-removed', self._on_tab_changed)
                        print("Connected to tab-removed signal")
                    except:
                        pass
                    
                # Also monitor the active slot for location changes
                slot = window.get_active_slot()
                if slot and hasattr(slot, 'connect'):
                    try:
                        slot.connect('location-changed', self._on_location_changed, window)
                        print("Connected to location-changed signal")
                    except:
                        pass
                    
            except Exception as e:
                print(f"Could not connect to window signals: {e}")
            
            # Schedule initial save after a delay to capture current state
            GLib.timeout_add(2000, self._initial_save, window)
    
    def _initial_save(self, window):
        """Perform initial save of current tabs."""
        try:
            tabs_data = TabsManager.get_current_tabs(window)
            if tabs_data:
                TabsManager.save_tabs(tabs_data)
                print(f"Initial save: {len(tabs_data)} tabs saved")
        except Exception as e:
            print(f"Error in initial save: {e}")
        return False  # Don't repeat
    
    def _on_tab_changed(self, window, *args):
        """Handle tab addition/removal."""
        self._schedule_auto_save(window)
    
    def _on_location_changed(self, slot, window):
        """Handle location changes within a tab."""
        self._schedule_auto_save(window)
    
    def _schedule_auto_save(self, window):
        """Schedule an automatic save after a delay."""
        window_id = id(window)
        
        if window_id not in self.windows:
            return
        
        window_data = self.windows[window_id]
        
        # Cancel any existing timer
        if window_data['save_timer']:
            GLib.source_remove(window_data['save_timer'])
        
        # Schedule new save
        window_data['save_timer'] = GLib.timeout_add(
            AUTO_SAVE_DELAY, 
            self._auto_save_tabs, 
            window
        )
    
    def _auto_save_tabs(self, window):
        """Automatically save current tabs."""
        try:
            current_time = time.time()
            window_id = id(window)
            
            if window_id in self.windows:
                window_data = self.windows[window_id]
                
                # Avoid saving too frequently
                if current_time - window_data['last_save_time'] < 1.0:
                    return False  # Don't repeat timer
                
                tabs_data = TabsManager.get_current_tabs(window)
                if tabs_data:
                    TabsManager.save_tabs(tabs_data)
                    window_data['last_save_time'] = current_time
                    print(f"Auto-saved {len(tabs_data)} tabs")
                
                window_data['save_timer'] = None
        except Exception as e:
            print(f"Error in auto-save: {e}")
        
        return False  # Don't repeat timer
    
    def _auto_restore_tabs(self, window):
        """Automatically restore tabs when window opens."""
        try:
            saved_tabs = TabsManager.load_tabs()
            if saved_tabs:
                print(f"Auto-restoring {len(saved_tabs)} saved tabs")
                TabsManager.restore_tabs_to_window(window, saved_tabs)
                return True
            else:
                print("No saved tabs to restore")
        except Exception as e:
            print(f"Error in auto-restore: {e}")
        return False
    
    def _manual_restore_tabs(self, menu_item, window):
        """Manually restore saved tabs."""
        try:
            saved_tabs = TabsManager.load_tabs()
            if saved_tabs:
                TabsManager.restore_tabs_to_window(window, saved_tabs)
                print(f"Manually restored {len(saved_tabs)} tabs")
                
                # Show notification
                try:
                    notification = Gio.Notification.new(_("Tabs Restored"))
                    notification.set_body(_("Restored {} saved tabs").format(len(saved_tabs)))
                    Gio.Application.get_default().send_notification(None, notification)
                except:
                    pass
            else:
                print("No saved tabs to restore")
        except Exception as e:
            print(f"Error in manual restore: {e}")
    
    def _delayed_restore(self, window, tabs_data):
        """Perform delayed restoration of tabs."""
        try:
            TabsManager.restore_tabs_to_window(window, tabs_data)
        except Exception as e:
            print(f"Error in delayed restore: {e}")
        return False  # Don't repeat
    
    def _manual_save_tabs(self, menu_item, window):
        """Manually save current tabs."""
        try:
            tabs_data = TabsManager.get_current_tabs(window)
            TabsManager.save_tabs(tabs_data)
            
            # Show notification
            try:
                notification = Gio.Notification.new(_("Tabs Saved"))
                notification.set_body(_("Current tabs have been saved manually"))
                Gio.Application.get_default().send_notification(None, notification)
            except:
                pass
                
        except Exception as e:
            print(f"Error in manual save: {e}")
    
    def get_name_and_desc(self):
        """Return plugin name and description."""
        return [(f"nemo-restore-tabs:::{PLUGIN_DESCRIPTION}")]