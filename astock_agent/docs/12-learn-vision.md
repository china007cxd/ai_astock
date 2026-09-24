# 12-learn-vision：学习管线①截图解读（`learn/vision.py`）

## 职责

学习管线第一步：把案例截图交给视觉模型"看图说话"，输出结构化
形态描述 JSON，供第二步规则提炼使用。

只在学习阶段使用（离线一次），运行时不做图形判断。

## 对外的接口

| 接口 | 说明 |
|---|---|
| `analyze_image_file(path) -> dict` | 单张截图 → 结构化解读；解析失败降级 `{"raw": 原文}` |
| `await analyze_case_images(paths, progress) -> list[dict]` | 并发解读一个案例的全部截图（并发3） |

## 视觉模型输出 JSON 结构（VISION_PROMPT 规定）

```
kline_pattern   K线形态（箱体突破/头肩底/连板拉升...）
ma_status       均线状态（多头排列/粘合/回踩某均线...）
indicator_status MACD/KDJ/成交量状态
volume_price    量价关系（放量突破/缩量回调...）
annotations     图中标注文字原文（逐条）
panels          面板信息（筹码/资金/板块摘要）
judgment        整体形态一句话判断
```

提示词强调"只描述图中可见内容，不要推测图外信息"——防模型脑补。

## 谁依赖它

- `main.py` 的 `_learn_job`：对每个案例调用 `analyze_case_images`

## 修改注意点

1. **改 VISION_PROMPT 的字段**：extract.py 的提炼提示词会把整个
   解读 dict 塞给文本模型，改字段名/口径会影响规则提炼质量。
   改后最好重新跑一个模式的学习对比效果。
2. **降级策略不要去掉**：`{"raw": 原文}` 保证单张图解析失败时
   学习流程继续，只是材料里多一段原文。
3. `asyncio.to_thread` 是必须的：`analyze_image` 内部是同步阻塞的
   openai SDK 调用，直接 await 会卡死事件循环。
4. 并发上限 3 是视觉模型限流友好的保守值。
