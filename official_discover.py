"""Conservative official-page monitoring, not verification of open tenders.
No authenticated access or bulk crawl. Use homepage links as leads only.
"""
import datetime as dt
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import socket
import urllib.parse as up
import urllib.request as ur

ROOT=Path(__file__).resolve().parent
LIMIT=1_500_000
KEYWORDS=re.compile(r'\b(?:tender|procurement|request for (?:quotation|proposal)|invitation to bid|RFQ|RFP|ITB|bid notice)\b|مناقص[ةات]|توريد|استدراج عروض|طلب عروض',re.I)
SYRIA=re.compile(r'syria|syrian|سوريا|سورية|دمشق|حلب|حمص|إدلب|درعا|اللاذقية|طرطوس|الحسكة|دير الزور',re.I)
class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.href=None;self.bits=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a': self.href=dict(attrs).get('href');self.bits=[]
    def handle_data(self, data):
        if self.href is not None:self.bits.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href is not None:
            self.links.append((self.href,' '.join(''.join(self.bits).split())))
            self.href=None;self.bits=[]
class NoRedirect(ur.HTTPRedirectHandler):
    def redirect_request(self,*args):return None

def safe_host(host):
    if not host:return False
    try:
        addr=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
        return bool(addr) and all(ipaddress.ip_address(a[4][0]).is_global for a in addr)
    except (OSError,ValueError):return False

def https_url(url):
    try:
        s=up.urlsplit(url)
        return s.scheme=='https' and not s.username and not s.password and safe_host(s.hostname)
    except ValueError:return False

def run():
    raw=json.loads((ROOT/'official_sources.json').read_text(encoding='utf-8'))
    leads={};statuses=[]; opener=ur.build_opener(NoRedirect)
    for src in raw:
        if not src.get('enabled'):continue
        url=src.get('url',''); state={'name':src.get('name',''),'url':url,'status':'skipped','links_checked':0,'candidates':0}
        try:
            if not https_url(url):raise ValueError('URL is not public HTTPS')
            request=ur.Request(url,headers={'User-Agent':'NewBuildTenderMonitor/1.0 (public-page audit)'})
            with opener.open(request,timeout=20) as r:
                if r.status!=200:raise ValueError('HTTP '+str(r.status))
                if 'html' not in r.headers.get('Content-Type','').lower():raise ValueError('non-HTML response')
                page=r.read(LIMIT+1)
            if len(page)>LIMIT:raise ValueError('page too large')
            parser=Links();parser.feed(page.decode('utf-8','replace'))
            state['links_checked']=len(parser.links)
            for href,title in parser.links:
                dest=up.urljoin(url,href)
                parts=up.urlsplit(dest)
                if parts.scheme!='https' or not parts.hostname or not title:continue
                # Both conditions required to avoid classifying general pages as Syria tenders.
                if not KEYWORDS.search(title+' '+parts.path) or not SYRIA.search(title+' '+parts.path):continue
                link=up.urlunsplit((parts.scheme,parts.netloc,parts.path,parts.query,''))
                if link not in leads:
                    leads[link]={'title':title[:250],'url':link,'source':src.get('name',''),'issuer':src.get('agency',''),'status':'candidate_only','verified':False,'deadline':None}
                state['candidates']+=1
            state['status']='checked'
        except Exception as exc:
            state['status']='error';state['error']=str(exc)[:160]
        statuses.append(state)
    # Static HTML can under-report JS-generated listings. Never mark full coverage.
    (ROOT/'official_candidates.json').write_text(json.dumps(list(leads.values()),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    status={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'sources_configured':len(raw),'sources_checked':sum(x['status']=='checked' for x in statuses),'source_errors':sum(x['status']=='error' for x in statuses),'unverified_candidates':len(leads),'directory_total_expected':281,'organizations_individually_monitored':0,'full_coverage_verified':False,'sources':statuses}
    (ROOT/'official_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'sources_checked':status['sources_checked'],'candidates':len(leads),'errors':status['source_errors']}))
if __name__=='__main__':run()
