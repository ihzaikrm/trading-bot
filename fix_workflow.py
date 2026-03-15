with open(".github/workflows/trading-bot.yml","r",encoding="utf-8") as f: c=f.read()

old = (
    "      - name: Commit trade logs\n"
    "  run: |\n"
    "    git config user.email \"bot@trading.com\"\n"
    "    git config user.name \"Trading Bot\"\n"
    "    git add logs/\n"
    "    git diff --staged --quiet || git commit -m \"bot: update logs\"\n"
    "    git push || true"
)
new = (
    "      - name: Commit trade logs\n"
    "        run: |\n"
    "          git config user.email \"bot@trading.com\"\n"
    "          git config user.name \"Trading Bot\"\n"
    "          git add logs/\n"
    "          git diff --staged --quiet || git commit -m \"bot: update logs\"\n"
    "          git push || true"
)

c = c.replace(old, new, 1)
with open(".github/workflows/trading-bot.yml","w",encoding="utf-8") as f: f.write(c)
print("Done!")
