# -*- coding: utf-8 -*-
import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

def t(name, path):
    try:
        r = urllib.request.urlopen('http://127.0.0.1:8765/api/' + path, timeout=25)
        d = json.loads(r.read().decode('utf-8'))
        s = json.dumps(d, ensure_ascii=False)
        print(name, 'OK len=%d' % len(s), s[:180].replace('\n', ' '))
    except Exception as e:
        print(name, 'FAIL', str(e)[:150])

t('indices', 'indices')
t('limit_up', 'limit_up')
t('xgb_broken', 'xgb_broken')
t('ladder', 'ladder')
t('hot_plate', 'hot_plate')
t('lhb', 'lhb')
t('bidding', 'bidding')
t('duishu', 'duishu&type=1&page=1&size=5')
t('market', 'market&sort=f3&page=1&size=5')
t('dates', 'dates')
