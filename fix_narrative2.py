with open("core/narrative_scanner.py","r",encoding="utf-8") as f: c=f.read()

# Fix: selalu update active_narratives, bukan hanya saat rotation
old = 'state["active_narratives"] = top_narratives'
new = 'state["active_narratives"] = top_narratives  # selalu update'

# Pindahkan update ke luar if block - tambah sebelum if rotation_needed
old2 = 'state["active_narratives"] = top_narratives  # selalu update\n\nstate["risk_profile"] = risk_profile'
# Tidak perlu ganti strukturnya, cukup update kondisi if

old3 = 'if rotation_needed and prev_narratives:'
new3 = 'if True:  # selalu update state narrative'

c = c.replace(old3, new3, 1)
with open("core/narrative_scanner.py","w",encoding="utf-8") as f: f.write(c)
print("Done!")
