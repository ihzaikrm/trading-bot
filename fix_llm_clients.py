with open('core/llm_clients.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[84] = '            elif name == "gemini": resp = await _openai_compat(cfg, sys_p, usr_p)\n'

with open('core/llm_clients.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done!')
