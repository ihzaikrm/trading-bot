with open('config/settings.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Tampilkan baris 48-75 untuk lihat struktur
for i, l in enumerate(lines[47:75], start=48):
    print(f'{i}: {l.rstrip()}')
