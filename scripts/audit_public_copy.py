#!/usr/bin/env python3
"""Inventory public page copy and metadata; lengths are observations, not ranking scores."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from xml.etree import ElementTree
from bs4 import BeautifulSoup

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base',default='http://127.0.0.1:3098')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
base=args.base.rstrip('/')
with urlopen(base+'/sitemap.xml',timeout=20) as response:
    sitemap=ElementTree.fromstring(response.read())
urls=[node.text for node in sitemap.iter() if node.tag.endswith('}loc')]

def inspect(url):
    path=urlparse(url).path or '/'
    with urlopen(base+path,timeout=20) as response:
        soup=BeautifulSoup(response.read().decode('utf-8'),'html.parser')
        status=response.status
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    description=soup.find('meta',attrs={'name':'description'})
    description=description.get('content','') if description else ''
    canonical=soup.find('link',attrs={'rel':'canonical'})
    h1=[node.get_text(' ',strip=True) for node in soup.find_all('h1')]
    for node in soup.select('script,style,nav,header,footer'):node.decompose()
    main=soup.find('main') or soup
    return {'url':url,'status':status,'title':title,'titleChars':len(title),'description':description,'descriptionChars':len(description),'h1':h1,'canonical':canonical.get('href') if canonical else None,'mainWords':len(main.get_text(' ',strip=True).split()),'headings':[node.get_text(' ',strip=True) for node in main.find_all(['h2','h3'])]}

with ThreadPoolExecutor(max_workers=4) as pool:
    rows=list(pool.map(inspect,urls))
def duplicates(field):
    grouped=defaultdict(list)
    for row in rows:grouped[row[field].strip().lower()].append(row['url'])
    return [{'value':value,'urls':paths} for value,paths in grouped.items() if len(paths)>1 and value]
failures=[row['url'] for row in rows if row['status']!=200 or not row['title'] or not row['description'] or len(row['h1'])!=1 or (row['canonical'] or '').rstrip('/')!=row['url'].rstrip('/')]
report={'status':'failed' if failures else 'passed','pages':len(rows),'basicMetadataFailures':failures,'duplicateTitles':duplicates('title'),'duplicateDescriptions':duplicates('description'),'pagesWithShortDescription':[row['url'] for row in rows if len(row['description'])<70],'notes':'All indexable sitemap pages inventoried. Content quality reviewed separately by specialists; word counts and character lengths are not ranking factors or target scores.','results':rows}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({key:value for key,value in report.items() if key!='results'},ensure_ascii=False))
assert not failures,failures
