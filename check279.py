with open('dashboard/index.html','r',encoding='utf-8') as f: c=f.read()
lines = c.split('\n')
for i in range(506, 525):
    print(i, repr(lines[i].strip()[:100]))
