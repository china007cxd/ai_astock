# 复盘与导出工具 VIP 笔记本版完整接口文档

> 目标文件：`复盘与导出工具vip笔记本_全能.exe`  
> SHA-256：`48bc912a9b238e4e75a1e1289769c549d17fcd48224b7d4cb23089047d3b7029`  
> 样本：PE32 / x86 / C++ / Qt 5 / Windows GUI / 28,389,176 bytes  
> 编译时间（PE 字段）：2026-08-14 10:44:54  
> 分析方式：radare2 6.2.2 字符串、导入表、XREF、`pdc` 伪代码，以及项目内适配代码交叉验证。

## 1. 范围、结论与可信度

本次从笔记本版样本中直接提取并逐项归类了 286 条 URL 字符串。台式版与笔记本版的业务 URL 集合相同；差异仅见于代码签名证书链 URL，不影响业务功能。

“接口”在本文中包括：

1. HTTP/HTTPS 数据接口；
2. 页面、更新、静态资源和证书网络入口；
3. Qt 网络、JSON、文件、配置接口；
4. Windows 注册表、窗口消息、进程、COM/WMI 等本地接口；
5. 文件导入导出和第三方客户端联动接口。

证据级别：

- **A**：笔记本版二进制内存在完整 URL/参数，或已由 XREF、反编译确认；
- **B**：二进制存在端点，响应字段由项目内适配代码交叉确认；
- **C**：仅有 URL/页面字符串，方法或响应结构需运行时抓包确认。

静态分析可以完整列出硬编码端点和参数模板，但服务端可随时增加字段；本文把无法从客户端消费代码确认的输出统一标为“透传 JSON/文本”。所有硬编码 Token、UserID、DeviceID、签名值均已替换为占位符。

## 2. 通用约定

### 2.1 HTTP 行为

| 项目 | 结论 |
|---|---|
| 默认方法 | 绝大多数为 `GET`，参数位于 QueryString |
| Qt 调用链 | `QUrl` → `QUrlQuery` → `QNetworkRequest` → `QNetworkAccessManager::get()` → `QNetworkReply::readAll()` |
| 常用 User-Agent | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ... Chrome/119.0 Safari/537.36` |
| 龙虎 VIP Referer | `https://www.longhuvip.com/`（关联适配代码确认） |
| 常见编码 | JSON UTF-8；腾讯行情为 GBK 文本；部分接口为 JSONP/HTML/图片/二进制 |
| 超时 | 授权禁用链路中确认存在 3000 ms 定时退出 |

### 2.2 龙虎 VIP 通用输入参数

| 参数 | 类型 | 含义 |
|---|---|---|
| `a` | string | 动作名，是标准化端点的主要标识 |
| `c` | string | 控制器/模块名 |
| `Index` / `index` | int | 分页起点或页号，通常从 0 开始 |
| `st` | int | 返回数量，常见 1/20/22/25/30/45/60/100/500/1000/2000/6000/10000 |
| `Order` | int | 排序方向，样本使用 0/1 |
| `Date` / `Day` / `Time` | string | 日期或时间；常见 `YYYY-MM-DD`、`YYYYMMDD`、`HHmm` |
| `DEnd` | string | 查询截止日期 |
| `RStart` / `REnd` | string | 盘中时间范围，如 0925、1500 |
| `StockID` | string | 股票、指数或板块代码 |
| `PlateID` / `GroupID` | string | 板块/分组 ID |
| `StockIDList` | string | 股票代码列表 |
| `Type` / `PidType` / `ZSType` | int/string | 业务类型 |
| `PhoneOSNew` | int | 客户端标识，样本固定 1 |
| `Token` / `UserID` | string | 上游账户认证参数 |
| `DeviceID` | string | UUID 设备标识 |
| `apiv` / `VerSion` | string | API/客户端版本 |
| `TSZB` / `TSZB_Type` | int | 指数榜类型 |
| `old` / `IsZZ` / `IsKZZType` | int | 历史、指数/转债过滤开关 |
| `Is_st` / `Isst` | int | ST 股票过滤开关 |
| `FilterMotherboard` / `FilterTIB` / `FilterGem` / `Filter` | int | 主板、科创板、创业板等过滤 |
| `IsLB` / `IsZT` / `IsShow` / `IsBoom` / `Red` | int | 列表显示或状态过滤 |
| `ColumnID` / `MsgID` / `ID` | string/int | 文章、消息或题材 ID |
| `View` | CSV string | 指数信息视图集合 |

### 2.3 龙虎 VIP 通用输出

不同动作会返回对象或列表，客户端可见的通用包络为：

```json
{
  "State": 0,
  "Data": [],
  "List": [],
  "Count": 0,
  "Page": 0
}
```

常见数据项字段族：

| 字段族 | 常见字段 | 含义 |
|---|---|---|
| 股票身份 | `ID`, `StockID`, `Code`, `Name`, `StockName` | 代码、名称 |
| 行情 | `Price`, `IncreaseAmount`, `Change`, `Open`, `High`, `Low`, `Close` | 价格及涨跌 |
| 成交 | `Volume`, `Turnover`, `TurnoverRatio`, `Amplitude` | 成交、换手、振幅 |
| 涨停 | `Day`, `Time`, `Type`, `Reason`, `HighDays`, `FirstTime`, `LastTime` | 日期、类型、原因、连板与封板时间 |
| 资金 | `BuyIn`, `Capitalization`, `CircPrice`, `Amount`, `NetInflow` | 净买、总/流通市值、资金 |
| 板块 | `PlateID`, `PlateName`, `GroupID`, `GroupName` | 板块和分组 |
| 题材 | `Title`, `Content`, `HotVal`, `HotTag`, `New` | 题材标题、内容、热度 |

未列出的字段属于上游透传字段，应按实际 JSON 保留，不能在客户端侧做封闭枚举。

## 3. 龙虎 VIP / 开盘红接口全表

下表按“主机 + `c` + `a`”去除 URL 模板重复；“输入”列只写动作专有参数，通用参数见 2.2；输出均叠加 2.3 的通用包络。

