# -*- coding: utf-8 -*-
"""临时脚本：从会话记录中提取某个源文件的原始版本，用于核对重写时逻辑未被改动。"""
import json
import sys

transcript = r"C:\Users\wskj\.qoder\cache\projects\v62.1-139c3797\conversation-history\218eb55f\218eb55f.jsonl"
target = sys.argv[1] if len(sys.argv) > 1 else "llm.py"
out = sys.argv[2] if len(sys.argv) > 2 else "_t_orig.txt"

found = []
with open(transcript, encoding="utf-8") as f:
    for line in f:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        msg = obj.get("message", {})
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text", "")
            # 命中包含目标文件路径的消息（读文件或写文件的工具调用）
            if target in text and ("Contents of" in text or "file_path" in text):
                found.append(text)

text = "\n".join(found)
with open(out, "w", encoding="utf-8") as f:
    f.write(text)
print("written", len(found), "chunks,", len(text), "chars")
