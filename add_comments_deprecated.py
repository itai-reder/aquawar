#!/usr/bin/env python3
"""
Script to add OLD: and NEW: comment prefixes to the deprecated file.
"""

import re

def add_comment_prefixes_deprecated(file_path):
    """Add OLD: and NEW: comment prefixes to history function calls in deprecated file."""
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    modified_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this line contains add_history_entry_unified that isn't already commented
        if 'self.game.add_history_entry_unified(' in line and not line.strip().startswith('#'):
            # Get the indentation
            indent = len(line) - len(line.lstrip())
            indent_str = ' ' * indent
            
            # Add OLD: comment for this line (change back to old function name)
            old_line = line.replace('add_history_entry_unified(', 'add_history_entry_with_retry(')
            old_comment = f"{indent_str}# OLD: {old_line.strip()}\n"
            
            # Find the closing parenthesis for multi-line calls
            paren_count = line.count('(') - line.count(')')
            j = i
            while paren_count > 0 and j < len(lines) - 1:
                j += 1
                paren_count += lines[j].count('(') - lines[j].count(')')
                if paren_count > 0:
                    old_line = lines[j].strip()
                    old_comment += f"{indent_str}# OLD: {old_line}\n"
            
            # Add the OLD comment and NEW comment
            modified_lines.append(old_comment)
            modified_lines.append(f"{indent_str}# NEW: Use unified history function\n")
            
            # Add the current line (and any continuation lines)
            for k in range(i, j + 1):
                modified_lines.append(lines[k])
            
            i = j + 1
        else:
            modified_lines.append(line)
            i += 1
    
    return ''.join(modified_lines)

def main():
    file_path = '/home/itai/git/aquawar/deprecated/utils/ollama_client.py'
    
    print(f"Adding comment prefixes to {file_path}...")
    
    try:
        new_content = add_comment_prefixes_deprecated(file_path)
        
        with open(file_path, 'w') as f:
            f.write(new_content)
            
        print("Comment prefixes added successfully!")
        
        # Count occurrences
        old_count = new_content.count('# OLD:')
        new_count = new_content.count('# NEW:')
        unified_count = new_content.count('add_history_entry_unified')
        
        print(f"OLD comments added: {old_count}")
        print(f"NEW comments added: {new_count}")
        print(f"Total unified calls: {unified_count}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    main()