### 3.1 `apphis.longhuvip.com` 历史数据

基础路径：`GET https://apphis.longhuvip.com/w1/api/index.php`

| `c` | `a` | 功能 | 专有输入 | 主要输出 | 级别 |
|---|---|---|---|---|---|
| `HisHomeDingPan` | `DailyLimitPerformance` | 历史涨停表现 | `PidType,Type` | 涨停表现列表/统计 | A |
| `HisHomeDingPan` | `DailyLimitPerformance2` | 历史涨停表现变体 | `PidType,Type` | 涨停表现列表/统计 | A |
| `HisHomeDingPan` | `HisDaBanList` | 历史打板列表 | `Day,Is_st,PidType,Type,Filter*` | 股票、连板、涨停原因、封板数据 | A |
| `HisHomeDingPan` | `DiskReview` | 大盘复盘 | `Day` | 指数、涨跌停及市场统计 | A |
| `HisHomeDingPan` | `HisZhangFuDetail` | 历史涨幅详情 | `Day` | 涨幅分布/个股列表 | A |
| `HisHomeDingPan` | `MarketSCLN` | 市场量能 | `Date` | 成交量能统计 | A |
| `HisHomeDingPan` | `RiseFallAnalysis` | 涨跌分析 | 分页 | 涨跌分布、数量 | A |
| `HisHomeDingPan` | `Radar` | 历史雷达 | `Date` | 异动/事件列表 | A |
| `HisHomeDingPan` | `MorningBiddingList` | 历史早盘竞价 | 分页 | 竞价股票列表 | A |
| `ZhiShuRanking` | `RealRankingInfo` | 指数/板块排行 | `Date,RStart,ZSType,Type` | 排名、涨幅、热度 | A |
| `ZhiShuRanking` | `ZhiShuStockList_W8` | 指数成分股 | `Date,RStart,PlateID,Type,TSZB*` | 成分股行情列表 | A |
| `ZhiShuRanking` | `InterviewsByDate` | 指数访谈 | `DEnd` | 日期、标题、内容 | A |
| `ZhiShuRanking` | `SonPlate_Info` | 子板块信息 | `Date/DEnd,IsShow` | 子板块列表 | A |
| `StockLineData` | `GetInterviewsByDateZS` | 指数连线 | `DEnd` | 连线内容列表 | A |
| `StockLineData` | `GetInterviewsByDateStock` | 个股连线 | `DEnd` | 个股连线内容 | A |
| `StockBidYiDong` | `GetBKJJ_w36` | 板块竞价 | `Type` | 板块竞价排行 | A |
| `StockBidYiDong` | `GetBKJJBL` | 板块竞价比例 | `IsLB,IsZT,Isst` | 比例、金额、排名 | A |
| `StockBidYiDong` | `GetWPQC` | 外盘驱动 | `Type` | 外盘驱动列表 | A |
| `StockBidYiDong` | `GetYDTP_WXHJ_His` | 历史异动突破 | `Token,UserID` | 异动股票列表 | A |
| `HisLimitResumption` | `GetDayZhangTing` | 个股历史涨停 | `StockID,apiv,VerSion` | 涨停日期、原因、表现 | A |
| `HisLimitResumption` | `GetPlateInfo` | 历史板块信息 | `Date` | 板块涨停统计 | A |
| `HisLimitResumption` | `GetPlateInfo_w38` | 历史板块信息新版 | `Date` | 板块涨停统计 | A |
| `HisLimitResumption` | `KLineZhangTingReason` | K 线涨停原因 | `Date,Token?` | 股票与涨停原因映射 | A |
| `ZhiShuKLine` | `GetDayBaseFaceListZDEvnArt` | 指数日 K | `StockID,Type` | OHLC、成交量/额 | A |
| `ZhiShuKLine` | `GetPlateKLineDay` | 板块日 K | `StockID,Type=d` | OHLC、成交量/额 | A |
| `ZhiShuL2Data` | `GetTrendIncremental` | 指数增量趋势 | `StockID` | 时间、价格、涨幅 | A |
| `ZhiShuL2Data` | `GetVolTurIncremental` | 指数量能增量 | `StockID,apiv` | 时间、成交量/额 | A |
| `StockL2History` | `GetZsReal` | 历史指数实时切片 | `Day` | 指数分时数据 | A |
| `StockFengKData` | `GetFengKListBest` | 涨停封单 | `Time,Day` | 封单额、封单量、时间 | A |
| `FuPanLa` | `GetPMSL_KQXY` | 盘面梳理/开情绪 | `Date` | 市场情绪数据 | A |
| `FuPanLa` | `GetPMSL_PMLD` | 盘面亮点 | `Date` | 亮点列表 | A |
| `FuPanLa` | `GetYTFP_BKHX` | 异动复盘板块核心 | `Date` | 板块异动 | A |
| `FuPanLa` | `GetYTFP_LHBDX` | 异动复盘龙虎榜动向 | `Date` | 龙虎榜动向 | A |
| `FuPanLa` | `GetYTFP_SCTD` | 异动复盘市场梯队 | `Date` | 梯队列表 | A |
| `StockNewHigh` | `GroupCount_w28` | 新高分组计数 | `Date,Type` | 分组及数量 | A |
| `StockNewHigh` | `GetGroupStock_ByGroup_W28` | 新高分组股票 | `Date,Type` | 分组股票列表 | A |
| `HisStockRanking` | `HisRankingInfo_W8` | 历史排行 | `RStart` | 个股排行 | A |
| `HisConceptionPoint` | `ZhiBoContent` | 历史直播内容 | `Date,index` | 时间、标题、内容 | A |
| `YiDianCangWei` | `GetGuDong` | 股东/仓位 | `StockID,Type` | 股东、仓位信息 | A |

### 3.2 `apphq.longhuvip.com` 实时数据

基础路径：`GET https://apphq.longhuvip.com/w1/api/index.php`

