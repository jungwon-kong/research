import json, urllib.request, urllib.parse, datetime, hashlib, xml.etree.ElementTree as ET, time, os
from pathlib import Path
from zoneinfo import ZoneInfo
p=Path('data/items.json'); rows=json.loads(p.read_text()); seen={r['id'] for r in rows}; today=datetime.datetime.now(ZoneInfo('Asia/Seoul')).date(); since=today-datetime.timedelta(days=30)
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ResearchObservatory/1.0'}),timeout=35) as r:return r.read()
def add(r):
    r['id']=hashlib.sha256(r['url'].lower().encode()).hexdigest(); r['collected']=str(today)
    if r['id'] in seen:return False
    seen.add(r['id']);rows.append(r);return True
for category,query in [('음악 연구','music industry music psychology music creativity'),('창의성 연구','creativity creative thinking innovation psychology')]:
    try:
        params={'query.bibliographic':query,'filter':f'from-pub-date:{since},type:journal-article','rows':50,'sort':'relevance'}
        items=json.loads(get('https://api.crossref.org/works?'+urllib.parse.urlencode(params)))['message']['items']; n=0
        for x in items:
            if not x.get('title') or not x.get('DOI'):continue
            date=x.get('published',{}).get('date-parts',[[]])[0]; abstract=x.get('abstract',''); import re
            r=dict(category=category,title=x['title'][0],url='https://doi.org/'+x['DOI'].lower(),source=(x.get('container-title') or [''])[0],authors=', '.join(' '.join([a.get('given',''),a.get('family','')]).strip() for a in x.get('author',[])),date='-'.join(str(v).zfill(2) for v in date),abstract=re.sub('<[^>]+>',' ',abstract),quartile='Q1 미검증')
            if add(r):n+=1
            if n>=3:break
        print(category,n)
    except Exception as e:print(category,e)
for category,query,lang,country in [('국내 문화예술 정책','문화예술 정책 OR 문화체육관광부 when:7d','ko','KR'),('해외 문화예술 정책','cultural policy OR arts funding OR creative industries policy when:7d','en','US')]:
    try:
        url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':lang,'gl':country,'ceid':country+':'+lang}); n=0
        for x in ET.fromstring(get(url)).findall('./channel/item'):
            link=x.findtext('link'); title=x.findtext('title'); source=x.findtext('source') or ''; date=x.findtext('pubDate') or ''
            if link and title and add(dict(category=category,title=title,url=link,source=source,date=date,abstract='',authors='',quartile='')):n+=1
            if n>=3:break
        print(category,n)
    except Exception as e:print(category,e)
rows.sort(key=lambda r:r['collected'],reverse=True);p.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
