# -*- coding: utf-8 -*-
"""第三轮探测: 人气榜/题材投资/智能选股/开盘啦/同花顺热榜"""
import urllib.request
import urllib.parse
import json

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Referer": "https://guba.eastmoney.com/",
}
UA_LHV = dict(UA)
UA_LHV["Referer"] = "https://www.longhuvip.com/"
UA_THS = dict(UA)
UA_THS["Referer"] = "https://eq.10jqka.com.cn/"


def t(name, url, headers=None, show=160, post=None):
    try:
        r = urllib.request.Request(url, headers=headers or UA,
                                   data=urllib.parse.urlencode(post).encode() if post else None,
                                   method="POST" if post else "GET")
        d = urllib.request.urlopen(r, timeout=8).read()
        txt = d.decode("utf-8", "ignore").replace("\n", " ")
        print(name, "OK", len(d), txt[:show])
    except Exception as e:
        print(name, "FAIL", str(e)[:110])


# 东财人气榜 v2 (带固定 appId/globalId)
t("EM.rank_current", "https://emappdata.eastmoney.com/stockrank/getCurrentList?appId=appId01&globalId=786e4c21-70dc-435a-93bb-38cb5f6e3a38&marketType=&pageNo=1&pageSize=20")
t("EM.rank_his", "https://emappdata.eastmoney.com/stockrank/getHisList?appId=appId01&globalId=786e4c21-70dc-435a-93bb-38cb5f6e3a38&marketType=&pageNo=1&pageSize=20")
# 东财题材投资(带参数)
t("EM.theme", "https://emcfgdata.eastmoney.com/api/themeInvest/getThemeList?date=20260821")
t("EM.theme2", "https://emcfgdata.eastmoney.com/api/themeInvest/getTodayChance")
# 东财涨停原因 push2ex 已确认可用, 试昨日涨停今日表现(龙头晋级)
t("EM.yzt", "https://push2ex.eastmoney.com/getYesterdayZTPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=20&sort=zsdb%3Adesc&date=20260821")
t("EM.zrzt", "https://push2ex.eastmoney.com/getYesterdayZTPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=10&sort=fbt%3Aasc&date=20260820")
# 同花顺热榜
t("THS.hot_stock", "https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_stock/a/hour/data.txt", UA_THS)
t("THS.hot_plate", "https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_plate/concept/data.txt", UA_THS)
# 开盘啦
t("KPL.zt", "https://www.kaipanla.com/api/v1/ztlist?start=0&limit=10", UA_THS)
t("KPL.home", "https://www.kaipanla.com/api/v1/home/zt", UA_THS)
t("KPL.hiszt", "https://apphis.kaipanla.com/w1/api/index.php?a=GetDayZhangTing&st=10&c=HisLimitResumption&PhoneOSNew=1&Index=0&apiv=w43&StockID=002230", UA_LHV)
# 东财智能选股 POST
t("EM.smart_post", "https://np-tjxg-b.eastmoney.com/api/smart-tag/stock/v3/pw/search-code",
  post={"keyword": "涨停"})
# 龙虎VIP 今日题材
t("LHV.TopicDetail", "https://applhb.longhuvip.com/w1/api/index.php?a=InfoGet&c=Topic&PhoneOSNew=1&ID=2380", UA_LHV)
# 东财涨停炸板原因
t("EM.zbpool", "https://push2ex.eastmoney.com/getTopicZBPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=5&sort=fbt%3Aasc&date=20260821")