| `c` | `a` | 功能 | 专有输入 | 主要输出 |
|---|---|---|---|---|
| `HomeDingPan` | `DailyLimitPerformance` / `DailyLimitPerformance2` | 实时涨停表现 | `PidType,Type` | 涨停表现列表/统计 |
| `HomeDingPan` | `ChangeStatistics` | 涨跌统计 | `st` | 涨跌、平盘数量 |
| `HomeDingPan` | `DiskReview` | 实时大盘回顾 | 无 | 大盘统计 |
| `ZhiShuRanking` | `RealRankingInfo` | 实时指数排行 | `RStart,ZSType,Type,DeviceID` | 指数/板块排名 |
| `ZhiShuRanking` | `ZhiShuStockList_W8` | 实时成分股 | `RStart,old,IsZZ,Token` | 成分股行情 |
| `ZhiShuRanking` | `SonPlate_Info` | 子板块 | `DEnd/PlateID` | 子板块列表 |
| `StockLineData` | `GetInterviewsByDateZS` | 实时指数连线 | `DEnd` | 连线内容 |
| `StockBidYiDong` | `GetHotPHB` | 热门排行 | `Type,Token,UserID` | 热门股票排行 |
| `StockBidYiDong` | `GetBKJJ_w36` | 实时板块竞价 | `Type` | 竞价排行 |
| `StockBidYiDong` | `GetPianLiZhi_Index` | 指数偏离值 | `ZDJK_Type,apiv` | 偏离值序列 |
| `StockBidYiDong` | `GetPianLiZhi_Many` | 多股偏离值 | 无 | 多股偏离值 |
| `StockL2Data` | `GetFeaturedSection` | 精选板块 | `StockID` | 板块/个股精选数据 |
| `StockL2Data` | `GetTrendIncremental` | 实时趋势增量 | `StockID` | 分时价格 |
| `StockL2Data` | `GetVolTurIncremental` | 实时量能增量 | `StockID` | 分时量能 |
| `DailyLimitResumption` | `GetPlateInfo` | 实时板块信息 | 分页 | 板块涨停数据 |
| `StockNewHigh` | `GroupCount_w28` | 新高分组计数 | `Type` | 分组计数 |
| `StockNewHigh` | `GetGroupStock_ByGroup_W28` | 新高分组股票 | `GroupID,Type` | 股票列表 |
| `UserSelectStock` | `RefreshStockList` | 刷新自选 | `Token` | 自选行情 |
| `Index` | `GetInfo` | 指数信息 | `View=2,3,4,5,7,8,9,10,11` | 多指数摘要 |

### 3.3 `apphwhq.longhuvip.com` 盘后数据

基础路径：`GET https://apphwhq.longhuvip.com/w1/api/index.php`

| `c` | `a` | 功能 | 专有输入 | 主要输出 |
|---|---|---|---|---|
| `HomeDingPan` | `DailyLimitPerformance` | 盘后涨停表现 | `PidType,Type` | 涨停表现 |
| `HomeDingPan` | `MorningBiddingList` | 盘后早盘竞价 | 分页 | 竞价股票 |
| `HomeDingPan` | `Radar` | 盘后雷达 | 分页 | 异动列表 |
| `ZhiShuRanking` | `RealRankingInfo` | 盘后指数排行 | `Type` | 排行列表 |
| `ZhiShuRanking` | `InterviewsByDate` | 盘后访谈 | `DEnd` | 访谈列表 |
| `ZhiShuRanking` | `GetPlate_Info_QJ` | 板块区间 | `PlateID` | 区间板块数据 |
| `StockLineData` | `GetInterviewsByDateStock` | 个股访谈 | `DEnd` | 个股访谈 |
| `StockLineData` | `GetKLineZhangTing` | 个股 K 线涨停 | `StockID` | K 线涨停点 |
| `StockBidYiDong` | `GetBKJJBL` | 板块竞价比例 | `IsLB,IsZT,Isst` | 竞价比例 |
| `StockBidYiDong` | `GetWPQC` | 外盘驱动 | 无 | 驱动列表 |
| `StockBidYiDong` | `GetYDTP_WXHJ_His` | 异动突破历史 | 无 | 异动列表 |
| `StockBidYiDong` | `GetYDTP_ZDJK_His` | 重点监控历史 | 无 | 监控列表 |
| `StockBidYiDong` | `GetYDTP_ZDJK_Today` | 重点监控今日 | 无 | 监控列表 |
| `ZhiShuL2Data` | `GetBaseFaceListZDEvnArtNew` | 指数 K 线新版 | `StockID` | OHLC/量额 |
| `DailyLimitResumption` | `GetPlateInfo_w38` | 板块信息 | 分页 | 板块统计 |
| `StockL2Data` | `GetStockIDPlate` | 个股所属板块 | `StockID,Type,Token?,UserID?` | 板块列表 |
| `StockL2Data` | `GetStockPanKou_Narrow` | 窄版盘口 | `StockID` | 买卖档、价格、量 |
| `StockYiDongKanPan` | `StockDPRealData` | 个股实时盘口 | `StockID` | 实时盘口/异动 |
| `UserSelectStock` | `RefreshStockList_W8` | 批量自选刷新 | `StockIDList` | 自选行情 |
| `FuPanLa` | `GetPMSL_KQXY` / `GetPMSL_PMLD` | 盘面梳理 | 分页 | 情绪/亮点 |
| `FuPanLa` | `GetYTFP_BKHX` / `GetYTFP_LHBDX` / `GetYTFP_SCTD` | 异动复盘 | 无 | 板块、龙虎榜、梯队 |
| `ConceptionPoint` | `ZhiBoContent` | 实时直播 | `index` | 直播内容 |

### 3.4 `apphwshhq.longhuvip.com` 上海盘后数据

基础路径：`GET https://apphwshhq.longhuvip.com/w1/api/index.php`

