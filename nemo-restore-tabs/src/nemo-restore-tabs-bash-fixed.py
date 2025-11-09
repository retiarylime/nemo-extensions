#!/usr/bin/env python3

import gi
gi.require_version('Nemo', '3.0')
from gi.repository import Nemo, GObject
import subprocess
import os
import json
import time
import threading
import shutil

CONFIG_DIR = os.path.expanduser("~/.config/nemo")
TABS_FILE = os.path.join(CONFIG_DIR, "restore-tabs.json")

# Simple locks to prevent duplicate execution
_save_lock = threading.Lock()
_restore_lock = threading.Lock()
_parsing_flag = threading.Event()  # Flag to prevent duplicate parsing

class NemoRestoreTabsExtension(GObject.GObject, Nemo.MenuProvider):
    """Extension that runs script and immediately parses results."""
    
    def get_background_items(self, window, file):
        """Add menu items when right-clicking on background."""
        item1 = Nemo.MenuItem(
            name='NemoRestoreTabs::save_headless',
            label='🚀 Save Tabs (Headless)',
            tip='Run tab script headless and auto-save results'
        )
        item1.connect('activate', self._run_script_callback)
        
        item2 = Nemo.MenuItem(
            name='NemoRestoreTabs::restore_tabs',
            label='📂 Restore Saved Tabs',
            tip='Restore saved tabs using nemo --tabs command'
        )
        item2.connect('activate', self._restore_tabs_callback)
        
        return [item1, item2]
    
    def _run_script_callback(self, menu_item):
        """Run the bash script headless and save results immediately."""
        if not _save_lock.acquire(blocking=False):
            print("⏳ Save operation already in progress, skipping...")
            return
            
        try:
            print("🚀 Starting headless tab collection...")
            
            # Small delay to ensure window is ready
            time.sleep(0.5)
            
            # Get the active Nemo window ID dynamically
            try:
                # Find active Nemo window
                result = subprocess.run(['xdotool', 'getactivewindow'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    active_window = result.stdout.strip()
                    print(f"🔍 Active window: {active_window}")
                    
                    # Verify it's a Nemo window
                    result = subprocess.run(['xdotool', 'getwindowname', active_window], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 and 'nemo' in result.stdout.lower():
                        window_id = active_window
                        print(f"✅ Using active Nemo window: {window_id}")
                    else:
                        # Fall back to searching for Nemo windows
                        result = subprocess.run(['xdotool', 'search', '--class', 'nemo'], 
                                              capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            windows = result.stdout.strip().split('\n')
                            window_id = windows[-1]  # Use the last (most recent) window
                            print(f"🔧 Using most recent Nemo window: {window_id}")
                        else:
                            window_id = "119537674"  # Fallback
                            print(f"⚠️ Using fallback window ID: {window_id}")
                else:
                    window_id = "119537674"  # Fallback
                    print(f"⚠️ Failed to detect active window, using fallback: {window_id}")
            except Exception as e:
                window_id = "119537674"  # Fallback
                print(f"⚠️ Error detecting window ({e}), using fallback: {window_id}")
            
            # Create wrapper script
            print("📄 Wrapper script created, running headless...")
            
            with open('/tmp/nemo_auto_wrapper.sh', 'w') as f:
                f.write(f'''#!/bin/bash
# Wrapper script for headless tab capture

echo "=== WRAPPER SCRIPT STARTING ===" > /tmp/nemo_full_output.txt
/tmp/test_nemo_tabs.sh {window_id} >> /tmp/nemo_full_output.txt 2>&1
echo "=== WRAPPER SCRIPT COMPLETED (exit code: $?) ===" >> /tmp/nemo_full_output.txt
echo "=== WRAPPER EXTRACTION DONE ===" >> /tmp/nemo_full_output.txt
''')
            
            os.chmod('/tmp/nemo_auto_wrapper.sh', 0o755)
            
            # Run script in background and immediately parse results
            print("🔄 Running script in background...")
            print("🧵 Starting background monitor thread...")
            
            def monitor_script():
                print("👀 Monitoring script execution...")
                
                # Clear any previous parsing flag
                _parsing_flag.clear()
                
                # Use bash -c with explicit DISPLAY for better X11 compatibility
                cmd = ['bash', '-c', f'DISPLAY=:0 /tmp/nemo_auto_wrapper.sh']
                print(f"🚀 Starting subprocess: {' '.join(cmd)}")
                
                process = subprocess.Popen(cmd, 
                                         stdout=subprocess.DEVNULL, 
                                         stderr=subprocess.DEVNULL)
                print(f"📋 Process PID: {process.pid}")
                
                # Start backup timer with a function that checks the flag
                def backup_parse():
                    if not _parsing_flag.is_set():
                        print("⏰ Backup timer: script still running...")
                        _parsing_flag.set()
                        self._auto_parse_results()
                
                backup_timer = threading.Timer(8.0, backup_parse)
                backup_timer.start()
                print("⏰ Backup timer started (8 seconds)")
                
                # Monitor for completion with timeout
                try:
                    print("⌛ Waiting for script to complete...")
                    process.wait(timeout=15)  # Maximum 15 seconds
                    backup_timer.cancel()  # Cancel backup if script finishes first
                    print("⏰ Backup timer cancelled - script finished")
                    
                    # Only parse if not already done by backup timer
                    if not _parsing_flag.is_set():
                        _parsing_flag.set()
                        if process.returncode == 0:
                            print("✅ Script completed with exit code: 0")
                            print("🔍 Script finished, parsing results immediately...")
                            self._auto_parse_results()
                        else:
                            print(f"❌ Script failed with exit code: {process.returncode}")
                            # Try to get some debug info
                            if os.path.exists('/tmp/nemo_full_output.txt'):
                                with open('/tmp/nemo_full_output.txt', 'r') as f:
                                    print(f"🔍 Debug output: {f.read()[:500]}...")
                    else:
                        print("🔄 Results already parsed by backup timer")
                        
                except subprocess.TimeoutExpired:
                    print("⏰ Script timed out after 15 seconds")
                    backup_timer.cancel()
                    process.kill()
                    if not _parsing_flag.is_set():
                        _parsing_flag.set()
                        print("🔍 Attempting to parse any partial results...")
                        self._auto_parse_results()
            
            thread = threading.Thread(target=monitor_script)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            print(f"❌ Error running script: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
        finally:
            # Only release the lock if we acquired it
            if _save_lock.locked():
                _save_lock.release()
    
    def _auto_parse_results(self):
        """Copy and display the exact output from test_nemo_tabs.sh script."""
        try:
            print("🔄 Copying output from test_nemo_tabs.sh...")
            
            # First, read the full output to show everything
            full_output_file = "/tmp/nemo_full_output.txt"
            if os.path.exists(full_output_file):
                print("📄 Full script output:")
                print("="*50)
                with open(full_output_file, 'r') as f:
                    full_content = f.read()
                    print(full_content)
                print("="*50)
                
                # Extract and show just the RESULTS section
                lines = full_content.split('\n')
                
                # Look for the last occurrence of RESULTS: to avoid confusion with restore output
                results_section_start = -1
                for i, line in enumerate(lines):
                    if line.strip() == "RESULTS:":
                        results_section_start = i
                
                tab1_path = None
                tab2_path = None
                
                if results_section_start >= 0:
                    print(f"🔍 Found RESULTS section at line {results_section_start + 1}")
                    
                    # Process lines after the RESULTS: line
                    for i in range(results_section_start + 1, len(lines)):
                        line = lines[i].strip()
                        print(f"  Processing line {i+1}: '{line}'")
                        
                        if line.startswith('TAB1:'):
                            tab1_path = line[5:].strip()
                            print(f"  ✅ Found TAB1: '{tab1_path}'")
                        elif line.startswith('TAB2:'):
                            tab2_path = line[5:].strip()
                            print(f"  ✅ Found TAB2: '{tab2_path}'")
                        elif line.startswith('====') and (tab1_path or tab2_path):
                            # Stop when we hit the separator after getting results
                            print(f"  ✅ End of RESULTS section")
                            break
                else:
                    print("❌ No RESULTS: section found")
                
                print(f"🎯 Final extracted paths:")
                print(f"   TAB1: '{tab1_path}'")
                print(f"   TAB2: '{tab2_path}'")
                
                # Display results exactly like the manual script
                print("RESULTS:")
                print(f"TAB1: {tab1_path if tab1_path else ''}")
                print(f"TAB2: {tab2_path if tab2_path else ''}")
                
                # Save to JSON if we have valid paths
                tabs = []
                print("🔍 Validating paths...")
                
                if tab1_path:
                    print(f"   Checking TAB1: '{tab1_path}'")
                    if tab1_path.startswith('/'):
                        print(f"   TAB1 starts with '/' ✅")
                        if os.path.exists(tab1_path):
                            print(f"   TAB1 path exists ✅")
                            tabs.append({
                                'path': tab1_path,
                                'timestamp': time.time(),
                                'window_tab_index': 1,
                                'active': True
                            })
                            print(f"   TAB1 added to tabs list ✅")
                        else:
                            print(f"   TAB1 path does not exist ❌")
                    else:
                        print(f"   TAB1 does not start with '/' ❌")
                else:
                    print("   TAB1 is empty ❌")
                
                if tab2_path:
                    print(f"   Checking TAB2: '{tab2_path}'")
                    if tab2_path.startswith('/'):
                        print(f"   TAB2 starts with '/' ✅")
                        if os.path.exists(tab2_path):
                            print(f"   TAB2 path exists ✅")
                            if tab2_path != tab1_path:
                                print(f"   TAB2 is different from TAB1 ✅")
                                tabs.append({
                                    'path': tab2_path,
                                    'timestamp': time.time(),
                                    'window_tab_index': 2,
                                    'active': False
                                })
                                print(f"   TAB2 added to tabs list ✅")
                            else:
                                print(f"   TAB2 is same as TAB1, skipping ❌")
                        else:
                            print(f"   TAB2 path does not exist ❌")
                    else:
                        print(f"   TAB2 does not start with '/' ❌")
                else:
                    print("   TAB2 is empty ❌")
                
                print(f"📊 Total valid tabs: {len(tabs)}")
                
                if tabs:
                    os.makedirs(CONFIG_DIR, exist_ok=True)
                    data = {
                        'timestamp': time.time(),
                        'tabs': tabs,
                        'method': 'full_output_copy'
                    }
                    
                    print(f"💾 Saving {len(tabs)} tabs to JSON...")
                    try:
                        # Ensure the config directory exists
                        os.makedirs(CONFIG_DIR, exist_ok=True)
                        
                        # Write to temporary file first to avoid corruption
                        temp_file = TABS_FILE + '.tmp'
                        with open(temp_file, 'w') as f:
                            json.dump(data, f, indent=2)
                        
                        # Verify the temporary file before moving
                        with open(temp_file, 'r') as f:
                            verify_data = json.load(f)
                        print(f"✅ Temporary JSON file verified: {len(verify_data.get('tabs', []))} tabs")
                        
                        # Atomically move the verified file
                        import shutil
                        shutil.move(temp_file, TABS_FILE)
                        print(f"✅ Saved {len(tabs)} tabs to {TABS_FILE}")
                        
                    except Exception as save_error:
                        print(f"❌ Error saving JSON: {save_error}")
                else:
                    print("❌ No valid tabs found")
            else:
                print("❌ No full output file found")
            
        except Exception as e:
            print(f"❌ Error copying output: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
    
    def _restore_tabs_callback(self, menu_item):
        """Restore saved tabs using nemo --tabs command."""
        # Wait a moment if save operation is in progress
        if _save_lock.locked():
            print("⏳ Waiting for save operation to complete...")
            time.sleep(2)
            
        if not _restore_lock.acquire(blocking=False):
            print("⏳ Restore operation already in progress, skipping...")
            return
            
        try:
            print("📂 Starting tab restoration...")
            
            # Check if saved tabs file exists
            if not os.path.exists(TABS_FILE):
                print("❌ No saved tabs found")
                print(f"   Expected file: {TABS_FILE}")
                return
            
            print(f"📁 Reading tabs from: {TABS_FILE}")
            
            # Check file size first
            file_size = os.path.getsize(TABS_FILE)
            print(f"📊 File size: {file_size} bytes")
            
            if file_size == 0:
                print("❌ Saved tabs file is empty")
                return
            
            # Read and display raw file content for debugging
            with open(TABS_FILE, 'r') as f:
                raw_content = f.read()
            print(f"📄 Raw file content ({len(raw_content)} chars):")
            print(f"'{raw_content[:200]}{'...' if len(raw_content) > 200 else ''}")
            
            # Force a fresh read of the file
            import importlib
            import sys
            if TABS_FILE in sys.modules:
                importlib.reload(sys.modules[TABS_FILE])
            
            # Try to parse JSON with better error handling
            try:
                with open(TABS_FILE, 'r') as f:
                    content = f.read().strip()
                
                # Check for common corruption patterns
                if content.count('{') != content.count('}'):
                    print(f"❌ JSON has mismatched braces: {content.count('{')} {{ vs {content.count('}')} }}")
                    print(f"   Attempting to fix...")
                    
                    # Try to find the last valid closing brace
                    if content.endswith('}}'):
                        content = content[:-1]
                        print(f"   Removed extra closing brace")
                
                data = json.loads(content)
                print(f"✅ JSON parsed successfully")
            except json.JSONDecodeError as json_error:
                print(f"❌ JSON decode error: {json_error}")
                print(f"   Error at position: {json_error.pos if hasattr(json_error, 'pos') else 'unknown'}")
                return
            
            tabs = data.get('tabs', [])
            if not tabs:
                print("❌ No tabs in saved file")
                print(f"   Available keys: {list(data.keys())}")
                return
            
            print(f"📋 Found {len(tabs)} saved tabs:")
            
            # Debug: Show what we actually read
            print(f"🔍 File timestamp: {data.get('timestamp', 'unknown')}")
            for i, tab in enumerate(tabs):
                path = tab.get('path', 'unknown')
                tab_timestamp = tab.get('timestamp', 'unknown')
                print(f"  {i+1}. {path} (saved at: {tab_timestamp})")
            
            # Build the nemo --tabs command
            tab_paths = []
            for i, tab in enumerate(tabs):
                path = tab.get('path', '')
                if path and os.path.exists(path):
                    tab_paths.append(path)
                    print(f"  {i+1}. {path}")
                else:
                    print(f"  {i+1}. {path} (path not found, skipping)")
            
            if not tab_paths:
                print("❌ No valid tab paths found")
                return
            
            # Build and execute nemo --tabs command
            nemo_command = ['nemo', '--tabs'] + tab_paths
            print(f"🚀 Executing: {' '.join(nemo_command)}")
            
            # Run the command - nemo --tabs returns immediately
            try:
                # Use Popen for truly non-blocking execution
                process = subprocess.Popen(nemo_command, 
                                         stdout=subprocess.DEVNULL, 
                                         stderr=subprocess.DEVNULL)
                
                print(f"✅ Successfully restored {len(tab_paths)} tabs!")
                print("   New tabs opened in existing Nemo window")
                print(f"   Process ID: {process.pid}")
                    
            except FileNotFoundError:
                print("❌ nemo command not found")
            except Exception as e:
                print(f"❌ Error restoring tabs: {e}")
                
        except Exception as e:
            print(f"❌ Error in restore function: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
        finally:
            # Only release the lock if we acquired it
            if _restore_lock.locked():
                _restore_lock.release()