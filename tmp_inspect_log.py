from pathlib import Path
import csv
p = Path('logs/responsible_ai_log.csv')
with p.open('r', encoding='utf-8', newline='') as f:
    rdr = csv.reader(f)
    print('line,num_fields')
    for i, row in enumerate(rdr, start=1):
        print(i, len(row), row)