| `c` | `a` | 功能 | 输入 | 输出 |
|---|---|---|---|---|
| `HomeDingPan` | `DailyLimitPerformance` | 盘后涨停表现 | `PidType,Type` | 涨停表现 |
| `ZhiShuRanking` | `RealRankingInfo` | 竞价时段指数排行 | `RStart,REnd,ZSType` | 指数排行 |
| `ZhiShuRanking` | `ZhiShuStockList_W8` | 竞价时段成分股 | `RStart,REnd,old,IsZZ,Token` | 成分股列表 |
| `StockL2Data` | `GetStockPanKou` | 完整盘口 | `StockID` | 买卖档、价格、量 |
| `StockFengKData` | `GetFengKListBest` | 最佳封单 | `Time` | 封单列表 |

### 3.5 龙虎榜、文章和开盘红

| 方法与端点 | 功能 | 输入 | 输出 |
|---|---|---|---|
| `GET applhb... index.php?a=GetStockList&c=LongHuBang` | 龙虎榜股票 | `st,Time,Index,Type,Token,UserID` | `list[]`: `ID,Name,IncreaseAmount,BuyIn,JoinNum,Turnover,CircPrice,Amplitude,TurnoverRatio,Capitalization,D3` |
| `GET applhb... index.php?a=InfoList&c=Topic` | 题材时间线 | `st,index,Token?,UserID?` | `List[].Day,List[].List[]`; 项含 `ID,Title,HotVal,HotTag,Time,New` |
| `GET applhb... index.php?a=InfoGet&c=Topic` | 题材详情 | `ID,Token?,UserID?` | `Title,Content` |
| `GET applhb... index.php?a=InfoGet&c=Theme` | 主题详情 | 通用参数 | 主题对象 |
| `GET apparticle... index.php?a=GetInfo&c=ForumsMsgColumn` | 文章栏目 | `ColumnID,st,index,apiv,DeviceID,VerSion` | 文章列表 |
| `GET apparticle... index.php?a=GetInfo&c=ForumsMsgJX` | 文章详情 | `MsgID` | 标题、正文、时间 |
| `GET apphis.kaipanhong... a=GetPoint&c=HisConceptionPoint` | 历史概念点 | `Date` | 概念点列表 |
| `GET apphis.kaipanhong... a=GetZsTrend&c=StockL2History` | 历史指数趋势 | `StockID` | 趋势序列 |
| `GET apphis.kaipanhong... a=GetDayBaseFaceListZDEvnArt&c=ZhiShuKLine` | 历史指数 K 线 | `StockID,Red,IsBoom,apiv,VerSion,DeviceID` | OHLC/量额 |
| `GET apphq.kaipanhong... a=GetPoint&c=ConceptionPoint` | 实时概念点 | 无 | 概念点列表 |
| `GET apphq.kaipanhong... a=GetZsTrend&c=StockL2Data` | 实时指数趋势 | `StockID` | 分时趋势 |

## 4. 同花顺接口

| 方法与端点 | 输入 | 输出/字段 | 级别 |
|---|---|---|---|
| `GET data.10jqka.com.cn/dataapi/limit_up/limit_up_pool` | `page,limit,field,filter,order_field,order_type,date` | `data.info[]`: `code,name,high_days,limit_up_type,first_limit_up_time,last_limit_up_time,order_amount,reason_type,change_rate,turnover_rate,currency_value,latest,limit_up_suc_rate,is_again_limit,time_preview,market_type` | B |
| `GET data.10jqka.com.cn/dataapi/limit_up/block_top` | 上游默认参数 | 板块涨停排行 JSON | A |
| `GET data.10jqka.com.cn/dataapi/transaction/stock/v1/list` | `order_field=change,order_type=desc,date` | 股票成交排行 JSON | A |
| `GET eq.10jqka.com.cn/open/api/hot_list/v1/hot_plate/concept/data.txt` | 无 | `data.plate_list[]`: `code,name,order,rate,tag,hot_tag,etf_name,etf_product_id` | B |
| `GET eq.10jqka.com.cn/open/api/hot_list/v1/hot_stock/a/hour/data.txt` | 无 | 热门个股小时榜文本/JSON | A |
| `GET eq.10jqka.com.cn/call_auction_v2/stock_chance/v1/{code}/{date}` | 路径参数 `code,date` | 竞价机会 JSON | A |
| `GET comment.10jqka.com.cn/tzrl/getTzrlData.php` | `callback,type=data,date` | JSONP 人气数据 | A |
| `GET dq.10jqka.com.cn/fuyao/market_analysis_api/chart/v1/get_chart_data` | `chart_key=turnover_minute` | 分时成交图数据 | A |
| `GET news.10jqka.com.cn/pclient/news/push/stock/1.json` | 无 | 新闻推送 JSON | A |

页面入口：`https://data.10jqka.com.cn/`、`https://eq.10jqka.com.cn`、`.../webpage/call-auction/selfchance.html`。

## 5. 选股宝接口

| 方法与端点 | 输入 | 输出/字段 |
|---|---|---|
| `GET flash-api.xuangubao.com.cn/api/event/history` | `count,types`（由调用场景补入） | 事件时间线 |
| `GET flash-api.xuangubao.cn/api/pool/detail` | `pool_name=limit_up,date?` | `data[]`: `symbol,stock_chi_name,limit_up_days,m_days_n_boards_days,change_percent,first_limit_up,last_limit_up,break_limit_up_times,break_limit_down_times,first_break_limit_up,last_break_limit_up,turnover_ratio,surge_reason` |
| `GET flash-api.xuangubao.com.cn/api/pool/detail` | `pool_name=limit_up_broken,date?` | 同上，表示破板池 |
| `GET flash-api.xuangubao.cn/api/surge_stock/plates` | `date?` | 涨停板块列表 |
| `GET flash-api.xuangubao.cn/api/surge_stock/stocks` | `date?,normal=true,uplimit=true` | 涨停个股列表 |

`surge_reason` 常见子字段：`stock_reason`、`related_plates[].plate_name`、`related_plates[].plate_reason`。`.cn` 与 `.com.cn` 两组主机均存在于样本。

## 6. 东方财富接口

### 6.1 行情与资金

