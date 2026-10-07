# -*- coding: utf-8 -*-
"""隐私扫描：token / 本地路径 / 邮箱 / 设备码。"""
import re, io, sys, os, glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

patterns = {
    'GitHub token': r'(ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    '设备码': r'\b[A-Z]{4}-[A-Z]{4}\b',
    '本地路径(反斜杠)': r'C:\\Users\\[A-Za-z]+',
    '本地路径(正斜杠)': r'C:/Users/[A-Za-z]+',
    '本地路径(宽松)': r'C:.Users.[A-Za-z]+',
    '邮箱': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}',
}

files = [f for f in glob.glob('**/*', recursive=True)
         if os.path.isfile(f) and '.git' not in f]
found = 0
for f in files:
    content = open(f, encoding='utf-8', errors='replace').read()
    for label, pat in patterns.items():
        for m in re.finditer(pat, content):
            s = max(0, m.start() - 40)
            ctx = content[s:m.end() + 40].replace('\n', ' ')
            print(f'{f} [{label}]: ...{ctx}...')
            found += 1
print(f'--- 扫描完成：{len(files)} 个文件，{found} 处疑似敏感内容')
