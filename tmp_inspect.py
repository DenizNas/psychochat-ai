import os
import csv

output_lines = []

dirs = ['data/emotion', 'data/crisis']
for d in dirs:
    if os.path.exists(d):
        for f in os.listdir(d):
            if f.endswith('.csv'):
                path = os.path.join(d, f)
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        reader = csv.reader(file)
                        headers = next(reader, None)
                        row1 = next(reader, None)
                        row2 = next(reader, None)
                        output_lines.append(f"--- {path} ---")
                        output_lines.append(f"Columns: {headers}")
                        if row1: output_lines.append(str(row1))
                        if row2: output_lines.append(str(row2))
                except Exception as e:
                    output_lines.append(f"--- {path} --- (Error reading: {e})")

with open('tmp_inspect.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))