| 方法与端点 | 输入 | 输出/字段 |
|---|---|---|
| `GET {90.}push2.eastmoney.com/api/qt/clist/get` | `cb?,pn,pz,po,np,ut,fltt,invt,wbp2u?,fid,fs,fields,_?` | `data.total,data.diff[]`；字段见下表 |
| `GET push2.eastmoney.com/api/qt/ulist.np/get` | `ut,fltt,invt,fields,secids` | `data.diff[]` 自选行情 |
| `GET datacenter.eastmoney.com/securities/api/data/v1/get` | 动态 Query | 数据中心分页 JSON |
| `GET gbcdn.dfcfw.com/rank/popularityList.js` | `type,sort,page` | 人气榜 JavaScript/JSONP |
| `GET np-weblist.eastmoney.com/comm/web/getFastNewsList` | `client,biz,fastColumn,sortEnd,pageSize,req_trace,_` | 7×24 快讯列表 |
| `GET webquotepic.eastmoney.com/GetPic.aspx` | `imageType,nid` | PNG/JPEG 行情图 |
| `GET webquoteklinepic.eastmoney.com/GetPic.aspx` | `nid` | PNG/JPEG K 线图 |

`clist/get` 字段映射：

| 字段 | 含义 | 字段 | 含义 |
|---|---|---|---|
| `f2` | 最新价 | `f3` | 涨跌幅 |
| `f4` | 涨跌额 | `f5` | 成交量 |
| `f6` | 成交额 | `f7` | 振幅 |
| `f8` | 换手率 | `f9` | 市盈率动态 |
| `f10` | 量比 | `f11` | 5 分钟涨跌 |
| `f12` | 代码 | `f13` | 市场标识 |
| `f14` | 名称 | `f15/f16/f17/f18` | 高/低/开/昨收 |
| `f20/f21` | 总/流通市值 | `f22/f23/f24/f25` | 涨速/市净率/60日/年初涨幅 |
| `f62` | 主力净流入 | `f66/f72/f78/f81` | 超大/大/中/小单净额 |
| `f69/f75/f184` | 超大单/大单/主力占比 | `f104/f105/f106` | 上涨/下跌/平盘家数 |
| `f115/f128/f136/f148/f152` | 上游扩展字段 |  | 透传保留 |

### 6.2 题材与智能选股

| 方法与端点 | 输入 | 输出/字段 |
|---|---|---|
| `GET emcfgdata.eastmoney.com/api/themeInvest/getThemeList` | 动态 Query | 题材列表 |
| `GET .../getStockList` | 题材 ID、分页等动态 Query | 题材成分股 |
| `GET .../getTodayChance` | 动态 Query | 今日机会 |
| `GET .../getFryTomorrowList` | 动态 Query | 明日题材 |
| `POST np-tjxg-b.eastmoney.com/api/smart-tag/stock/v3/pw/search-code` | JSON，见下方 | `code,data.result.total,data.result.dataList[]` |

智能选股请求体：

```json
{
  "keywordNew": "自然语言选股条件",
  "pageSize": 20,
  "pageNo": 1,
  "fingerprint": "{32位小写hex}",
  "timestamp": 0,
  "requestId": "{32位小写hex}",
  "gids": [],
  "shareToGuba": false,
  "needShowStockNum": false,
  "client": "WEB"
}
```

响应股票字段：`SECURITY_CODE`、`SECURITY_SHORT_NAME`、`NEWEST_PRICE`、`CHG`、`TURNOVER_RATE`、`QRR`、`TRADING_VOLUMES`、`PE_DYNAMIC`、`PB`、`TOAL_MARKET_VALUE<140>`、`CIRCULATION_MARKET_VALUE<140>`、`FIRST_LIMITUP`、`LIMIT_UP_FLT`、`LIMIT_REASON`；字段名可能附带 `{日期}` 后缀。

页面入口：`data.eastmoney.com/zjlx/detail.html`、`emdata.eastmoney.com/appdc/lhb/index.html`、`emrnweb.eastmoney.com/graymarket/home`、`guba.eastmoney.com`、`quote.eastmoney.com`、`quotederivates.eastmoney.com/datacenter/darktrade`。

## 7. 腾讯、通达信及行情补充

| 方法与端点 | 输入 | 输出 |
|---|---|---|
| `GET qt.gtimg.cn/q=s_{code}` | 单个或逗号分隔代码 | GBK 文本 `v_code="字段~..."` |
| `GET web.ifzq.gtimg.cn/appstock/app/minute/query` | `_var,code,r` | 分时 JSON/JSONP |
| `GET pul.tdx.com.cn/TQLEX` | `Entry=JNLPSE.hotStockList,RI` | 热门股票列表 |
| `GET hot.icfqs.com:7615/TQLEX` | `Entry=CWServ.cfg_tk_scqx,RI` | 通达信配置/权限 |
| `GET hot.icfqs.com:7615/TQLEX` | `Entry=CWServ.pcwebcall_yzfp_mmmx` | 复盘明细 |
| `GET hot.icfqs.com:7615/TQLEX` | `Entry=CWServ.pcwebcall_yzfp_yzdx` | 复盘动向 |
| `GET excalc.icfqs.com:7616/TQLEX` | `Entry=HQServ.hq_nlp` | 行情自然语言处理结果 |
| `GET page3.tdx.com.cn:7615/site/pcwebcall_static/bxb/json/` | 路径资源 | 板块 JSON |

腾讯 `~` 分隔关键位置：`1` 名称、`2` 代码、`3` 现价、`4` 昨收、`5` 今开、`6` 成交量、`30` 时间、`31/32` 涨跌额/幅、`33/34` 高/低、`37/38` 成交额/换手、`39` PE、`43` 振幅、`44/45` 流通/总市值、`46` PB、`47/48` 涨跌停价、`49` 量比、`51` 均价。

通达信页面入口：`hot.icfqs.com:7615/site/tdx-pc-pcwebcall/page-qxzb.html?color=0&bkcolor=000000`。

## 8. 九阳公社、短线侠、问财及其他数据源

