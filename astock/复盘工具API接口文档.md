# 复盘与导出工具 v62.1 — 完整 API 接口文档

> 本文档从 `复盘与导出工具vip台式_全能.exe` 二进制中逆向提取，涵盖所有功能模块的数据接口。
> 用于后续自动化脚本开发，可直接据此生成 Python 请求代码。

---

## 目录

1. [通用信息](#1-通用信息)
2. [龙虎VIP — 核心行情数据](#2-龙虎vip--核心行情数据)
3. [同花顺 — 涨停/热门/情绪](#3-同花顺--涨停热门情绪)
4. [选股宝 — 事件/涨停池](#4-选股宝--事件涨停池)
5. [东方财富 — 行情/资金/选股](#5-东方财富--行情资金选股)
6. [通达信/腾讯 — 行情补充](#6-通达信腾讯--行情补充)
7. [九阳公社 — 产业链图谱](#7-九阳公社--产业链图谱)
8. [短线侠 — 封单/竞价](#8-短线侠--封单竞价)
9. [问财 — 智能选股](#9-问财--智能选股)
10. [其他数据源](#10-其他数据源)
11. [作者服务器 — 授权/配置](#11-作者服务器--授权配置)
12. [附录：本地联动机制](#12-附录本地联动机制)

---

## 1. 通用信息

### 1.1 请求头

所有 HTTP 请求统一使用以下 User-Agent：

```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36
```

### 1.2 请求方式

| 接口来源 | 默认方式 |
|----------|---------|
| longhuvip.com 系列 | GET，参数在 URL QueryString |
| 10jqka.com.cn 系列 | GET |
| eastmoney.com 系列 | GET |
| codingchangeworld.com | GET（页面）/ POST（授权） |

### 1.3 通用参数说明

| 参数名 | 含义 | 示例值 |
|--------|------|--------|
| `Index` | 分页页码，从 0 开始 | `0` |
| `st` | 每页条数 | `60`, `100`, `500`, `1000`, `2000` |
| `Date` / `Day` | 日期，格式 `YYYY-MM-DD` 或 `YYYYMMDD` | `2026-08-21` |
| `PhoneOSNew` | 固定值 | `1` |
| `Order` | 排序方向，`0`=降序, `1`=升序 | `1` |
| `Type` | 类型筛选 | `1`, `4`, `6`, `7`, `9`, `18` |
| `StockID` | 股票/指数代码 | `SH000001`, `002230` |
| `Token` | 认证令牌（部分接口需要） | 32位 hex |
| `UserID` | 用户ID（部分接口需要） | `1973778` |
| `DeviceID` | 设备ID | UUID 格式 |
| `apiv` | API 版本 | `w33`, `w43`, `w44` |
| `VerSion` | 客户端版本 | `5.22.0.7` |

### 1.4 响应格式

所有接口返回 **JSON**。龙虎VIP 接口的 JSON 结构通常为：

```json
{
  "State": 0,
  "Data": [...],
  "Count": 100,
  "Page": 0
}
```

---

## 2. 龙虎VIP — 核心行情数据

### 2.1 域名速查

| 域名 | 用途 | 数据时效 |
|------|------|---------|
| `apphq.longhuvip.com` | 实时行情 | 盘中实时 |
| `apphis.longhuvip.com` | 历史行情 | 历史回溯 |
| `apphwhq.longhuvip.com` | 盘后/午后行情 | 盘后 |
| `apphwshhq.longhuvip.com` | 盘后上海行情 | 盘后 |
| `applhb.longhuvip.com` | 龙虎榜 | 历史+实时 |
| `apparticle.longhuvip.com` | 文章/资讯 | 历史 |
| `apphis.kaipanhong.com` | 概念板块历史 | 历史 |
| `apphq.kaipanhong.com` | 概念板块实时 | 实时 |
| `appcdn.longhuvip.com` | CDN 静态资源 | - |

---

### 2.2 apphis.longhuvip.com — 历史行情

#### 2.2.1 历史打板列表（主要涨停数据）

```
GET https://apphis.longhuvip.com/w1/api/index.php
```

| 参数 | 值 | 说明 |
|------|-----|------|
| `Order` | `1` | |
| `a` | `HisDaBanList` | 接口名 |
| `st` | `60` | 每页条数 |
| `c` | `HisHomeDingPan` | 模块名 |
| `PhoneOSNew` | `1` | |
| `Index` | `{页码}` | 从 0 开始 |
| `Is_st` | `1` | 包含 ST |
| `PidType` | `1` | |
| `Type` | `9` | |
| `FilterMotherboard` | `0` | |
| `Filter` | `0` | |
| `FilterTIB` | `0` | |
| `Day` | `{日期}` | 格式 YYYY-MM-DD |
| `FilterGem` | `0` | 不过滤创业板 |

**完整 URL：**
```
https://apphis.longhuvip.com/w1/api/index.php?Order=1&a=HisDaBanList&st=60&c=HisHomeDingPan&PhoneOSNew=1&Index=0&Is_st=1&PidType=1&Type=9&FilterMotherboard=0&Filter=0&FilterTIB=0&Day=2026-08-21&FilterGem=0
```

#### 2.2.2 涨停表现分析（DailyLimitPerformance）

```
GET https://apphis.longhuvip.com/w1/api/index.php
```

| 参数 | 值 |
|------|-----|
| `Order` | `0` |
| `st` | `2000` |
| `a` | `DailyLimitPerformance` |
| `c` | `HisHomeDingPan` |
| `PhoneOSNew` | `1` |
| `Index` | `0` |
| `Type` | `4` |
| `PidType` | `{类型}` |

**变体（DailyLimitPerformance2）：** `st=500`

#### 2.2.3 指数排行（RealRankingInfo）

```
GET https://apphis.longhuvip.com/w1/api/index.php?Order=1&a=RealRankingInfo&st=60&c=ZhiShuRanking&PhoneOSNew=1&Index=0&Date=2026-08-21&Type=1&ZSType=7
```

#### 2.2.4 指数成分股列表（ZhiShuStockList_W8）

```
GET https://apphis.longhuvip.com/w1/api/index.php?Order=1&TSZB=0&a=ZhiShuStockList_W8&st=60&c=ZhiShuRanking&PhoneOSNew=1&old=1&IsZZ=0&Index=0&Date=2026-08-21&Type=6&IsKZZType=0&PlateID=801001&TSZB_Type=0&filterType=0
```

#### 2.2.5 早盘竞价列表（MorningBiddingList）

```
GET https://apphis.longhuvip.com/w1/api/index.php?Order=1&a=MorningBiddingList&st=60&c=HisHomeDingPan&PhoneOSNew=1
```

#### 2.2.6 大盘回顾（DiskReview）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=DiskReview&c=HisHomeDingPan&PhoneOSNew=1&Day=2026-08-21
```

#### 2.2.7 板块竞价（GetBKJJ_w36 / GetBKJJBL）

```
GET https://apphis.longhuvip.com/w1/api/index.php?Order=1&st=60&a=GetBKJJ_w36&c=StockBidYiDong&PhoneOSNew=1&Index=0&Type=1
GET https://apphis.longhuvip.com/w1/api/index.php?Order=1&a=GetBKJJBL&st=60&IsLB=0&c=StockBidYiDong&PhoneOSNew=1&IsZT=0&Isst=1&Index=0
```

#### 2.2.8 板块信息（GetPlateInfo_w38）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetPlateInfo_w38&st=100&c=HisLimitResumption&PhoneOSNew=1&Index=0&Date=2026-08-21
```

#### 2.2.9 K线涨停原因（KLineZhangTingReason）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=KLineZhangTingReason&c=HisLimitResumption&PhoneOSNew=1&Date=2026-08-21
```

#### 2.2.10 涨跌分析（RiseFallAnalysis）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=RiseFallAnalysis&st=10000&c=HisHomeDingPan&PhoneOSNew=1&Index=0
```

#### 2.2.11 市场量能（MarketSCLN）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=MarketSCLN&c=HisHomeDingPan&PhoneOSNew=1&Date=2026-08-21
```

#### 2.2.12 历史涨幅详情（HisZhangFuDetail）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=HisZhangFuDetail&c=HisHomeDingPan&PhoneOSNew=1&Day=2026-08-21
```

#### 2.2.13 个股历史涨停（GetDayZhangTing）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetDayZhangTing&st=25&c=HisLimitResumption&PhoneOSNew=1&VerSion=5.22.0.6&Index=0&apiv=w43&StockID=002230
```

#### 2.2.14 板块K线（GetPlateKLineDay）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetPlateKLineDay&st=630&c=ZhiShuKLine&PhoneOSNew=1&Token=0&Index=0&Type=d&StockID=801001
```

#### 2.2.15 指数K线（GetDayBaseFaceListZDEvnArt）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetDayBaseFaceListZDEvnArt&st=1000&c=ZhiShuKLine&PhoneOSNew=1&Index=0&Type=0&StockID=SH000001
```

#### 2.2.16 实时指数（GetZsReal）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetZsReal&c=StockL2History&Day=2026-08-21
```

#### 2.2.17 雷达数据（Radar）

```
GET https://apphis.longhuvip.com/w1/api/index.php?st=6000&a=Radar&Index=0&c=HisHomeDingPan&Date=2026-08-21
```

#### 2.2.18 异动复盘系列（FuPanLa）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetPMSL_KQXY&c=FuPanLa&PhoneOSNew=1&Date=2026-08-21
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetPMSL_PMLD&st=1000&c=FuPanLa&PhoneOSNew=1&Index=0&Date=2026-08-21
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetYTFP_BKHX&c=FuPanLa&Date=2026-08-21
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetYTFP_LHBDX&c=FuPanLa&Date=2026-08-21
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetYTFP_SCTD&c=FuPanLa&PhoneOSNew=1&Date=2026-08-21
```

#### 2.2.19 新高分组

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GroupCount_w28&Type=0_0_0_0_0&c=StockNewHigh&PhoneOSNew=1&Date=2026-08-21
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetGroupStock_ByGroup_W28&Type=0_0_0_0_0&c=StockNewHigh&PhoneOSNew=1&Date=2026-08-21
```

#### 2.2.20 子板块信息（SonPlate_Info）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=SonPlate_Info&c=ZhiShuRanking&IsShow=1&Date=2026-08-21
```

#### 2.2.21 直播内容（ZhiBoContent）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=ZhiBoContent&st=0&c=HisConceptionPoint&PhoneOSNew=1&index=0&Date=2026-08-21
```

#### 2.2.22 股东/仓位（GetGuDong）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetGuDong&Type=2&c=YiDianCangWei&PhoneOSNew=1&StockID=002230
```

#### 2.2.23 增量趋势/量能

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetTrendIncremental&c=ZhiShuL2Data&PhoneOSNew=1&StockID=SH000001
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetVolTurIncremental&apiv=w44&c=ZhiShuL2Data&StockID=SH000001
```

#### 2.2.24 外盘驱动（GetWPQC）

```
GET https://apphis.longhuvip.com/w1/api/index.php?Order=1&a=GetWPQC&st=1000&c=StockBidYiDong&PhoneOSNew=1&Index=0&Type=1
```

#### 2.2.25 访谈/连线

```
GET https://apphis.longhuvip.com/w1/api/index.php?Order=1&a=GetInterviewsByDateZS&st=1000&c=StockLineData&PhoneOSNew=1&DEnd=2026-08-21
GET https://apphis.longhuvip.com/w1/api/index.php?Order=1&st=60&a=GetInterviewsByDateStock&c=StockLineData&PhoneOSNew=1&DEnd=2026-08-21
```

#### 2.2.26 涨停封单（GetFengKListBest）

```
GET https://apphis.longhuvip.com/w1/api/index.php?PhoneOSNew=1&c=StockFengKData&a=GetFengKListBest&Time=0930&Day=2026-08-21
```

#### 2.2.27 历史排行（HisRankingInfo_W8）

```
GET https://apphis.longhuvip.com/w1/api/index.php?Order=1&a=HisRankingInfo_W8&st=6000&c=HisStockRanking&PhoneOSNew=1&RStart=0
```

#### 2.2.28 移动端突破（GetYDTP_WXHJ_His）

```
GET https://apphis.longhuvip.com/w1/api/index.php?a=GetYDTP_WXHJ_His&st=6000&c=StockBidYiDong&Token=9db76fbc981cc796139fbacfb26c9304&Index=25&UserID=2653861
```

---

### 2.3 apphq.longhuvip.com — 实时行情

#### 2.3.1 实时涨停表现

```
GET https://apphq.longhuvip.com/w1/api/index.php?Order=0&a=DailyLimitPerformance&st=1000&Type=4&c=HomeDingPan&PhoneOSNew=1&Index=0&PidType=1
GET https://apphq.longhuvip.com/w1/api/index.php?Order=0&a=DailyLimitPerformance2&st=500&Type=4&c=HomeDingPan&PhoneOSNew=1&Index=0&PidType=1
```

#### 2.3.2 实时指数排行

```
GET https://apphq.longhuvip.com/w1/api/index.php?Order=1&a=RealRankingInfo&st=60&Type=1&c=ZhiShuRanking&PhoneOSNew=1&Index=0&ZSType=7
```

#### 2.3.3 实时成分股

```
GET https://apphq.longhuvip.com/w1/api/index.php?Order=1&a=ZhiShuStockList_W8&st=60&c=ZhiShuRanking&PhoneOSNew=1&RStart=0925&old=1&IsZZ=0&Token=0&Index=0
```

#### 2.3.4 热门排行（GetHotPHB）

```
GET https://apphq.longhuvip.com/w1/api/index.php?Order=1&st=100&a=GetHotPHB&c=StockBidYiDong&PhoneOSNew=1&Token=d336f47db0d11c37400313830329564e&Index=0&Type=1&UserID=1973778
```

#### 2.3.5 实时大盘回顾

```
GET https://apphq.longhuvip.com/w1/api/index.php?a=DiskReview&c=HomeDingPan&PhoneOSNew=1
```

#### 2.3.6 涨跌统计

```
GET https://apphq.longhuvip.com/w1/api/index.php?a=ChangeStatistics&st=100&c=HomeDingPan
```

#### 2.3.7 实时板块信息

```
GET https://apphq.longhuvip.com/w1/api/index.php?a=GetPlateInfo&st=1000&c=DailyLimitResumption&Index=0
```

#### 2.3.8 实时板块竞价

```
GET https://apphq.longhuvip.com/w1/api/index.php?Order=1&st=60&a=GetBKJJ_w36&c=StockBidYiDong&PhoneOSNew=1&Index=0&Type=1
```

#### 2.3.9 增量趋势/量能

```
GET https://apphq.longhuvip.com/w1/api/index.php?a=GetTrendIncremental&c=ZhiShuL2Data&StockID=SH000001
GET https://apphq.longhuvip.com/w1/api/index.php?a=GetVolTurIncremental&c=ZhiShuL2Data&StockID=SH000001
```

#### 2.3.10 精选板块（GetFeaturedSection）

```
GET https://apphq.longhuvip.com/w1/api/index.php?a=GetFeaturedSection&c=StockL2Data&StockID=SH000001
```

#### 2.3.11 子板块信息

```
GET https://apphq.longhuvip.com/w1/api/index.php?a=SonPlate_Info&c=ZhiShuRanking&PhoneOSNew=1&DEnd=2026-08-21
GET https://apphq.longhuvip.com/w1/api/index.php?a=SonPlate_Info&c=ZhiShuRanking&PhoneOSNew=1&PlateID=801001
```

#### 2.3.12 自选股刷新

```
GET https://apphq.longhuvip.com/w1/api/index.php?a=RefreshStockList&c=UserSelectStock&PhoneOSNew=1&Token={token}
```

#### 2.3.13 偏离值

```
GET https://apphq.longhuvip.com/w1/api/index.php?a=GetPianLiZhi_Index&apiv=w43&c=StockBidYiDong&ZDJK_Type=1
GET https://apphq.longhuvip.com/w1/api/index.php?a=GetPianLiZhi_Many&c=StockBidYiDong&PhoneOSNew=1
```

#### 2.3.14 新高分组

```
GET https://apphq.longhuvip.com/w1/api/index.php?a=GroupCount_w28&Type=0_0_0_0_0&c=StockNewHigh&PhoneOSNew=1
GET https://apphq.longhuvip.com/w1/api/index.php?a=GetGroupStock_ByGroup_W28&Type=0_0_0_0_0&c=StockNewHigh&PhoneOSNew=1&GroupID={ID}
```

#### 2.3.15 指数信息

```
GET https://apphq.longhuvip.com/w1/api/index.php?c=Index&a=GetInfo&View=2,3,4,5,7,8,9,10,11
```

---

### 2.4 apphwhq.longhuvip.com — 盘后行情

#### 2.4.1 实时涨停表现

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?Order=0&a=DailyLimitPerformance&st=2000&Type=4&c=HomeDingPan&PhoneOSNew=1&Index=0&PidType=1
```

#### 2.4.2 实时指数排行

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?Order=1&a=RealRankingInfo&st=60&Type=1&c=ZhiShuRanking&PhoneOSNew=1&Index=0
```

#### 2.4.3 K线涨停（GetKLineZhangTing）

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetKLineZhangTing&c=StockLineData&PhoneOSNew=1&StockID=002230
```

#### 2.4.4 个股盘口（GetStockPanKou_Narrow）

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetStockPanKou_Narrow&c=StockL2Data&StockID=002230
```

#### 2.4.5 个股所属板块（GetStockIDPlate）

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetStockIDPlate&Type=2&c=StockL2Data&StockID=002230
```

#### 2.4.6 板块区间信息（GetPlate_Info_QJ）

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetPlate_Info_QJ&c=ZhiShuRanking&PhoneOSNew=1&PlateID=801001
```

#### 2.4.7 板块信息 w38

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetPlateInfo_w38&st=100&c=DailyLimitResumption&PhoneOSNew=1&Index=0
```

#### 2.4.8 实时个股盘口（StockDPRealData）

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=StockDPRealData&c=StockYiDongKanPan&StockID=002230
```

#### 2.4.9 自选股刷新

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=RefreshStockList_W8&c=UserSelectStock&StockIDList={代码列表}
```

#### 2.4.10 异动突破系列

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetYDTP_WXHJ_His&c=StockBidYiDong
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetYDTP_ZDJK_His&c=StockBidYiDong
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetYDTP_ZDJK_Today&c=StockBidYiDong
```

#### 2.4.11 异动复盘

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetYTFP_BKHX&c=FuPanLa&PhoneOSNew=1
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetYTFP_LHBDX&c=FuPanLa
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetYTFP_SCTD&c=FuPanLa&PhoneOSNew=1
```

#### 2.4.12 盘面梳理

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetPMSL_KQXY&c=FuPanLa&PhoneOSNew=1
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetPMSL_PMLD&st=1000&c=FuPanLa&PhoneOSNew=1&Index=0
```

#### 2.4.13 早盘竞价

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?Order=1&a=MorningBiddingList&st=60&c=HomeDingPan&PhoneOSNew=1
```

#### 2.4.14 板块竞价区间

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?Order=1&a=GetBKJJBL&st=60&IsLB=0&c=StockBidYiDong&PhoneOSNew=1&IsZT=0&Isst=1&Index=0
```

#### 2.4.15 外盘驱动

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?Order=1&a=GetWPQC&st=1000&c=StockBidYiDong
```

#### 2.4.16 直播内容

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=ZhiBoContent&c=ConceptionPoint&PhoneOSNew=1&index=0
```

#### 2.4.17 雷达

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?st=30&a=Radar&Index=0&c=HomeDingPan
```

#### 2.4.18 指数K线

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?a=GetBaseFaceListZDEvnArtNew&c=ZhiShuL2Data&StockID=SH000001
```

#### 2.4.19 访谈

```
GET https://apphwhq.longhuvip.com/w1/api/index.php?Order=1&a=InterviewsByDate&st=60&c=ZhiShuRanking&PhoneOSNew=1&DEnd=2026-08-21
GET https://apphwhq.longhuvip.com/w1/api/index.php?Order=1&st=60&a=GetInterviewsByDateStock&c=StockLineData&PhoneOSNew=1&DEnd=2026-08-21
```

---

### 2.5 apphwshhq.longhuvip.com — 盘后上海

#### 2.5.1 实时成分股（带竞价时段 RStart=0925）

```
GET https://apphwshhq.longhuvip.com/w1/api/index.php?Order=1&TSZB=0&a=ZhiShuStockList_W8&st=60&c=ZhiShuRanking&PhoneOSNew=1&RStart=0925&old=1&IsZZ=0&Index=0&REnd=1500
```

#### 2.5.2 实时指数排行（带竞价时段）

```
GET https://apphwshhq.longhuvip.com/w1/api/index.php?Order=1&RStart=0925&a=RealRankingInfo&st=22&Type=1&c=ZhiShuRanking&PhoneOSNew=1&Index=0&REnd=1500
```

#### 2.5.3 实时涨停表现

```
GET https://apphwshhq.longhuvip.com/w1/api/index.php?Order=0&a=DailyLimitPerformance&st=2000&Type=4&c=HomeDingPan&PhoneOSNew=1&Index=0&PidType=1
```

#### 2.5.4 个股盘口

```
GET https://apphwshhq.longhuvip.com/w1/api/index.php?a=GetStockPanKou&c=StockL2Data&StockID=002230
```

#### 2.5.5 涨停封单

```
GET https://apphwshhq.longhuvip.com/w1/api/index.php?c=StockFengKData&a=GetFengKListBest&Time=0930
```

---

### 2.6 applhb.longhuvip.com — 龙虎榜

#### 2.6.1 龙虎榜股票列表

```
GET https://applhb.longhuvip.com/w1/api/index.php?st=500&a=GetStockList&c=LongHuBang&PhoneOSNew=1&Token=d336f47db0d11c37400313830329564e&Time=2026-08-21&Index=0&Type=2&UserID=1973778
```

#### 2.6.2 主题/题材列表

```
GET https://applhb.longhuvip.com/w1/api/index.php?a=InfoList&st=1000&c=Topic&PhoneOSNew=1&UserID=2653861&Token=f4ae7604feffe0fc70be9fd50632a128&index=0
```

#### 2.6.3 主题/题材详情

```
GET https://applhb.longhuvip.com/w1/api/index.php?a=InfoGet&c=Theme&PhoneOSNew=1
GET https://applhb.longhuvip.com/w1/api/index.php?a=InfoGet&c=Topic&PhoneOSNew=1&UserID=1973778&Token=d336f47db0d11c37400313830329564e&ID={ID}
```

---

### 2.7 apparticle.longhuvip.com — 文章/资讯

```
GET https://apparticle.longhuvip.com/w1/api/index.php?ColumnID=2&a=GetInfo&st=60&apiv=w33&c=ForumsMsgColumn&PhoneOSNew=1&UserID=1973778&DeviceID=ffffffff-e91e-5efd-ffff-ffffa460846b&VerSion=5.11.0.6&Index=0
GET https://apparticle.longhuvip.com/w1/api/index.php?ColumnID=3&a=GetInfo&st=60&c=ForumsMsgColumn&PhoneOSNew=1&Index=0
GET https://apparticle.longhuvip.com/w1/api/index.php?a=GetInfo&c=ForumsMsgJX&MsgID={ID}
```

---

### 2.8 apphis.kaipanhong.com — 概念板块历史

```
GET https://apphis.kaipanhong.com/w1/api/index.php?a=GetPoint&c=HisConceptionPoint&PhoneOSNew=1&Date=2026-08-21
GET https://apphis.kaipanhong.com/w1/api/index.php?a=GetZsTrend&c=StockL2History&StockID=SH000001
GET https://apphis.kaipanhong.com/w1/api/index.php?st=20&a=GetDayBaseFaceListZDEvnArt&c=ZhiShuKLine&PhoneOSNew=1&DeviceID=49e6fc5f-1523-3d26-9af5-ed0e3f5b01f9&VerSion=6.0.10&Index=0&Red=1&apiv=w45&Type=0&StockID=SH000001&IsBoom=0
```

---

### 2.9 apphq.kaipanhong.com — 概念板块实时

```
GET https://apphq.kaipanhong.com/w1/api/index.php?a=GetPoint&c=ConceptionPoint&PhoneOSNew=1
GET https://apphq.kaipanhong.com/w1/api/index.php?a=GetZsTrend&c=StockL2Data&PhoneOSNew=1&StockID=SH000001
```

---

## 3. 同花顺 — 涨停/热门/情绪

### 3.1 data.10jqka.com.cn

#### 3.1.1 涨停池

```
GET https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool
```

| 参数 | 值 | 说明 |
|------|-----|------|
| `page` | `1` | 页码 |
| `limit` | `200` | 每页条数 |
| `field` | `199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584,3475914,9003,9004` | 返回字段 |
| `filter` | `HS,GEM2STAR` | 过滤 |
| `order_field` | `133970` | 排序字段 |
| `order_type` | `0` | 0=降序 |
| `date` | `20260821` | YYYYMMDD |

**完整 URL：**
```
https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool?page=1&limit=200&field=199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584,3475914,9003,9004&filter=HS,GEM2STAR&order_field=133970&order_type=0&date=20260821
```

#### 3.1.2 板块涨停 Top

```
GET https://data.10jqka.com.cn/dataapi/limit_up/block_top
```

#### 3.1.3 成交排行

```
GET https://data.10jqka.com.cn/dataapi/transaction/stock/v1/list?order_field=change&order_type=desc&date=20260821
```

---

### 3.2 eq.10jqka.com.cn

#### 3.2.1 热门板块概念

```
GET https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_plate/concept/data.txt
```

返回文本格式（非 JSON），包含热门概念板块列表。

#### 3.2.2 热门个股（小时级）

```
GET https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_stock/a/hour/data.txt
```

#### 3.2.3 竞价机会

```
GET https://eq.10jqka.com.cn/call_auction_v2/stock_chance/v1/{code}/{date}
```

#### 3.2.4 竞价页面

```
GET https://eq.10jqka.com.cn/webpage/call-auction/selfchance.html
```

---

### 3.3 comment.10jqka.com.cn — 涨停人气

```
GET https://comment.10jqka.com.cn/tzrl/getTzrlData.php?callback=callback_dt&type=data&date=20260821
```

返回 JSONP 格式。

---

### 3.4 dq.10jqka.com.cn — 分时图

```
GET https://dq.10jqka.com.cn/fuyao/market_analysis_api/chart/v1/get_chart_data?chart_key=turnover_minute
```

---

### 3.5 news.10jqka.com.cn — 新闻推送

```
GET https://news.10jqka.com.cn/pclient/news/push/stock/1.json
```

---

## 4. 选股宝 — 事件/涨停池

### 4.1 flash-api.xuangubao.com.cn

#### 4.1.1 历史事件

```
GET https://flash-api.xuangubao.com.cn/api/event/history
```

| 参数 | 说明 |
|------|------|
| `count` | 条数 |
| `types` | 事件类型 |

#### 4.1.2 涨停池

```
GET https://flash-api.xuangubao.com.cn/api/pool/detail?pool_name=limit_up&date=2026-08-21
```

#### 4.1.3 破板池

```
GET https://flash-api.xuangubao.com.cn/api/pool/detail?pool_name=limit_up_broken&date=2026-08-21
```

#### 4.1.4 涨停板块

```
GET https://flash-api.xuangubao.com.cn/api/surge_stock/plates?date=2026-08-21
```

#### 4.1.5 涨停个股

```
GET https://flash-api.xuangubao.com.cn/api/surge_stock/stocks?date=2026-08-21&normal=true&uplimit=true
```

---

## 5. 东方财富 — 行情/资金/选股

### 5.1 push2.eastmoney.com

#### 5.1.1 全市场列表

```
GET https://push2.eastmoney.com/api/qt/clist/get
```

| 参数 | 值 |
|------|-----|
| `pn` | `1` |
| `pz` | `20000` |
| `po` | `1` |
| `np` | `1` |
| `ut` | `bd1d9ddb04089700cf9c27f6f7426281` |
| `fltt` | `2` |
| `invt` | `2` |
| `fields` | `f2,f3,f12,f14,...` |
| `fs` | `m:0+t:6,m:0+t:80,m:1+t:2` |

#### 5.1.2 自选行情

```
GET https://push2.eastmoney.com/api/qt/ulist.np/get
```

| 参数 | 值 |
|------|-----|
| `ut` | `f057cbcbce2a86e2866ab8877db1d059` |
| `fltt` | `2` |
| `invt` | `2` |
| `fields` | `f14,f148,f3,f12,f2,f13,f29` |
| `secids` | `{逗号分隔代码}` |

**URL 示例：**
```
http://push2.eastmoney.com/api/qt/ulist.np/get?ut=f057cbcbce2a86e2866ab8877db1d059&fltt=2&invt=2&fields=f14,f148,f3,f12,f2,f13,f29&secids=1.000001,0.002230
```

---

### 5.2 emcfgdata.eastmoney.com — 题材投资

```
GET https://emcfgdata.eastmoney.com/api/themeInvest/getThemeList
GET https://emcfgdata.eastmoney.com/api/themeInvest/getStockList
GET https://emcfgdata.eastmoney.com/api/themeInvest/getTodayChance
GET https://emcfgdata.eastmoney.com/api/themeInvest/getFryTomorrowList
```

---

### 5.3 np-tjxg-b.eastmoney.com — 智能选股

```
GET https://np-tjxg-b.eastmoney.com/api/smart-tag/stock/v3/pw/search-code
```

---

### 5.4 np-weblist.eastmoney.com — 724 快讯

```
GET https://np-weblist.eastmoney.com/comm/web/getFastNewsList
```

| 参数 | 值 |
|------|-----|
| `client` | `web` |
| `biz` | `web_724` |
| `fastColumn` | `102` |
| `sortEnd` | 空 |
| `pageSize` | `50` |
| `req_trace` | `{毫秒时间戳}` |
| `_` | `{毫秒时间戳}` |

---

### 5.5 datacenter.eastmoney.com

```
GET https://datacenter.eastmoney.com/securities/api/data/v1/get
```

---

### 5.6 gbcdn.dfcfw.com — 人气排名

```
GET http://gbcdn.dfcfw.com/rank/popularityList.js?type=0&sort=0&page=1
```

---

### 5.7 webquotepic.eastmoney.com — K线图

```
GET http://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&nid={图片ID}
```

### 5.8 webquoteklinepic.eastmoney.com — K线图

```
GET https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={图片ID}
```

---

## 6. 通达信/腾讯 — 行情补充

### 6.1 qt.gtimg.cn — 腾讯行情

```
GET http://qt.gtimg.cn/q=s_{代码}
```

返回格式：`v_sz000001="当前价~涨跌~涨幅~..."` 类 JSON 文本。

### 6.2 web.ifzq.gtimg.cn — 腾讯分时图

```
GET https://web.ifzq.gtimg.cn/appstock/app/minute/query?_var=&code=sh000001&r={随机数}
```

### 6.3 pul.tdx.com.cn — 通达信热门股票

```
GET https://pul.tdx.com.cn/TQLEX?Entry=JNLPSE.hotStockList&RI={随机数}
```

### 6.4 page3.tdx.com.cn — 通达信板块

```
GET http://page3.tdx.com.cn:7615/site/pcwebcall_static/bxb/json/
```

### 6.5 hot.icfqs.com — 通达信联动

```
GET http://hot.icfqs.com:7615/site/tdx-pc-pcwebcall/page-qxzb.html?color=0&bkcolor=000000
GET http://hot.icfqs.com:7615/TQLEX?Entry=CWServ.cfg_tk_scqx&RI={随机数}
GET http://hot.icfqs.com:7615/TQLEX?Entry=CWServ.pcwebcall_yzfp_mmmx
GET http://hot.icfqs.com:7615/TQLEX?Entry=CWServ.pcwebcall_yzfp_yzdx
```

### 6.6 excalc.icfqs.com

```
GET http://excalc.icfqs.com:7616/TQLEX?Entry=HQServ.hq_nlp
```

---

## 7. 九阳公社 — 产业链图谱

### 7.1 app.jiuyangongshe.com

```
GET https://app.jiuyangongshe.com/jystock-app/api/v1/action/diagram-url
GET https://app.jiuyangongshe.com/jystock-app/api/v1/action/field
GET https://app.jiuyangongshe.com/jystock-app/api/v1/action/list
GET https://app.jiuyangongshe.com/jystock-app/api/v1/industry/list
```

---

## 8. 短线侠 — 封单/竞价

### 8.1 duanxianxia.com

```
GET https://duanxianxia.com/api/getFengdanLast
GET https://duanxianxia.com/vendor/stockdata/jjlive.json
GET https://duanxianxia.com/vendor/stockdata/platechart1.json
```

---

## 9. 问财 — 智能选股

### 9.1 www.iwencai.com

```
GET https://www.iwencai.com/gateway/urp/v7/landing/getDataList
GET https://www.iwencai.com/unifiedwap/unified-wap/v2/result/get-robot-data
```

---

## 10. 其他数据源

### 10.1 api.duishu.com — 堆书涨停

```
GET https://api.duishu.com/lhbapp/zhangting/index
```

| 参数 | 值 |
|------|-----|
| `pagecount` | `200` |
| `page` | `1` |
| `type` | `7` |
| `apiversion` | `8.9` |
| `device_id` | `wuxiao20fb7a24-6420-46f3-b104-4f3ff8ec15dc` |
| `dxwappid` | `dxw88888` |
| `dxwsign` | `{签名}` |

### 10.2 x-quote.cls.cn — 财联社

```
GET https://x-quote.cls.cn/v2/quote/a/plate/up_down_analysis
```

### 10.3 www.tgb.cn — 淘股吧

```
GET https://www.tgb.cn/new/nrnt/getNoticeStock?type=H
```

### 10.4 www.59155188.xyz — 自定义数据

```
GET https://www.59155188.xyz/api/get_csv
GET https://www.59155188.xyz/api/get_sign
```

### 10.5 49.51.133.138:8000

```
GET http://49.51.133.138:8000/history
```

---

## 11. 作者服务器 — 授权/配置

### 11.1 codingchangeworld.com

#### 11.1.1 授权激活

```
POST https://codingchangeworld.com/license/activate/
```

**请求体（JSON）：**
```json
{
  "license_code": "qq_200_22693601853434",
  "device_name": "LAPTOP-NM9A7VAF",
  "license_device_id": "HW-{64位hex}",
  "device": "{设备ID}",
  "app": "复盘与导出工具",
  "token": "{token}"
}
```

**响应状态码：**

| status | 含义 |
|--------|------|
| `available` | 激活成功 |
| `not_found` | 激活码无效 |
| `expired` | 授权已到期 |
| `disabled` | 授权已被禁用 |
| `device_mismatch` | 该授权已绑定其他电脑 |
| `trial_used` | 该设备已领取过试用 |
| `invite_daily_limit` | 邀请码今日名额已用完 |
| `kicked` | 被踢下线 |

#### 11.1.2 授权禁用

```
POST https://codingchangeworld.com/license/disable/
```

#### 11.1.3 心跳保活

```
POST https://codingchangeworld.com/license/heartbeat/
```

**请求体：**
```json
{
  "token": "{license_token}",
  "device": "{设备ID}"
}
```

#### 11.1.4 邀请码信息

```
GET https://codingchangeworld.com/license/invite/info/
```

#### 11.1.5 其他功能接口

```
GET https://www.codingchangeworld.com/getCurrentTime/
GET https://codingchangeworld.com/searchCode/?code={代码}
GET https://codingchangeworld.com/kplGetCode/
GET https://codingchangeworld.com/dfcfxgmy/
GET https://www.codingchangeworld.com/jcyd/cache/
GET https://codingchangeworld.com/jcydCookies/
GET https://www.codingchangeworld.com/updateTck/
POST https://www.codingchangeworld.com/addAdvice/
GET https://www.codingchangeworld.com/aiFp/
GET https://www.codingchangeworld.com/apzjgj/history/
GET https://www.codingchangeworld.com/bkzjgj/history/
GET https://www.codingchangeworld.com/kplbkzjgj/history/
GET https://www.codingchangeworld.com/jjfd_history/
GET https://www.codingchangeworld.com/rqb_history/
GET https://www.codingchangeworld.com/AGztyy/
```

---

### 11.2 OSS 静态资源

```
GET https://codingchangeworld.oss-cn-beijing.aliyuncs.com/update2.json   # 版本更新
GET https://codingchangeworld.oss-cn-beijing.aliyuncs.com/kpl.txt        # 开盘啦板块
GET https://codingchangeworld.oss-cn-beijing.aliyuncs.com/gnb.txt        # 概念板块
GET https://codingchangeworld.oss-cn-beijing.aliyuncs.com/SB.txt         # 首板
```

---

## 12. 附录：本地联动机制

### 12.1 通达信联动

通过 Windows 窗口句柄与通达信联动：

| 操作 | 方式 |
|------|------|
| 读取自选股 | 读取 `T0002/blocknew/*.blk` 文件 |
| 标记数据 | 读写 `T0002/mark.dat` |
| 窗口联动 | 查找 `TdxW` 类名窗口 |

**板块文件：** ZTB, ZTEB, ZTSB, ZTGJJ, ZRZTBX, DTB, SLB, WLB, FXB, DCRQB, TDXRQB, KPLRQB, THSRQB, TGBRQB, DCZNXG, THSWCXG, THSZT, JJZT, JJYP, ZXG, ZPJJ, ZQFK, GDB, WPQC, JCGSYD, SBZT, LBTT, XGBRDJD, JRLY

### 12.2 同花顺联动

查找 `同花顺远航版` / `同花顺金融` 窗口标题实现联动。

### 12.3 本地配置文件

| 文件 | 用途 |
|------|------|
| `StockList.ini` | 股票代码-名称映射（GBK 编码） |
| `LiandongConfig.ini` | 联动配置 |
| `start.ini` | 启动页配置 |
| `select.ini` | 选股配置 |
| `page.ini` | 页面配置 |
| `tablelayout.ini` | 表格布局 |
| `tuozhuaiColumn.ini` | 拖拽列配置 |
| `快捷键.ini` | 快捷键配置 |
| `gpbb.ini` | 股票报表 |
| `jjxg.ini` | 精选选股 |
| `dpzb.ini` | 大盘指标 |
| `apzjgj.ini` | A股资金轨迹 |
| `bkzjgj.ini` | 板块资金轨迹 |
| `kplbkzjgj.ini` | 开盘啦板块资金轨迹 |
| `stock-data.json` | 缓存数据 |

### 12.4 注册表

| 路径 | 内容 |
|------|------|
| `HKCU\Software\kpl_key\codingchangeworld` | `license_device_id`（HW-{64位hex}） |
| `HKCU\Software\coding\kpl\kphDtbTcp` | `deviceId`（UUID）, `lastMode` |
| `HKCU\Software\coding\kpl\tcpLogin` | `loginBodyHex`（protobuf） |

### 12.5 硬件指纹

- `device_name`：环境变量 `COMPUTERNAME`
- `license_device_id`：`HW-{SHA256}` 格式，通过 WMI COM 采集硬件信息计算
- `deviceId`：UUID 格式设备ID

---

## 附录 A：反检测机制

程序检测到以下环境时自动调用 `/license/disable/` 禁用授权：

**系统代理检测：** 代理地址包含 `127.0.0.1`, `localhost`, `::1`, `whistle`, `fiddler`, `charles`, `burp`, `mitm`, `proxyman`, `reqable`, `httptoolkit`

**进程/窗口检测：** Fiddler, Charles, Wireshark, Burp Suite, mitmproxy, Proxyman, Reqable, HTTP Toolkit, x64dbg, x32dbg, OllyDbg, IDA Pro, frida 等

---

## 附录 B：程序版本信息

| 字段 | 值 |
|------|------|
| 版本号 | `62.1` |
| 内部版本 | `5.22.0.7` |
| 作者 | 代码改变世界 |
| 微信 | `liuyoudyping` |
| QQ | `1449917271` |
| 官网 | `https://codingchangeworld.com` |

---

> 生成时间：2026-08-21 | 来源：`复盘与导出工具vip台式_全能.exe` (v62.1, 28MB) | 共计 150+ API 端点，30+ 域名