"""Update verified HTTPS JSON feeds and manually curated CSV records; no scraping or shell commands."""
import csv
import datetime as dt
import ipaddress
import json
from pathlib import Path
import socket
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
NOW = dt.datetime.now(dt.timezone.utc)

def check_url(value):
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            return False
        # Prevent fetching local/private URLs, even if supplied in source config.
        for family, _, _, _, sockaddr in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(sockaddr[0])
            if not ip.is_global:
                return False
        return True
    except (ValueError, OSError):
        return False

def valid(record):
    if not isinstance(record, dict):
        return False
    if not all(str(record.get(x, '')).strip() for x in ['issuer', 'title', 'deadline', 'url']):
        return False
    if not str(record['url']).startswith('https://'):
        return False
    try:
        stamp = dt.datetime.fromisoformat(str(record['deadline']).replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=dt.timezone(dt.timedelta(hours=3)))
        return stamp.astimezone(dt.timezone.utc) > NOW and str(record.get('status', '')).lower() not in {'closed','cancelled','canceled'}
    except ValueError:
        return False

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError('Redirects disabled for configured sources')

records = []
for path in [ROOT / 'tenders.json']:
    try:
        data = json.loads(path.read_text('utf-8'))
        if isinstance(data, list): records.extend(data)
    except (OSError, ValueError): pass
try:
    with (ROOT / 'manual_tenders.csv').open(encoding='utf-8-sig', newline='') as f:
        records.extend(csv.DictReader(f))
except OSError: pass
try:
    sources = json.loads((ROOT / 'sources.json').read_text('utf-8'))
    if not isinstance(sources, list): sources = []
except (OSError, ValueError): sources = []

opener = urllib.request.build_opener(NoRedirect)
active_sources = 0
for src in sources:
    if not isinstance(src, dict) or src.get('enabled') is not True or src.get('type') != 'json':
        continue
    url = str(src.get('url', ''))
    if not check_url(url):
        print('Skipping invalid or private feed URL')
        continue
    active_sources += 1
    try:
        request = urllib.request.Request(url, headers={'User-Agent':'NewBuildTenderDashboard/2.0'})
        with opener.open(request, timeout=15) as response:
            if response.status != 200 or int(response.headers.get('Content-Length', '0')) > 2_000_000:
                raise ValueError('Feed exceeded size limit or failed')
            payload = response.read(2_000_001)
            if len(payload) > 2_000_000: raise ValueError('Feed too large')
            data = json.loads(payload)
            if isinstance(data, list): records.extend(data)
    except Exception as exc:
        print('Source skipped:', type(exc).__name__)

unique = {}
for item in records:
    if valid(item):
        key = (str(item['issuer']).strip().casefold(), str(item.get('reference') or item['title']).strip().casefold())
        unique[key] = item
result = sorted(unique.values(), key=lambda x: x['deadline'])
(ROOT/'tenders.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
(ROOT/'last_check.json').write_text(json.dumps({'last_check_utc':NOW.isoformat(),'verified_active_tenders':len(result),'automatic_sources_configured':active_sources},indent=2)+'\n',encoding='utf-8')
print('Active imported tenders:',len(result),'enabled JSON sources:',active_sources)