| 方法与端点 | 输入 | 输出 |
|---|---|---|
| `GET app.jiuyangongshe.com/jystock-app/api/v1/action/diagram-url` | 动态 Query | 产业链图 URL |
| `GET .../action/field` | 动态 Query | 产业链字段/分类 |
| `GET .../action/list` | 动态 Query | 产业链动作列表 |
| `GET .../industry/list` | 动态 Query | 行业列表 |
| `GET duanxianxia.com/api/getFengdanLast` | 无 | 以日期为键；值含 `table,t15,t20,t25` |
| `GET duanxianxia.com/vendor/stockdata/jjlive.json` | 无 | 竞价直播 JSON |
| `GET duanxianxia.com/vendor/stockdata/platechart1.json` | 无 | 板块图表 JSON |
| `GET www.iwencai.com/gateway/urp/v7/landing/getDataList` | 动态 Query/Cookie | 问财结果列表 |
| `GET/POST www.iwencai.com/unifiedwap/unified-wap/v2/result/get-robot-data` | 查询文本、分页、会话参数 | 机器人解析和选股结果 |
| `GET api.duishu.com/lhbapp/zhangting/index` | `pagecount,page,type,apiversion,backgroundcolor,use_self_dns,device_id,oaid,vaid,dxwappid,dxwsign` | `data.date,date_list,title,sum_list,baopan,tab_list,stock_list{head_info,list,multi}` |
| `GET x-quote.cls.cn/v2/quote/a/plate/up_down_analysis` | 无 | `data.continuous_limit_up[]`, `plate_stock[]`, `limit_down`, `broken_limit_up` |
| `GET www.tgb.cn/new/nrnt/getNoticeStock` | `type=H` | 淘股吧提示股票列表 |
| `GET www.59155188.xyz/api/get_csv` | 动态 Query | CSV/下载信息 |
| `GET www.59155188.xyz/api/get_sign` | 动态 Query | 签名值 |

财联社结构：`continuous_limit_up[].height/stock_list[].secu_code,secu_name`；`plate_stock[].secu_name,change,plate_stock_up_num,up_reason,stock_list[]`。

页面入口：`duanxianxia.com/web/jjlive`、`www.iwencai.com/screener`、`www.jiuyangongshe.com/action/`、`www.xuangubao.cn/`、`www.59155188.xyz/page-ER-lesgkv.html`。

## 9. 作者服务、授权与更新

### 9.1 授权接口（反编译确认）

旧版文档把这些接口写成 POST JSON；笔记本版 `pdc` 证据明确显示它们调用 `QNetworkAccessManager::get()` 并通过 `QUrlQuery::addQueryItem()` 传参。

| 方法与端点 | Query 输入 | 客户端读取的输出 | 证据 |
|---|---|---|---|
| `GET https://codingchangeworld.com/license/activate/` | `code={激活码}`, `device={硬件设备ID}`, `device_name={COMPUTERNAME}`, `app=kpl` | `ok:int`, `code:string`, `token:string`, `plan_type:string`, `expires_at:string`, `invite_code:string` | A；XREF `fcn.008df5a0` |
| `GET https://codingchangeworld.com/license/heartbeat/` | `code={本地license_code}`, `token={license_token}`, `device={硬件设备ID}`, `app=kpl` | JSON；成功性字段至少含 `ok`，异步 finished 回调处理 | A；XREF `fcn.008dbd82` |
| `GET https://codingchangeworld.com/license/disable/` | `code={license_code}`, `token={license_token}`, `device={硬件设备ID}`, `reason={禁用原因}` | `ok:int` | A；XREF `fcn.008e0d9c` |
| `GET https://codingchangeworld.com/license/invite/info/` | 动态 Query，静态字符串未给出完整模板 | 邀请信息 JSON | A/C |

激活成功后写入本地设置：`license_code`、`license_token`、`license_plan_type`、`license_expires_at`、`license_invite_code`。不要把这些值写入日志或公开文档。

### 9.2 作者业务接口

| 方法与端点 | 输入 | 输出/用途 |
|---|---|---|
| `GET codingchangeworld.com/searchCode/` | `code` | 股票代码查询 |
| `GET codingchangeworld.com/kplGetCode/` | 动态 Query | 开盘啦代码映射 |
| `GET codingchangeworld.com/dfcfxgmy/` | 动态 Query | 东方财富选股配置/密钥 |
| `GET codingchangeworld.com/jcydCookies/` | 动态 Query | 竞价异动 Cookie/配置 |
| `GET www.codingchangeworld.com/getCurrentTime/` | 无 | 服务端时间 |
| `GET www.codingchangeworld.com/jcyd/cache/` | 动态 Query | 竞价异动缓存 |
| `GET www.codingchangeworld.com/updateTck/` | 动态 Query | 更新弹窗配置 |
| `POST/GET www.codingchangeworld.com/addAdvice/` | `activate` 或反馈正文（具体编码需动态确认） | 反馈提交结果 |
| `GET www.codingchangeworld.com/aiFp/` | 动态 Query | AI 复盘数据 |
| `GET www.codingchangeworld.com/apzjgj/history/` | 动态 Query | A 股资金轨迹历史 |
| `GET www.codingchangeworld.com/bkzjgj/history/` | 动态 Query | 板块资金轨迹历史 |
| `GET www.codingchangeworld.com/kplbkzjgj/history/` | 动态 Query | 开盘啦板块资金轨迹历史 |
| `GET www.codingchangeworld.com/jjfd_history/` | 动态 Query | 竞价封单历史 |
| `GET www.codingchangeworld.com/rqb_history/` | 动态 Query | 人气榜历史 |
| `GET www.codingchangeworld.com/AGztyy/` | 动态 Query | A 股主题/数据页面 |

### 9.3 OSS 和 CDN 资源

