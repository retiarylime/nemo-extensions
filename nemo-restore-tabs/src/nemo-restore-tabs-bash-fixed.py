#!/usr/bin/env python3

import gi
gi.require_version('Nemo', '3.0')
from gi.repository import Nemo, GObject
import subprocess
import os
import json
import time

CONFIG_DIR = os.path.expanduser("~/.config/nemo")
TABS_FILE = os.path.join(CONFIG_DIR, "restore-tabs.json")

class NemoRestoreTabsExtension(GObject.GObject, Nemo.MenuProvider):
    """Extension that runs script in terminal and parses saved results."""
    
    def __init__(self):
        super().__init__()
        self.parsing_done = False  # Flag to prevent multiple parsing
    
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
        """Run the script headless and auto-parse results."""
        try:
            print("🚀 Starting headless tab collection...")
            self.parsing_done = False  # Reset flag for new run
            
            # Create a wrapper script that saves output automatically
            wrapper_script = '''#!/bin/bash
# Run the original script and capture ALL output
OUTPUT_FILE="/tmp/nemo_auto_results.txt"
FULL_OUTPUT_FILE="/tmp/nemo_full_output.txt"

# Clean old results
rm -f "$OUTPUT_FILE" "$FULL_OUTPUT_FILE"

echo "=== WRAPPER SCRIPT STARTING ===" > "$FULL_OUTPUT_FILE"

# Run the script and save full output, wait for it to complete
bash /tmp/test_nemo_tabs.sh >> "$FULL_OUTPUT_FILE" 2>&1
SCRIPT_EXIT_CODE=$?

echo "=== WRAPPER SCRIPT COMPLETED (exit code: $SCRIPT_EXIT_CODE) ===" >> "$FULL_OUTPUT_FILE"

# Extract just the RESULTS section and TAB lines
grep -A 10 "RESULTS:" "$FULL_OUTPUT_FILE" > "$OUTPUT_FILE" 2>/dev/null

# If that didn't work, just copy the TAB lines
if [ ! -s "$OUTPUT_FILE" ]; then
    grep "^TAB[12]:" "$FULL_OUTPUT_FILE" > "$OUTPUT_FILE" 2>/dev/null
fi

echo "=== WRAPPER EXTRACTION DONE ===" >> "$FULL_OUTPUT_FILE"
'''
            
            # Write wrapper script
            with open('/tmp/nemo_auto_wrapper.sh', 'w') as f:
                f.write(wrapper_script)
            os.chmod('/tmp/nemo_auto_wrapper.sh', 0o755)
            
            print("📄 Wrapper script created, running headless...")
            
            # Run wrapper headless with proper environment
            env = os.environ.copy()
            env['DISPLAY'] = os.environ.get('DISPLAY', ':0')
            process = subprocess.Popen(['bash', '/tmp/nemo_auto_wrapper.sh'], 
                                     env=env,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
            
            # Schedule auto-parsing after script completion
            import threading
            print("⏱️  Scheduling result parsing...")
            
            # Wait a bit longer to ensure script completes
            threading.Timer(3.0, self._check_and_parse_results).start()   # 3 seconds
            threading.Timer(7.0, self._check_and_parse_results).start()   # 7 seconds
            threading.Timer(12.0, self._check_and_parse_results).start()  # 12 seconds
            threading.Timer(18.0, self._check_and_parse_results).start()  # 18 seconds
            
        except Exception as e:
            print(f"❌ Error running script: {e}")
    
    def _check_and_parse_results(self):
        """Check if results are ready and parse them."""
        try:
            if self.parsing_done:
                return  # Already parsed, don't do it again
                
            result_file = "/tmp/nemo_auto_results.txt"
            full_output_file = "/tmp/nemo_full_output.txt"
            
            # Check if the wrapper script has completed
            if os.path.exists(full_output_file):
                with open(full_output_file, 'r') as f:
                    content = f.read()
                
                # Look for completion marker
                if "=== WRAPPER SCRIPT COMPLETED" in content:
                    print(f"🔍 Script completed, parsing results...")
                    self.parsing_done = True  # Mark as done
                    self._auto_parse_results()
                elif os.path.getsize(full_output_file) > 100:  # Has some content
                    print(f"🔍 Script still running, but has content ({os.path.getsize(full_output_file)} bytes)...")
                else:
                    print(f"⏳ Script still starting at {time.strftime('%H:%M:%S')}...")
            else:
                print(f"⏳ Output file not created yet at {time.strftime('%H:%M:%S')}...")
        except Exception as e:
            print(f"❌ Error checking results: {e}")
    
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
                        with open(TABS_FILE, 'w') as f:
                            json.dump(data, f, indent=2)
                        print(f"✅ Saved {len(tabs)} tabs to {TABS_FILE}")
                        
                        # Verify the saved file
                        with open(TABS_FILE, 'r') as f:
                            verify_data = json.load(f)
                        print(f"✅ JSON file verified: {len(verify_data.get('tabs', []))} tabs")
                        
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
            
            # Try to parse JSON
            try:
                with open(TABS_FILE, 'r') as f:
                    data = json.load(f)
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
            
            # Run the command
            result = subprocess.run(nemo_command, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            
            if result.returncode == 0:
                print(f"✅ Successfully restored {len(tab_paths)} tabs!")
                print("   New Nemo window opened with all tabs")
            else:
                print(f"❌ Command failed with return code: {result.returncode}")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()}")
                if result.stdout:
                    print(f"   Output: {result.stdout.strip()}")
            
        except FileNotFoundError:
            print("❌ nemo command not found")
        except subprocess.TimeoutExpired:
            print("❌ Command timed out")
        except Exception as e:
            print(f"❌ Error restoring tabs: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")