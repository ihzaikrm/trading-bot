with open('dashboard/index.html','r',encoding='utf-8') as f: c=f.read()
# Tambah comment kecil untuk trigger deploy
c = c.replace('</body>', '<!-- v2.1 -->\n</body>')
with open('dashboard/index.html','w',encoding='utf-8') as f: f.write(c)
print('Done')