| URL | 用途/输出 |
|---|---|
| `codingchangeworld.oss-cn-beijing.aliyuncs.com/update2.json` | 更新元数据 JSON |
| `.../kpl.txt` | 开盘啦配置/板块文本 |
| `.../gnb.txt` | 概念板块文本 |
| `.../SB.txt` | 首板数据文本 |
| `.../v8.0.7z` | 更新压缩包 |
| `appcdn.longhuvip.com/BiLeiLa/kaipanla_bileila_...` | 开盘啦比类啦 CDN 资源前缀 |
| `img.codingchangeworld.com/chatGroup/*.mp4` | 教程视频，不是 API |
| `img.codingchangeworld.com/chatGroup/*.csv` | 财报 CSV 静态资源 |

## 10. 本地文件接口

### 10.1 程序配置/缓存

| 文件 | 方向 | 输入/输出语义 |
|---|---|---|
| `StockList.ini` | 读 | GBK 股票代码—名称映射 |
| `LiandongConfig.ini` | 读写 | 第三方软件联动配置 |
| `start.ini` | 读写 | 启动页/启动状态 |
| `select.ini` | 读写 | 选股条件 |
| `page.ini` | 读写 | 页面状态 |
| `tablelayout.ini` | 读写 | 表格列布局 |
| `tuozhuaiColumn.ini` | 读写 | 拖拽列配置 |
| `快捷键.ini` | 读写 | 快捷键定义 |
| `gpbb.ini` | 读写 | 股票报表配置 |
| `jjxg.ini` | 读写 | 精选选股配置 |
| `dpzb.ini` | 读写 | 大盘指标配置 |
| `apzjgj.ini` | 读写 | A 股资金轨迹 |
| `bkzjgj.ini` | 读写 | 板块资金轨迹 |
| `kplbkzjgj.ini` | 读写 | 开盘啦板块资金轨迹 |
| `stock-data.json` | 读写 | 股票数据缓存 |
| `stock_list.json` / `trade_calendar.json` | 读 | 股票列表和交易日历 |

### 10.2 通达信文件联动

- 自选/板块输入输出：`T0002/blocknew/*.blk`；内容为通达信市场前缀加股票代码。
- 标记输入输出：`T0002/mark.dat`。
- 已识别板块名：`ZTB,ZTEB,ZTSB,ZTGJJ,ZRZTBX,DTB,SLB,WLB,FXB,DCRQB,TDXRQB,KPLRQB,THSRQB,TGBRQB,DCZNXG,THSWCXG,THSZT,JJZT,JJYP,ZXG,ZPJJ,ZQFK,GDB,WPQC,JCGSYD,SBZT,LBTT,XGBRDJD,JRLY`。
- 导出能力包括 CSV、文本、图片，以及向第三方客户端自定义板块写入；Excel 自动化可能通过 OLE/COM 完成，具体工作簿对象调用需动态验证。

## 11. 注册表 / QSettings 接口

| 逻辑路径 | 键 | 方向 | 含义 |
|---|---|---|---|
| `HKCU\Software\kpl_key\codingchangeworld` | `license_code` | 读写 | 激活码 |
| 同上 | `license_token` | 读写 | 授权令牌 |
| 同上 | `license_plan_type` | 写 | 套餐类型 |
| 同上 | `license_expires_at` | 写 | 到期时间 |
| 同上 | `license_invite_code` | 写 | 邀请码 |
| 同上 | `windows1.0` | 写 | 当前授权/环境状态标记 |
| `HKCU\Software\coding\kpl\kphDtbTcp` | `deviceId,lastMode` | 读写 | 设备 UUID、最近模式 |
| `HKCU\Software\coding\kpl\tcpLogin` | `loginBodyHex` | 读写 | 登录 protobuf 十六进制缓存 |

硬件设备 ID 由本机信息生成；反编译确认 `device_name` 取环境变量 `COMPUTERNAME`，`device` 由内部 `fcn.008db868` 生成/读取。

## 12. Windows、COM 和 Qt 功能接口

样本导入 16 个动态库：`Qt5Charts.dll`、`Qt5Core.dll`、`Qt5Gui.dll`、`Qt5Network.dll`、`Qt5Widgets.dll`、`Qt5Xml.dll`、`libgcc_s_dw2-1.dll`、`libstdc++-6.dll`、`gdi32.dll`、`kernel32.dll`、`msvcrt.dll`、`ole32.dll`、`oleaut32.dll`、`psapi.dll`、`shell32.dll`、`user32.dll`。

### 12.1 网络与序列化

| 接口 | 关键入参 | 返回/用途 |
|---|---|---|
| `QNetworkAccessManager::get(QNetworkRequest)` | URL、Header | `QNetworkReply*` |
| `QNetworkAccessManager::post(...)` | Request、body | 少数表单/JSON请求；具体端点以第 6/9 节为准 |
| `QNetworkRequest(QUrl)` | URL | 请求对象 |
| `QNetworkReply::readAll()` | 无 | `QByteArray` 响应体 |
| `QNetworkReply::error()` | 无 | 网络错误码 |
| `QUrlQuery::addQueryItem(k,v)` | 参数名、值 | 构造 QueryString |
| `QJsonDocument::fromJson(bytes)` | JSON bytes | 文档/解析错误 |
| `QJsonObject::value(key)` | 字段名 | `QJsonValue` |
| `QEventLoop::exec()` / `QTimer::singleShot()` | 事件标志/超时 | 同步等待异步网络响应 |

### 12.2 窗口与输入联动

| WinAPI | 关键入参 | 返回/用途 |
|---|---|---|
| `EnumWindows(callback,lParam)` | 枚举回调 | 查找第三方行情客户端窗口 |
| `FindWindowW(class,title)` | 类名、标题 | `HWND`；识别 `TdxW`、同花顺远航版/金融版等 |
| `GetWindowTextW(hwnd,buf,n)` | 窗口句柄 | 标题文本 |
| `SendMessageW/PostMessageW(hwnd,msg,wParam,lParam)` | 窗口消息 | 同步/异步联动代码或命令 |
| `SendInput(count,inputs,size)` | 键鼠输入数组 | 模拟快捷键/输入 |
| `RegisterHotKey(hwnd,id,mods,vk)` | 修饰键、虚拟键 | 全局快捷键注册 |
| `SetForegroundWindow/ShowWindow` | `HWND`、显示命令 | 激活或显示联动窗口 |

