import os

keywords = ['regex', 'pattern', 'isvalid', 'validation', 'match', 'filter']
for root, dirs, files in os.walk('psikochat-android'):
    for file in files:
        if file.endswith('.kt'):
            path = os.path.join(root, file)
            try:
                lines = open(path, encoding='utf-8').read().splitlines()
                for i, line in enumerate(lines):
                    if any(k in line.lower() for k in keywords):
                        print(f"{path}:{i+1}: {line}")
            except Exception as e:
                pass
