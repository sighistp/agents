"""Smart emoji replacement: only replace in template section, keep in script."""
import os
import re

src_dir = r'C:\Users\lahm\Desktop\Many AgentS\frontend\src'

for root, dirs, files in os.walk(src_dir):
    for f in files:
        if not f.endswith('.vue'):
            continue
        path = os.path.join(root, f)
        content = open(path, 'r', encoding='utf-8').read()
        
        # Split into template and script sections
        template_match = re.search(r'<template>(.*?)</template>', content, re.DOTALL)
        script_match = re.search(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
        
        if not template_match:
            continue
            
        template = template_match.group(1)
        script = script_match.group(1) if script_match else ''
        
        # Only replace in template, not in script
        emoji_pattern = re.compile('[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]')
        template_emoji = emoji_pattern.findall(template)
        
        if not template_emoji:
            continue
        
        # Replace emoji in template with simple text labels
        replacements = {
            '🔄': '↻', '📤': '↑', '❌': '✗', '✅': '✓',
            '📝': '✎', '📖': '◉', '🔧': '⚙', '📦': '⊞',
            '🚀': '▲', '📋': '☰', '✕': '×',
            '⏸': '‖', '▶': '▶', '⏹': '■',
            '💾': '♦', '🗑': '×', '✚': '+',
            '⚠': '!', '🐍': 'Py', '🌐': 'W',
            '🎨': 'C', '⚡': 'JS', '⚙': '⚙', '📄': 'F',
            '👤': '●', '🏗': '▲', '💻': '▸', '🧪': '◆', '🔍': '◎',
            '🤖': '○', '💬': '◇', '⭐': '★', '🔒': '◆',
            '📊': '▥', '📁': '⊞',
        }
        
        new_template = template
        for emoji, replacement in replacements.items():
            new_template = new_template.replace(emoji, replacement)
        
        if new_template != template:
            new_content = content.replace(template, new_template)
            open(path, 'w', encoding='utf-8').write(new_content)
            rel = os.path.relpath(path, src_dir)
            print(f'{rel}: replaced {len(template_emoji)} template emoji')

print('Done')