### 12.3 进程和内存

| WinAPI | 关键入参 | 返回/用途 |
|---|---|---|
| `OpenProcess(access,inherit,pid)` | 权限、PID | 进程句柄 |
| `EnumProcessModules(process,modules,cb,needed)` | 进程句柄 | 模块列表 |
| `GetModuleFileNameExW(process,module,buf,size)` | 进程/模块 | 模块路径 |
| `VirtualQueryEx(process,address,info,size)` | 地址 | 内存区域属性 |
| `VirtualAllocEx(process,address,size,type,protect)` | 大小、保护 | 远程内存地址 |
| `WriteProcessMemory(process,address,buffer,size,written)` | 地址、字节 | 写入目标进程 |
| `VirtualProtect(process-local address,...)` / `VirtualFreeEx(...)` | 地址、大小 | 修改保护/释放远程内存 |

这些导入说明程序具备进程检查或第三方客户端深度联动能力；仅凭导入不能断言每条路径均在当前配置中执行。

### 12.4 COM/OLE/WMI

| WinAPI | 输入 | 输出/用途 |
|---|---|---|
| `CoInitializeEx` / `CoUninitialize` | 线程模型 | 初始化/释放 COM |
| `CoCreateInstance(clsid,...,iid,out)` | COM 类和接口 IID | 创建 WMI/OLE/自动化对象 |
| `GetActiveObject(clsid,...)` | COM 类 | 获取已运行对象，可能用于 Excel 联动 |
| `VariantInit/Clear`、`SysAllocString/FreeString` | VARIANT/BSTR | 自动化参数编组 |

WMI 用于采集硬件信息并参与设备指纹计算；OLE 自动化用于与已安装桌面软件交互。

## 13. 反调试、代理检测和授权禁用链路

程序检查：

- 系统代理包含 `127.0.0.1`、`localhost`、`::1`；
- 抓包代理关键词：`whistle`、`fiddler`、`charles`、`burp`、`mitm`、`proxyman`、`reqable`、`httptoolkit`；
- 进程/窗口关键词：Fiddler、Charles、Wireshark、Burp Suite、mitmproxy、Proxyman、Reqable、HTTP Toolkit、x64dbg、x32dbg、OllyDbg、IDA Pro、frida 等。

命中时可调用 `/license/disable/`，传入 `code`、`token`、`device` 和 `reason`。这也是为什么文档和自动化脚本不应记录真实授权令牌。

## 14. 非业务 URL 完整分类

以下 URL 被计入 286 条原始字符串，但不应误认为业务 JSON API：

- 证书/吊销：Certum、VeriSign、GlobalSign 的 OCSP、CRL、CA certificate、CPS URL；
- 编译工具链来源：`android.googlesource.com/toolchain/llvm-project`；
- 字体元数据：`microsoft.com/typography`；
- 教程/帮助：Bilibili、语雀、蓝奏云、作者站点教程视频；
- 首页/页面：作者官网、东方财富、同花顺、九阳公社、选股宝、股吧、暗盘页面；
- 更新/下载：`update2.json`、`v8.0.7z`；
- 静态媒体：MP4、CSV、行情图片、CDN 资源。

带证书 ASN.1 尾部乱码的 URL 是签名证书数据被字符串扫描器连带截取，并非实际超长 HTTP 请求。

## 15. 调用示例（已脱敏）

### 15.1 历史打板

```http
GET /w1/api/index.php?Order=1&a=HisDaBanList&st=60&c=HisHomeDingPan&PhoneOSNew=1&Index=0&Is_st=1&PidType=1&Type=9&FilterMotherboard=0&Filter=0&FilterTIB=0&Day=2026-08-21&FilterGem=0 HTTP/1.1
Host: apphis.longhuvip.com
```

### 15.2 同花顺涨停池

```http
GET /dataapi/limit_up/limit_up_pool?page=1&limit=200&field=199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584,3475914,9003,9004&filter=HS,GEM2STAR&order_field=133970&order_type=0&date=20260821 HTTP/1.1
Host: data.10jqka.com.cn
```

### 15.3 授权激活（笔记本版真实方法）

```http
GET /license/activate/?code={LICENSE_CODE}&device={DEVICE_ID}&device_name={COMPUTERNAME}&app=kpl HTTP/1.1
Host: codingchangeworld.com
```

响应中客户端明确读取：

```json
{
  "ok": 1,
  "code": "...",
  "token": "...",
  "plan_type": "...",
  "expires_at": "...",
  "invite_code": "..."
}
```

## 16. 覆盖核对与限制

- 已覆盖笔记本版静态扫描得到的全部 286 条 URL 字符串；业务端点按“主机 + 路径 + `c/a` 动作”标准化，重复参数模板合并展示。
- 已把 API、网页、下载、图片、教程、证书 URL 分开，避免把证书和页面误算成业务接口。
- 已反编译授权激活、心跳和禁用调用链，修正旧文档把它们写成 POST JSON 的错误。
- 已列出所有导入 DLL，并对与产品功能有关的 Qt/Win32/COM 接口给出入参与返回语义；C/C++ 运行库和纯 GUI 绘制函数不属于业务接口，未逐函数展开。
- 对 URL 中直接可见的输入参数已完整记录；动态拼接但没有静态键名的参数标为“动态 Query”。
- 对客户端明确读取或关联适配代码已解析的输出字段逐项列出；其余输出标为透传 JSON/文本，必须通过合法运行环境抓包才能确认服务端当前完整 Schema。
- 上游接口、固定 Token、Cookie、签名算法和返回字段可能变更；调用时应容忍空值、字段新增、主机切换和限流。

---

生成依据：笔记本版 EXE 二进制直接证据 + radare2 XREF/`pdc` + 工作区既有接口文档与数据适配代码交叉验证。本文档不包含真实授权令牌、个人设备 ID 或可复用私密凭据。