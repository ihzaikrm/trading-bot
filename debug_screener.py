with open("bot.py","r",encoding="utf-8") as f: c=f.read()

# Bug: candidates adalah list of dict, tapi ada akses salah
# Cek isi fungsi build_dynamic_assets
start = c.find("def build_dynamic_assets")
end = c.find("\ndef ", start+1)
print(c[start:end])
