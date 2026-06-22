import re, os

emoji_pattern = re.compile('[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]')
src_dir = r'C:\Users\lahm\Desktop\Many AgentS\frontend\src'

for root, dirs, files in os.walk(src_dir):
    for f in files:
        if f.endswith(('.vue', '.js')):
            path = os.path.join(root, f)
            try:
                content = open(path, encoding='utf-8').read()
                matches = emoji_pattern.findall(content)
                if matches:
                    rel = os.path.relpath(path, src_dir)
                    print(f"{rel}: {len(matches)} emoji")
            except:
                pass
