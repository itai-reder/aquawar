#!/usr/bin/env python3
"""
Script to systematically replace old history function calls with new unified function calls.
This fixes the double increment bug by changing player_index + 1 to player_index.
"""

import re
import sys

def replace_history_calls(file_path):
    """Replace add_history_entry_with_retry calls with add_history_entry_unified calls."""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to match the old function calls
    # This regex captures multi-line calls to add_history_entry_with_retry
    pattern = r'(\s*)self\.game\.add_history_entry_with_retry\(\s*\n\s*self\.player_index \+ 1,\s*(.*?)\s*\)'
    
    def replacement_func(match):
        indent = match.group(1)
        args = match.group(2)
        
        # Create the replacement
        old_call = f"{indent}# OLD: self.game.add_history_entry_with_retry(\n{indent}#     self.player_index + 1, {args}\n{indent}# )"
        new_call = f"{indent}# NEW: Use unified history function with 0-based player index\n{indent}self.game.add_history_entry_unified(\n{indent}    self.player_index, {args}\n{indent})"
        
        return f"{old_call}\n{new_call}"
    
    # Replace multiline calls
    content = re.sub(pattern, replacement_func, content, flags=re.DOTALL | re.MULTILINE)
    
    # Handle single line calls (pattern for calls that are all on one line)
    single_line_pattern = r'(\s*)self\.game\.add_history_entry_with_retry\(self\.player_index \+ 1,\s*(.*?)\)'
    
    def single_line_replacement(match):
        indent = match.group(1)
        args = match.group(2)
        
        old_call = f"{indent}# OLD: self.game.add_history_entry_with_retry(self.player_index + 1, {args})"
        new_call = f"{indent}# NEW: Use unified history function with 0-based player index\n{indent}self.game.add_history_entry_unified(self.player_index, {args})"
        
        return f"{old_call}\n{new_call}"
    
    content = re.sub(single_line_pattern, single_line_replacement, content)
    
    return content

def main():
    file_path = '/home/itai/git/aquawar/aquawar/ai/ollama_player.py'
    
    print(f"Processing {file_path}...")
    
    try:
        # Restore from backup
        import shutil
        shutil.copy(file_path + '.backup3', file_path)
        print("Restored from backup")
        
        new_content = replace_history_calls(file_path)
        
        with open(file_path, 'w') as f:
            f.write(new_content)
            
        print("Replacements completed successfully!")
        
        # Count replacements
        old_count = new_content.count('add_history_entry_with_retry')
        new_count = new_content.count('add_history_entry_unified') 
        print(f"Remaining old calls: {old_count}")
        print(f"New unified calls: {new_count}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())