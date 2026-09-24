---
trigger: always_on
---
# 日志MDC标签注入与SLF4J占位符统一规范

## 一、改造范围
仅对日志输出中包含 `JSON.toJSONString(xxx)` 或 `JSONObject.toJSONString(xxx)` 的日志行进行MDC标签注入改造，不含这些调用的日志行不做处理。

## 二、注入格式
1. 日志格式字符串必须以 `[{}]` 开头
2. 第一个参数固定为 `MdcUtil.RIZHIYI_SEC_LOG_DISCARD`
3. MdcUtil 必须直接导入已有的 `import com.guoke.star.common.log.config.MdcUtil`，禁止新建工具类

## 三、占位符规则
1. `log.info`/`log.warn`：`{}` 总数（含前缀 `[{}]` 中的1个）严格等于参数总数
2. `log.error`：若最后一个参数为 `Throwable`（含 `.getCause()` 等），则 `{}` 数量 = 参数总数 - 1（SLF4J 自动捕获堆栈，禁止为 Throwable 分配占位符）
3. 日志字符串中的字面逗号 `，` 不参与占位符计数

## 四、字符串拼接禁令（关键陷阱）
原始代码中形如 `log.info("xxx" + JSONObject.toJSONString(obj))` 的字符串拼接日志，**必须重构为 SLF4J 占位符格式**：
- 正确：`log.info("[{}]xxx{}", MdcUtil.RIZHIYI_SEC_LOG_DISCARD, JSONObject.toJSONString(obj))`
- 错误：`log.info("[{}]xxx" + JSONObject.toJSONString(obj), MdcUtil.RIZHIYI_SEC_LOG_DISCARD)` （保留了 + 拼接）
- 错误：`log.info("[{}]xxx", MdcUtil.RIZHIYI_SEC_LOG_DISCARD)` （丢失了数据输出）

严禁保留 `+` 拼接形式，严禁丢失数据输出部分。

## 五、改造流程
1. **搜索定位**：Grep 搜索 `log\.(info|warn|error)\(.*(?:JSON|JSONObject)\.toJSONString`，注意结果有25条截断上限，必须按子目录分层搜索
2. **注入改造**：在日志字符串前添加 `[{}]` 前缀，参数列表首位添加 MdcUtil 常量，同时将 `+` 拼接重构为 `{}` 占位符
3. **添加导入**：确保文件包含 `import com.guoke.star.common.log.config.MdcUtil`

## 六、全量验证（改造后必做）
1. **正向检查**：搜索 `MdcUtil\.RIZHIYI_SEC_LOG_DISCARD\);$`（以该常量结尾的行），结果应为 0 —— 若有则说明存在 `+` 拼接未重构
2. **逐行校验5项**：
   - `[{}]` 是否在格式字符串最前面
   - `MdcUtil.RIZHIYI_SEC_LOG_DISCARD` 是否为第一个参数
   - 日志字符串中不得出现 `+` 拼接对象输出
   - 所有 `toJSONString(obj)` 必须作为独立参数，对应位置为 `{}` 占位符
   - `{}` 总数严格等于参数数量（Throwable 除外）
3. **反向检查**：所有已改造行必须包含 `toJSONString` 调用，不含的属于错误改造（过度改造）
4. **Grep 截断防范**：大项目必须按子目录拆分搜索，大文件（超3000行）需分段 Read 兜底验证
