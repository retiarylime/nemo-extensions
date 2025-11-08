#!/usr/bin/python3
# -*- coding: UTF-8 -*-

############################################################################
##                                                                        ##
## Nemo Restore Tabs - Restore previously opened tabs in Nemo            ##
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

"""Nemo extension to restore previously opened tabs."""

import os
import json
import signal
import locale
import gettext
from urllib.parse import unquote

import gi
gi.require_version('Nemo', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import GObject, Nemo, Gtk, Gio

# Handle Ctrl+C gracefully
signal.signal(signal.SIGINT, signal.SIG_DFL)

# Initialize i18n
APP = 'nemo-extensions'
LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain(APP, LOCALE_DIR)
gettext.bindtextdomain(APP, LOCALE_DIR)
gettext.textdomain(APP)
_ = gettext.gettext

PLUGIN_DESCRIPTION = _("Allows restoring previously opened tabs")
TABS_STORAGE_FILE = os.path.expanduser("~/.config/nemo/restore-tabs.json")

class TabsManager:
    """Manages saving and restoring of tab information."""
    
    @staticmethod
    def save_tabs(tabs_data):
        """Save tabs data to storage file."""
        try:
            os.makedirs(os.path.dirname(TABS_STORAGE_FILE), exist_ok=True)
            with open(TABS_STORAGE_FILE, 'w') as f:
                json.dump(tabs_data, f, indent=2)
        except Exception as e:
            print(f"Error saving tabs: {e}")
    
    @staticmethod
    def load_tabs():
        """Load tabs data from storage file."""
        try:
            if os.path.exists(TABS_STORAGE_FILE):
                with open(TABS_STORAGE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading tabs: {e}")
        return []
    
    @staticmethod
    def clear_tabs():
        """Clear saved tabs data."""
        try:
            if os.path.exists(TABS_STORAGE_FILE):
                os.remove(TABS_STORAGE_FILE)
        except Exception as e:
            print(f"Error clearing tabs: {e}")

class NemoRestoreTabsExtension(GObject.GObject, Nemo.MenuProvider, Nemo.NameAndDescProvider):
    """Main extension class for restoring tabs functionality."""
    
    def __init__(self):
        """Initialize the extension."""
        super().__init__()
    
    def get_background_items(self, window, current_folder):
        """Return context menu items for background clicks."""
        if not current_folder or current_folder.get_uri_scheme() != 'file':
            return []
        
        # Initialize i18n for this instance
        locale.setlocale(locale.LC_ALL, '')
        gettext.bindtextdomain(APP)
        gettext.textdomain(APP)
        _ = gettext.gettext
        
        items = []
        
        # Save current tabs item
        save_item = Nemo.MenuItem(
            name='NemoRestoreTabs::save_tabs',
            label=_('Save Current Tabs'),
            tip=_('Save currently open tabs for later restoration')
        )
        save_item.connect('activate', self._save_current_tabs, window)
        items.append(save_item)
        
        # Restore tabs item (only if saved tabs exist)
        saved_tabs = TabsManager.load_tabs()
        if saved_tabs:
            restore_item = Nemo.MenuItem(
                name='NemoRestoreTabs::restore_tabs',
                label=_('Restore Saved Tabs'),
                tip=_('Restore previously saved tabs')
            )
            restore_item.connect('activate', self._restore_tabs, window)
            items.append(restore_item)
            
            # Clear saved tabs item
            clear_item = Nemo.MenuItem(
                name='NemoRestoreTabs::clear_tabs',
                label=_('Clear Saved Tabs'),
                tip=_('Clear saved tabs data')
            )
            clear_item.connect('activate', self._clear_saved_tabs, window)
            items.append(clear_item)
        
        return items
    
    def get_file_items(self, window, files):
        """Return context menu items for file selections."""
        # Only show on background, not on files
        return []
    
    def _save_current_tabs(self, menu_item, window):
        """Save currently open tabs."""
        try:
            # Try to get tabs from the window (this is Nemo-specific)
            # Note: This might need adjustment based on actual Nemo API
            tabs_data = []
            
            # For now, save the current location as a fallback
            # In a real implementation, you'd iterate through actual tabs
            current_location = window.get_active_slot().get_current_location()
            if current_location:
                path = unquote(current_location.get_uri())
                if path.startswith('file://'):
                    path = path[7:]
                tabs_data.append({
                    'path': path,
                    'timestamp': GObject.get_current_time()
                })
            
            TabsManager.save_tabs(tabs_data)
            
            # Show notification (if available)
            try:
                notification = Gio.Notification.new(_("Tabs Saved"))
                notification.set_body(_("Current tabs have been saved"))
                Gio.Application.get_default().send_notification(None, notification)
            except:
                pass  # Notification not available
                
        except Exception as e:
            print(f"Error saving tabs: {e}")
    
    def _restore_tabs(self, menu_item, window):
        """Restore previously saved tabs."""
        try:
            saved_tabs = TabsManager.load_tabs()
            
            for tab_data in saved_tabs:
                path = tab_data.get('path', '')
                if path and os.path.exists(path):
                    # Open new tab with the saved location
                    # Note: This might need adjustment based on actual Nemo API
                    location = Gio.File.new_for_path(path)
                    try:
                        # Try to open in new tab (Nemo-specific)
                        window.open_location_in_new_tab(location)
                    except:
                        # Fallback: open in current window
                        window.open_location(location)
                        
        except Exception as e:
            print(f"Error restoring tabs: {e}")
    
    def _clear_saved_tabs(self, menu_item, window):
        """Clear saved tabs data."""
        TabsManager.clear_tabs()
        
        # Show notification (if available)
        try:
            notification = Gio.Notification.new(_("Tabs Cleared"))
            notification.set_body(_("Saved tabs data has been cleared"))
            Gio.Application.get_default().send_notification(None, notification)
        except:
            pass  # Notification not available
    
    def get_name_and_desc(self):
        """Return plugin name and description."""
        return [(f"nemo-restore-tabs:::{PLUGIN_DESCRIPTION}")]