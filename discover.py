"""Read public Telegram preview pages as candidate notices; never assume verification."""
import datetime as dt
import html
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import socket
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parent
MAX_BYTES=1_500_000
KEYWORDS=re.compile(r'مناقصة|مناقصات|توريد|طلب عروض|استدراج عروض|عطاء|تأهيل|استدراج|tender|procurement|rfq|rfp|invitation to bid|quotation',re.I)
DATE_RE=re.compile(r'(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})|(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})(?!\d)')
DEADLINE_WORDS=re.compile(r'آخر موعد|اخر موعد|إغلاق|اغلاق|ينتهي|الموعد النهائي|نهاية التقديم|آخر يوم|deadline|closing date|submission deadline',re.I)
class TelegramParser(HTMLParser):
    def __init__(self):
        super().__init__();self.current=None;self.depth=0;self.records=[];self.capture=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);cls=a.get('class','')
        if tag=='div' and 'tgme_widget_message ' in (' '+cls+' ') and 'tgme_widget_message_wrap' not in cls:
            self.current={'text':'','url':'','date':''};self.depth=1;return
        if self.current is None:return
        if tag=='div':self.depth+=1
        if tag=='a' and 'tgme_widget_message_date' in cls:self.current['url']=a.get('href','')
        if tag=='time' and 'datetime' in a:self.current['date']=a['datetime']
        if tag=='div' and 'tgme_widget_message_text' in cls:self.capture=self.depth
        if tag=='br' and self.capture:self.current['text']+='\n'
    def handle_endtag(self,tag):
        if self.current is None:return
        if tag=='div':
            if self.capture==self.depth:self.capture=0
            self.depth-=1
            if self.depth==0:self.records.append(self.current);self.current=None
    def handle_data(self,data):
        if self.current is not None and self.capture:self.current['text']+=data

def public_telegram_url(u):
    try:
        parsed=urllib.parse.urlsplit(u)
        return parsed.scheme=='https' and parsed.hostname=='t.me' and re.fullmatch(r'/s/[A-Za-z0-9_]{4,64}',parsed.path) is not None and not parsed.query
    except ValueError:return False

def fetch(u):
    req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0 (compatible; NewBuildTenderDiscovery/1.0)'})
    with urllib.request.urlopen(req,timeout=25) as r:
        if urllib.parse.urlsplit(r.geturl()).hostname!='t.me':raise ValueError('Unexpected redirect')
        payload=r.read(MAX_BYTES+1)
    if len(payload)>MAX_BYTES:raise ValueError('Too large')
    return payload.decode('utf-8',errors='replace')

def deadline_candidate(text):
    # Only extract a date when close to an explicit deadline phrase.
    for m in DEADLINE_WORDS.finditer(text):
        segment=text[m.start():m.start()+125]
        found=DATE_RE.search(segment)
        if not found:continue
        if found.group(1):y,mo,d=map(int,found.group(1,2,3))
        else:d,mo,y=map(int,found.group(4,5,6))
        try:return dt.date(y,mo,d).isoformat()
        except ValueError:continue
    return ''

def main():
    try:sources=json.loads((ROOT/'discovery_sources.json').read_text('utf8'))
    except (OSError,ValueError):sources=[]
    existing={}
    try:
        for x in json.loads((ROOT/'candidates.json').read_text('utf8')):
            if isinstance(x,dict) and x.get('url'):existing[x['url']]=x
    except (OSError,ValueError):pass
    results=[];now=dt.datetime.now(dt.timezone.utc);errors=[]
    for src in sources:
        if not isinstance(src,dict) or src.get('enabled') is not True or src.get('type')!='telegram_public':continue
        url=src.get('url','')
        if not public_telegram_url(url):errors.append({'source':src.get('name',''),'error':'Invalid Telegram public URL'});continue
        try:
            parser=TelegramParser();parser.feed(fetch(url));found=0
            for post in parser.records:
                body=html.unescape(re.sub(r'\s+',' ',post['text'])).strip()
                if not body or not KEYWORDS.search(body):continue
                link=post['url'].split('?')[0]
                if not link.startswith('https://t.me/') or not re.search(r'/\d+$',link):continue
                due=deadline_candidate(body)
                if due and due < now.date().isoformat():continue
                prior=existing.get(link,{})
                results.append({'title':body[:160],'summary':body[:950],'source_name':src.get('name',''),'url':link,'published':post['date'],'deadline_unverified':due,'verification':'candidate_only','first_seen_utc':prior.get('first_seen_utc',now.isoformat())});found+=1
            errors.append({'source':src.get('name',''),'posts_parsed':len(parser.records),'relevant_candidates':found})
        except Exception as e:errors.append({'source':src.get('name',''),'error':type(e).__name__+': '+str(e)[:140]})
    # Retain previous candidates for 14 days, when first_seen is parseable.
    for link,item in existing.items():
        if any(x['url']==link for x in results):continue
        try:
            seen=dt.datetime.fromisoformat(item['first_seen_utc'])
            if (now-seen).days <=14: results.append(item)
        except (ValueError,KeyError,TypeError):pass
    results=sorted({x['url']:x for x in results}.values(),key=lambda x:x.get('published',''),reverse=True)[:500]
    (ROOT/'candidates.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    status={'last_attempt_utc':now.isoformat(),'candidate_count':len(results),'sources':errors,'warning':'These are unverified leads, not confirmed open tenders.'}
    (ROOT/'discovery_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(status,ensure_ascii=False))
if __name__=='__main__':main()
