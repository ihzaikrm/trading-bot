import sys
with open('bot.py','r',encoding='utf-8') as f:
    lines=f.readlines()
for i,l in enumerate(lines[83:103],84):
    print(i,repr(l.strip()[:80]))
