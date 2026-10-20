import csv,json,datetime,re,pathlib,urllib.request
ROOT=pathlib.Path(__file__).parent
now=datetime.datetime.now(datetime.timezone.utc).date()
def valid(x):
    if not isinstance(x,dict):return False
    needed=('issuer','title','deadline','url')
    if not all(x.get(k) for k in needed) or not str(x['url']).startswith('https://'):return False
    try:return datetime.date.fromisoformat(str(x['deadline'])[:10])>=now
    except ValueError:return False
records=[]
p=ROOT/'tenders.json'
if p.exists():
    try:records+=json.loads(p.read_text(encoding='utf-8'))
    except (ValueError,TypeError):pass
p=ROOT/'manual_tenders.csv'
if p.exists():
    with p.open(encoding='utf-8-sig',newline='') as f:records+=list(csv.DictReader(f))
p=ROOT/'sources.json'
if p.exists():
    try:sources=json.loads(p.read_text(encoding='utf-8'))
    except ValueError:sources=[]
    for source in sources:
        if source.get('type')!='json' or not source.get('enabled',False):continue
        url=source.get('url','')
        if not url.startswith('https://'):continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'NewBuildTenderDashboard/1.0'}),timeout=15) as response:
                found=json.load(response)
            if isinstance(found,list):records.extend(found)
        except Exception as e:print('Source unavailable:',source.get('name',url),type(e).__name__)
dedup={}
for x in records:
    if valid(x):
        key=(str(x['issuer']).strip().casefold(),str(x.get('reference') or x['title']).strip().casefold())
        dedup[key]=x
out=sorted(dedup.values(),key=lambda x:x['deadline'])
(ROOT/'tenders.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'last_check.json').write_text(json.dumps({'last_check_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verified_active_tenders':len(out),'note':'No automatic discovery from Telegram/Facebook is configured.'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Active valid tenders:',len(out))
