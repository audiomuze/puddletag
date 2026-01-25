import inspect
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from . import parse_html
from puddlestuff.audioinfo import isempty, CaselessDict
from puddlestuff.constants import CHECKBOX
from puddlestuff.puddleobjects import ratio
from puddlestuff.tagsources import (write_log, set_status, RetrievalError,
                          urlopen, parse_searchstring, retrieve_cover, get_encoding, iri_to_uri,
                          get_useragent, set_useragent)

try:
    _URL_OPEN_SUPPORTS_HEADERS = 'headers' in inspect.signature(urlopen).parameters
except (AttributeError, TypeError, ValueError):
    _URL_OPEN_SUPPORTS_HEADERS = False

_HEADERS_FALLBACK_LOGGED = False


class OldURLError(RetrievalError):
    pass


ALBUM_ID = 'amg_album_id'

release_order = ('year', 'type', 'label', 'catalog')
search_adress = 'https://www.allmusic.com/search/albums/%s'
album_url = 'https://www.allmusic.com/album/'
ALLMUSIC_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 OPR/122.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 OPR/125.0.0.0",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) obsidian/1.8.4 Chrome/130.0.6723.191 Electron/33.3.2 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/29.0 Chrome/136.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 26_1_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/143.0.7499.151 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 15; F-52E Build/V34RD51A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/143.0.7499.115 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.81 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.5249.119 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) obsidian/1.10.6 Chrome/138.0.7204.251 Electron/37.10.2 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 26_2_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/143.0.7499.151 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Cursor/2.2.44 Chrome/138.0.7204.251 Electron/37.7.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) TikTokLIVEStudio/1.12.0 Chrome/136.0.7103.59 Electron/36.4.0-rs.18.release.ls.26 TTElectron/36.4.0-rs.18.release.ls.26 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0.1 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 YaBrowser/25.12.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win32; x86) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/143.0.7499.151 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 OPR/125.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/143.0.7499.151 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]


class _AllMusicUserAgent:
    """Temporarily override puddletag's User-Agent with a random browser."""

    def __enter__(self):
        self.previous = get_useragent()
        self.current = random.choice(ALLMUSIC_USER_AGENTS)
        set_useragent(self.current)
        return self.current

    def __exit__(self, exc_type, exc, tb):
        set_useragent(self.previous)
        return False

spanmap = CaselessDict({
    'Genre': 'genre',
    'Styles': 'style',
    'Style': 'style',
    'Themes': 'theme',
    'Moods': 'mood',
    'Release Date': 'year',
    'Recording Date': 'recording_date',
    'Recording Location': 'recordinglocation',
    'Label': 'label',
    'Album': 'album',
    'Artist': 'artist',
    'Featured Artist': 'artist',
    'Performer': 'performer',
    'Title': 'title',
    'Composer': 'composer',
    'Time': '__length',
    'duration': '__length',
    'Type': 'type',
    'Year': 'year',
    'Performance': 'performance',
    'Sound': 'sound',
    'Rating': 'rating',
    'AMG Album ID': ALBUM_ID,
    'Performed By': 'performer',
    'sample': None,
    'stream': None,
    'title-artist': 'artist',
    'AMG Pop ID': 'amg_pop_id',
    'Rovi Music ID': 'amg_rovi_id',
    'tracknum': 'track',
    'AMG Classical ID': 'amg_classical_id',
    'catalog #': 'catalog',
    'release info': 'release_info',
    'primary': 'composer',
})

sqlre = re.compile(r'(r\d+)$')
gallery_re = re.compile(r'var\s+imageGallery\s*=\s*(\[[^\]]+\])', re.S)
album_id_re = re.compile(r'-(m[wr][0-9a-z]+)$', re.I)

first_white = lambda match: match.groups()[0][0]


def find_id(tracks, field=None):
    for track in tracks:
        if field in track:
            value = track[field]
            if isinstance(value, str):
                return value.replace(' ', '').lower()
            else:
                return value[0].replace(' ', '').lower()


white_replace = lambda match: match.group()[0]


def convert(value):
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    text = value.strip()
    text = re.sub(r'\s{2,}', white_replace, text)
    return text


def element_text(element):
    if element is None:
        return ''
    text = element.string
    if text:
        return convert(text)
    return convert(element.all_recursive_text())


def extract_canonical_url(album_soup):
    canonical = album_soup.find('link', {'rel': 'canonical'})
    if canonical is None:
        return None
    href = canonical.element.attrib.get('href')
    if href:
        return iri_to_uri(href)
    return None


def extract_linked_text(block):
    if block is None:
        return ''
    anchors = block.find_all('a')
    if anchors:
        parts = [element_text(anchor) for anchor in anchors]
        parts = [part for part in parts if part]
        if parts:
            return '\\\\\\'.join(parts)
    return element_text(block)


def decode_data_attribute(value):
    if not value:
        return ''
    return convert(urllib.parse.unquote_plus(value))


def decode_page(page):
    if isinstance(page, bytes):
        return page.decode('utf-8', 'ignore')
    return page


def extract_album_id_from_url(url):
    if not url:
        return None
    match = album_id_re.search(url)
    if match:
        return match.group(1).lower()
    return None


def convert_year(info):
    if 'release date' not in info:
        return {}

    info['year'] = info['release date']
    del (info['release date'])

    if not isinstance(info['year'], str):
        info['year'] = info['year'][0]
    info['year'] = info['year'].strip()

    formats = [
        ('%B %d, %Y', '%Y-%m-%d'),
        ('%B %d %Y', '%Y-%m-%d'),
        ('%b %d, %Y', '%Y-%m-%d'),
        ('%b %d %Y', '%Y-%m-%d'),
        ('%B %Y', '%Y-%m'),
        ('%B, %Y', '%Y-%m'),
        ('%b %Y', '%Y-%m'),
        ('%Y', '%Y'),
    ]

    for fmt, output_fmt in formats:
        try:
            year = time.strptime(info['year'], fmt)
            return {'year': time.strftime(output_fmt, year)}
        except ValueError:
            continue

    return {'year': info['year']}


def create_search(terms):
    terms = re.sub('[%]', '', terms.strip())
    return search_adress % urllib.parse.quote(re.sub(r'(\s+)', ' ',
                                                     terms))


def equal(audio1, audio2, play=False, tags=('artist', 'album')):
    for key in tags:
        if (key in audio1) and (key in audio2):
            if ratio(''.join(audio1[key]), ''.join(audio2[key])) < 0.5:
                return False
        else:
            return False
    if play and ('#play' not in audio2):
        return False
    return True


def parse_cover(soup):
    cover_html = soup.find('img', src=re.compile('http://image.allmusic.com/'))
    try:
        cover_url = cover_html.element.attrib['src']
    except AttributeError:
        return {}
    return {'#cover-url': cover_url}


def parse_rating(dd):
    dd.find('span', {'class': "hidden", 'itemprop': "rating"})
    return convert(dd.string)


def parse_review(content):
    reviewer = content.find('h4', {'class': 'review-author headline'})
    if reviewer:
        author = convert(reviewer.string)
        text_section = content.find('div', {'class': 'text'})
        paragraphs = []
        if text_section is not None and text_section.find('p') is not None:
            paragraphs.append(element_text(text_section.find('p')))
        else:
            paragraphs = [element_text(p) for p in content.find_all('p')]
        paragraphs = [p for p in paragraphs if p]
        if paragraphs:
            text = '\n\n'.join(paragraphs)
            return {'review': author + '\n\n' + text}
        return {}

    heading = content.find('h3')
    paragraphs = [element_text(p) for p in content.find_all('p')]
    if not any(paragraphs):
        text_section = content.find('div', {'class': 'text'})
        if text_section is not None:
            paragraphs = [element_text(text_section)]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return {}

    text = '\n\n'.join(paragraphs)
    author = None
    if heading is not None:
        heading_text = element_text(heading)
        match = re.search(r'\bby\s+(.+)', heading_text, re.IGNORECASE)
        if match:
            author = match.group(1).strip()

    if author:
        return {'review': author + '\n\n' + text}
    return {'review': text}


def parse_similar(swipe):
    ret = []
    try:
        similar = swipe.find('ul', {'class': "swipe-gallery-pages"})
    except AttributeError:
        return {}
    for div in similar.find_all('div', {'class': "thumbnail lg album"}):
        try:
            title = div.a.element.attrib['title']
        except KeyError:
            title = div.a.element.attrib['oldtitle']

        url = '; http://www.allmusic.com' + div.a.element.attrib['href']
        ret.append(title.replace(' - ', '; ', 1) + url)

    if ret:
        return {'similar_albums': ret}
    return {}


def parse_albumpage(page, artist=None, album=None, album_url=None):
    album_soup = parse_html.SoupWrapper(parse_html.parse(page))

    if album_soup.find('div', {'id': 'albumHeadline'}):
        return parse_modern_albumpage(page, album_soup, artist, album, album_url)

    info = {}

    album = album_soup.find('h1', {'class': 'album-title'})
    artist = album_soup.find('h2', {'class': 'album-artist'})
    release_title = album_soup.find('h3', 'release-title')

    if release_title:
        album = release_title
        details = album_soup.find('p', {'class': 'release-details'})
        if details:
            info['release'] = convert(details.string)

    if not artist:
        artist = album_soup.find('h3', 'release-artist')

    if album is None:
        info.update({'artist': convert(artist.string), 'album': ''})
    else:
        info.update({'artist': convert(artist.string), 'album': convert(album.string)})
    info['albumartist'] = info['artist']

    sidebar = album_soup.find('div', {'class': 'sidebar'})
    info.update(parse_sidebar(sidebar))
    info.update(convert_year(info))

    content = album_soup.find('section', {'class': 'review read-more'})
    if content:
        info.update(parse_review(content))

    # swipe = main.find('div', {'id':"similar-albums", 'class':"grid-gallery"})

    # info.update(parse_similar(swipe))

    info = dict((spanmap.get(k, k), v) for k, v in info.items() if not isempty(v))

    canonical = extract_canonical_url(album_soup)
    if canonical:
        info['#canonical-url'] = canonical

    return [info, parse_tracks(album_soup, info)]


def parse_sidebar_element(element):
    try:
        title = convert(element.find('h4').string.lower())
    except AttributeError:
        return {}

    if element.find('span'):
        values = [convert(element.find('span').string)]
    elif element.find('div'):
        anchors = element.find_all('a')
        values = []
        if anchors:
            values = [convert(anchor.string) for anchor in anchors]
            values = [value for value in values if value and value.lower() not in ('see more', 'see all')]
        if not values:
            values = []
            for div in element.find_all('div'):
                text = div.string or getattr(div, 'text', None)
                if text:
                    values.append(convert(text))
            if not values:
                div = element.find('div')
                if div and div.string:
                    values = [convert(div.string)]
    elif element.find('ul'):
        values = [convert(z.string) for z in element.ul.find_all('li')]
    else:
        return {}
    return {title: values}


def parse_metadata_ids(element):
    data = {}
    key = None
    for child in element.contents:
        if child.element.attrib.get('class') == 'id-type':
            key = convert(child.string)
        elif key:
            data[key] = [convert(child.string)]
            key = None
    return data


def parse_sidebar(sidebar):
    info = {}

    container = sidebar.find('div', {'class': 'album-contain'})
    if container is None:
        container = sidebar.find('div', {'class': 'release-cover-contain'})
    cover = container.find('img')
    if cover is not None:
        try:
            cover_url = json.loads(cover.element.attrib['data-lightbox'])['url']
        except KeyError:
            try:
                cover_url = cover.element.attrib['src']
                if cover.element.attrib.get('class') == 'no-image':
                    cover_url = None
            except (AttributeError, KeyError):
                cover_url = None

        if cover_url:
            cover_url = cover_url.replace('?partner=allrovi.com', '')
            if cover_url.startswith('/'):
                cover_url = 'http://www.allmusic.com' + cover_url
            info['#cover-url'] = cover_url

    basic_info = sidebar.find('section', {'class': 'basic-info'})
    invalids = set(['affiliates', 'advertising medium-rectangle', 'partner-buttons'])
    for div in basic_info.find_all('div'):
        class_name = div.element.attrib.get('class')
        if class_name in invalids: continue
        if class_name == 'metadata-ids':
            info.update(parse_metadata_ids(div))
        elif class_name:
            info.update(parse_sidebar_element(div))

    moods = sidebar.find('section', {'class': 'moods'})
    if moods is not None:
        info['mood'] = [convert(z.string) for z in
                        moods.find_all('span', {'class': 'mood'})]

    themes = sidebar.find('section', {'class': 'themes'})
    if themes is not None:
        info['theme'] = [convert(z.string) for z in
                         themes.find_all('span', {'class': 'theme'})]

    return info


def parse_basic_info_meta(album_soup):
    info = {}
    basic_info = album_soup.find('div', {'id': 'basicInfoMeta'})
    if basic_info is None:
        return info

    for section in basic_info.element:
        try:
            tag = section.tag
        except AttributeError:
            continue
        if not isinstance(tag, str):
            continue
        wrapper = parse_html.SoupWrapper(section)
        if not wrapper.find('h4'):
            continue
        info.update(parse_sidebar_element(wrapper))
    return info


def extract_gallery_cover(page):
    html_text = decode_page(page)
    match = gallery_re.search(html_text)
    if not match:
        return None
    try:
        images = json.loads(match.group(1))
    except (ValueError, TypeError):
        return None
    for image in images:
        url = image.get('zoomURL') or image.get('url')
        if url:
            if url.startswith('//'):
                url = 'https:' + url
            return url
    return None


def parse_modern_cover(album_soup, page):
    cover_url = extract_gallery_cover(page)
    if not cover_url:
        image = album_soup.find('img', {'id': 'posterImage'})
        if image is not None:
            cover_url = (image.element.attrib.get('data-src') or
                         image.element.attrib.get('src'))
    if cover_url and cover_url.startswith('//'):
        cover_url = 'https:' + cover_url
    if cover_url:
        return {'#cover-url': cover_url}
    return {}


def _normalize_album_url(album_url):
    if not album_url:
        return None
    normalized = album_url.split('#', 1)[0].strip()
    if normalized.endswith('/'):
        normalized = normalized[:-1]
    return normalized or album_url


def _manual_urlopen_with_headers(url, headers=None):
    request = urllib.request.Request(url)
    headers = headers or {}
    normalized = {key.lower(): value for key, value in headers.items() if value}
    user_agent = get_useragent()
    if user_agent and 'user-agent' not in normalized:
        request.add_header('User-Agent', user_agent)
    for header, value in headers.items():
        if value is None:
            continue
        request.add_header(header, value)
    try:
        with urllib.request.build_opener().open(request) as response:
            return response.read()
    except urllib.error.URLError as exc:
        raise RetrievalError(str(exc))


def fetch_tracklisting_soup(album_url):
    global _URL_OPEN_SUPPORTS_HEADERS, _HEADERS_FALLBACK_LOGGED
    normalized = _normalize_album_url(album_url)
    if not normalized:
        return None
    ajax_url = iri_to_uri(f"{normalized}/trackListingAjax")
    headers = {'Referer': iri_to_uri(normalized)}
    write_log(f"Fetching track listing via AJAX - {ajax_url}")
    if _URL_OPEN_SUPPORTS_HEADERS:
        try:
            track_page = urlopen(ajax_url, headers=headers)
        except TypeError as exc:
            message = str(exc)
            if 'headers' not in message:
                raise
            _URL_OPEN_SUPPORTS_HEADERS = False
            if not _HEADERS_FALLBACK_LOGGED:
                write_log("tagsources.urlopen() does not accept headers; falling back to manual request.")
                _HEADERS_FALLBACK_LOGGED = True
            try:
                track_page = _manual_urlopen_with_headers(ajax_url, headers=headers)
            except RetrievalError as exc:
                write_log(f"Track listing fallback fetch failed: {exc}")
                return None
        except RetrievalError as exc:
            write_log(f"Track listing AJAX fetch failed: {exc}")
            return None
    else:
        if not _HEADERS_FALLBACK_LOGGED:
            write_log("tagsources.urlopen() does not accept headers; falling back to manual request.")
            _HEADERS_FALLBACK_LOGGED = True
        try:
            track_page = _manual_urlopen_with_headers(ajax_url, headers=headers)
        except RetrievalError as exc:
            write_log(f"Track listing fallback fetch failed: {exc}")
            return None
    track_text = decode_page(track_page)
    # Tracklisting AJAX responses omit charset info, so decode explicitly.
    return parse_html.SoupWrapper(parse_html.parse(track_text))


def parse_modern_albumpage(page, album_soup, artist=None, album=None, album_url=None):
    info = {}

    title = album_soup.find('h1', {'id': 'albumTitle'})
    if title is not None:
        info['album'] = convert(title.string)
        album_id = title.element.attrib.get('data-albumid')
        if album_id:
            info[ALBUM_ID] = album_id.lower()
    elif album:
        info['album'] = album
    else:
        info['album'] = ''

    artist_block = album_soup.find('h2', {'id': 'albumArtists'})
    if artist_block is not None:
        info['artist'] = element_text(artist_block)
    elif artist:
        info['artist'] = artist
    if 'artist' in info:
        info['albumartist'] = info['artist']

    info.update(parse_basic_info_meta(album_soup))
    info.update(convert_year(info))

    cover_info = parse_modern_cover(album_soup, page)
    if cover_info:
        info.update(cover_info)

    canonical = extract_canonical_url(album_soup)
    if canonical:
        info['#canonical-url'] = canonical

    review_section = album_soup.find('div', {'id': 'review'})
    if review_section is None:
        review_section = album_soup.find('section', {'class': 'review read-more'})
    if review_section is not None:
        info.update(parse_review(review_section))

    info = dict((spanmap.get(k, k), v) for k, v in info.items() if not isempty(v))

    if 'artist' in info and 'albumartist' not in info:
        info['albumartist'] = info['artist']

    tracks = parse_tracks(album_soup, info)
    if not tracks:
        ajax_source = info.get('#canonical-url') or album_url
        ajax_soup = fetch_tracklisting_soup(ajax_source)
        if ajax_soup is not None:
            ajax_tracks = parse_tracks(ajax_soup, info)
            if ajax_tracks:
                tracks = ajax_tracks

    return [info, tracks]


def parse_search_element(entry, id_field=ALBUM_ID):
    """Parse a search-result entry and return normalized album info."""

    info_block = entry.find('div', {'class': 'info'})
    if info_block is None:
        info_block = entry

    title_block = info_block.find('div', {'class': 'title'})
    link = title_block.find('a') if title_block is not None else None
    if link is None:
        return {}

    url = link.element.attrib.get('href', '')
    if not url:
        return {}

    info = {
        'album': convert(link.string),
        '#albumurl': iri_to_uri(url),
        'amg_url': iri_to_uri(url),
    }

    artist_block = info_block.find('div', {'class': 'artist'})
    if artist_block is not None:
        info['artist'] = element_text(artist_block)

    year_block = info_block.find('div', {'class': 'year'})
    if year_block is not None:
        info['year'] = element_text(year_block)

    genre_block = info_block.find('div', {'class': 'genres'})
    if genre_block is not None:
        info['genre'] = element_text(genre_block)

    info['#extrainfo'] = [
        info['album'] + ' at AllMusic.com', info['#albumurl']]

    album_id = extract_album_id_from_url(info['#albumurl'])
    if album_id:
        info[id_field] = album_id

    return dict((k, v) for k, v in info.items() if not isempty(v))


def parse_searchpage(page, artist=None, album=None, id_field=ALBUM_ID):
    """Parses a search page and gets relevant info.


    Arguments:
    page -- html string with search page's html.
    artist -- artist to to check for in results. If found only results
              with that artist are returned.
    album -- album to check for in results. If found only results with
             with the album are returned.
    id_field -- key to use for the album id found.

    Return a tuple with the first element being == True if the list
    was truncated with only matching artist/albums.

    """
    soup = parse_html.SoupWrapper(parse_html.parse(page))
    results = []

    result_container = soup.find('div', {'id': 'resultsContainer'})
    if result_container is not None:
        results = result_container.find_all('div', {'class': 'album'})
    else:
        legacy = soup.find('ul', {'class': 'search-results'})
        if legacy is not None:
            results = legacy.find_all('div', {'class': 'info'})

    albums = [parse_search_element(result, id_field=id_field) for result in results]
    albums = [album_info for album_info in albums if album_info]
    if not albums:
        return []

    d = {}
    if artist and album:
        d = {'artist': artist, 'album': album}
        top = [album for album in albums if equal(d, album, True)]
    elif album:
        d = {'album': album}
        top = [album for album in albums if equal(d, album, True, ['album'])]
        if not top:
            top = [album for album in albums if
                   equal(d, album, False, ['album'])]
    elif artist:
        d = {'artist': artist}
        top = [album for album in albums if equal(d, album, True, ['artist'])]
        if not top:
            top = [album for album in albums if
                   equal(d, album, False, ['artist'])]
    else:
        top = []

    if top:
        return True, top
    return False, albums


def parse_track_table(table, discnum=None):

    def to_string(e):
        try:
            return convert(e.a.string)
        except AttributeError:
            return convert(e.string)

    header_items = table.thead.find('tr').find_all('th')
    headers = [th.element.attrib.get('class', convert(th.string))
               for th in header_items]

    fields = [spanmap.get(key, key) for key in headers]

    tracks = []
    performance_title = None
    for item in table.tbody.find_all('tr'):
        if item.element.attrib.get('class') == 'performance-title':
            performance_title = convert(item.string.strip())
            continue
        t = parse_track(item, fields, performance_title)
        tracks.append(t)
    return tracks


def parse_modern_disc(disc):
    track_divs = disc.find_all('div', {'class': re.compile(r'(?:^|\s)track(?:\s|$)')})
    tracks = []
    for track_div in track_divs:
        track_info = parse_modern_track(track_div)
        if track_info:
            tracks.append(track_info)
    return tracks


def parse_modern_track(track_div):
    track = {}

    number = track_div.find('div', {'class': 'trackNum'})
    if number is not None:
        track_number = element_text(number)
        if track_number:
            track['track'] = track_number

    title_block = track_div.find('div', {'class': 'title'})
    if title_block is not None:
        link = title_block.find('a')
        if link is not None and link.string:
            track['title'] = convert(link.string)
            href = link.element.attrib.get('href')
            if href:
                track['#trackurl'] = iri_to_uri(href)
        else:
            track['title'] = element_text(title_block)

    composer_block = track_div.find('div', {'class': 'composer'})
    if composer_block is not None:
        composer_text = extract_linked_text(composer_block)
        if composer_text:
            track['composer'] = composer_text

    performer_block = track_div.find('div', {'class': 'performer'})
    if performer_block is not None:
        performer_text = extract_linked_text(performer_block)
        if performer_text:
            track['performer'] = performer_text

    duration_block = track_div.find('div', {'class': 'duration'})
    if duration_block is not None:
        duration = element_text(duration_block)
        if duration:
            track['__length'] = duration

    favorite = track_div.find('button', {'class': 'songFavoriteIcon'})
    if favorite is not None:
        track_id = favorite.element.attrib.get('data-id')
        if track_id:
            track['amg_track_id'] = track_id.strip()
        if 'performer' not in track:
            performer_raw = favorite.element.attrib.get('data-artist')
            performer_text = decode_data_attribute(performer_raw)
            if performer_text:
                track['performer'] = performer_text
        if 'title' not in track:
            title_raw = favorite.element.attrib.get('data-title')
            title_text = decode_data_attribute(title_raw)
            if title_text:
                track['title'] = title_text

    if 'performer' in track:
        track['artist'] = track['performer']
        del track['performer']

    return dict((spanmap.get(k, k), v) for k, v in track.items() if spanmap.get(k, k) and not isempty(v))


def parse_track(tr, fields, performance_title=None):
    track = {}
    ignore = set(['pick-prefix', 'sample', 'stream', 'pick-suffix'])

    if tr.element.attrib.get('class') == 'perfomance-title':
        return convert(tr.string)

    for td, field in zip(tr.find_all('td'), fields):
        if field in ignore:
            continue
        elif field is None:
            field = td.element.attrib.get('class')
            if not field:
                continue

        sub_fields = td.find_all('div')
        if (sub_fields):
            for div in sub_fields:
                sub_field = div.element.attrib['class']
                if field == 'performer' and sub_field == 'primary':
                    sub_field = field
                elif field == 'performer' and sub_field != 'primary':
                    if sub_field == 'featuring':
                        track[field] = '%s %s' % (track.get(field, ''), convert(div.string))
                    else:
                        sub_field = 'composer'

                value = convert(div.string)
                track[sub_field] = value
        else:
            track[field] = convert(td.string)
    if performance_title and 'title' in track:
        track['title'] = performance_title + ': ' + track['title']
    if 'performer' in track:
        track['artist'] = track['performer']
        del track['performer']
    return dict((spanmap.get(k, k), v) for k, v in track.items() if spanmap.get(k, k) and not isempty(v))


def replace_feat(album_info, track_info):
    artist = None
    for key in ['albumartist', 'artist', 'performer', 'composer']:
        value = album_info.get(key, '').strip()
        if not value.startswith('feat:'):
            artist = album_info[key]
            break

    if artist is None:
        return

    for k, v in track_info.items():
        if isinstance(v, str) and v.strip().startswith('feat:'):
            track_info[k] = artist + ' ' + v.strip()

    if 'featuring' in track_info:
        del (track_info['featuring'])


def parse_tracks(content, album_info):
    discs = content.find_all('div', 'disc')
    if not discs:
        return []
    tracks = []
    total_discs = len(discs)
    for i, disc in enumerate(discs):
        disc_number = str(i + 1)
        disc_title = disc.find('h3')
        disc_subtitle = element_text(disc_title) if disc_title is not None else ''
        disc_info = {}
        if total_discs > 1:
            disc_info['discnumber'] = disc_number
        if disc_subtitle:
            disc_info['discsubtitle'] = disc_subtitle
        table = getattr(disc, 'table', None)
        if table is not None:
            disc_tracks = parse_track_table(table)
        else:
            disc_tracks = parse_modern_disc(disc)
        for track in disc_tracks:
            if disc_info:
                track.update(disc_info)
            replace_feat(album_info, track)

        tracks.extend(disc_tracks)
    return tracks


def retrieve_album(url, coverurl=None, id_field=ALBUM_ID):
    write_log('Opening Album Page - %s' % url)
    cover = None
    with _AllMusicUserAgent():
        album_page, code = urlopen(url, False, True)
        if album_page.find(b"featured new releases") >= 0:
            raise OldURLError("Old AMG URL used.")

        info, tracks = parse_albumpage(album_page, album_url=url)
        resolved_url = info.get('#canonical-url', url)
        info['#albumurl'] = resolved_url
        info['amg_url'] = resolved_url

        if 'album' in info:
            info['#extrainfo'] = [
                info['album'] + ' at AllMusic.com', info['#albumurl']]

        if coverurl:
            try:
                write_log('Retrieving Cover - %s' % info['#cover-url'])
                cover = retrieve_cover(info['#cover-url'])
            except KeyError:
                write_log('No cover found.')
                cover = None
            except urllib.error.URLError as e:
                write_log('Error: While retrieving cover %s - %s' %
                          (info['#cover-url'], str(e)))
                cover = None
    return info, tracks, cover


def search(album):
    search_url = create_search(album.replace('/', ' '))
    write_log('Search URL - %s' % search_url)
    with _AllMusicUserAgent():
        return urlopen(iri_to_uri(search_url))


def text(z):
    text = z.all_recursive_text().strip()
    return re.sub(r'(\s+)', first_white, text)


def to_file(data, name):
    if os.path.exists(name):
        return to_file(data, name + '_')

    f = open(name, 'w')
    f.write(data)
    f.close()


class AllMusic(object):
    name = 'AllMusic.com'
    tooltip = "Enter search parameters here. If empty, the selected files are used. <ul><li><b>artist;album</b> searches for a specific album/artist combination.</li> <li>To list the albums by an artist leave off the album part, but keep the semicolon (eg. <b>Ratatat;</b>). For a album only leave the artist part as in <b>;Resurrection.</li><li>By prefacing the search text with <b>:id</b> you can search for an albums using it's AllMusic sql id eg. <b>:id 10:nstlgr7nth</b> (extraneous spaces are discarded.)<li></ul>"
    group_by = ['album', 'artist']
    _candidate_threshold = 0.55

    def __init__(self):
        super(AllMusic, self).__init__()
        self._getcover = True
        self._useid = True
        self.preferences = [
            ['Retrieve Covers', CHECKBOX, True],
            ['Use AllMusic Album ID to retrieve albums:', CHECKBOX, self._useid],
        ]

    def keyword_search(self, text):
        if text.startswith(':id'):
            sql = text[len(':id'):].strip().replace(' ', '').lower()
            if sql.startswith('mr'):
                url = album_url + 'release/' + sql
            else:
                url = album_url + sql
            info, tracks, cover = retrieve_album(url, self._getcover)
            if cover:
                info.update(cover)
            return [(info, tracks)]
        else:
            try:
                params = parse_searchstring(text)
            except RetrievalError:
                return self.search(text, [''])
            artists = [params[0][0]]
            album = params[0][1]
            return self.search(album, artists)

    def search(self, album, artists):
        ret = []
        if len(artists) > 1:
            artist = 'Various Artists'
        else:
            if hasattr(artists, 'items'):
                artist = list(artists.keys())[0]
            else:
                artist = artists[0]

        if self._useid and hasattr(artists, 'values'):
            tracks = []
            [tracks.extend(z) for z in artists.values()]
            for field in ('amg_rovi_id', 'amg_pop_id', 'amgsqlid', 'amg_album_id',):
                album_id = find_id(tracks, field)
                if album_id:
                    break

            if not isempty(album_id):
                write_log('Found Album ID %s' % album_id)
                try:
                    return self.keyword_search(':id %s' % album_id)
                except OldURLError:
                    write_log("Invalid URL used. Doing normal search.")

        if not album:
            raise RetrievalError('Album name required.')

        write_log('Searching for %s' % album)
        try:
            searchpage = search(album)
        except urllib.error.URLError as e:
            write_log('Error: While retrieving search page %s' %
                      str(e))
            raise RetrievalError(str(e))
        write_log('Retrieved search results.')

        search_results = parse_searchpage(searchpage, artist, album)
        if search_results:
            matched, matches = search_results
        else:
            return []

        if matched and len(matches) == 1:
            ret = [(matches[0], [])]
        elif matched:
            write_log('Ambiguous matches found for: %s - %s' %
                      (artist, album))
            ret.extend([(z, []) for z in matches])
        else:
            write_log('No exact matches found for: %s - %s' %
                      (artist, album))
            filtered = self._filter_candidates(album, artist, matches)
            if not filtered:
                ret.extend([(z, []) for z in matches])
            else:
                ret.extend([(z, []) for z in filtered])
        return ret

    def _filter_candidates(self, album, artist, candidates):
        if not candidates:
            return []
        target_album = (album or '').strip().lower()
        target_artist = (artist or '').strip().lower()
        if not target_album and not target_artist:
            return candidates

        passed = []
        for info in candidates:
            album_score = ratio(target_album, info.get('album', '').lower()) \
                if target_album and 'album' in info else 0.0
            artist_score = ratio(target_artist, info.get('artist', '').lower()) \
                if target_artist and 'artist' in info else 0.0

            if target_album and target_artist:
                if album_score < self._candidate_threshold or \
                        artist_score < self._candidate_threshold:
                    continue
                score = (album_score + artist_score) / 2.0
            elif target_album:
                if album_score < self._candidate_threshold:
                    continue
                score = album_score
            else:
                if artist_score < self._candidate_threshold:
                    continue
                score = artist_score
            passed.append((score, info))

        passed = [info for score, info in passed]
        if passed and target_album:
            passed.sort(key=lambda info: ratio(target_album,
                                               info.get('album', '').lower()),
                        reverse=True)
        return passed

    def retrieve(self, albuminfo):
        try:
            artist = albuminfo['artist']
            album = albuminfo['album']
            set_status('Retrieving %s - %s' % (artist, album))
            write_log('Retrieving %s - %s' % (artist, album))
        except KeyError:
            set_status('Retrieving album.')
            write_log('Retrieving album.')
        write_log('Album URL - %s' % albuminfo['#albumurl'])
        url = albuminfo['#albumurl']
        try:
            if self._useid:
                info, tracks, cover = retrieve_album(url, self._getcover)
            else:
                info, tracks, cover = retrieve_album(url, self._getcover)
        except urllib.error.URLError as e:
            write_log('Error: While retrieving album URL %s - %s' %
                      (url, str(e)))
            raise RetrievalError(str(e))
        if cover:
            info.update(cover)
        albuminfo = albuminfo.copy()
        albuminfo.update(info)
        return albuminfo, tracks

    def applyPrefs(self, args):
        self._getcover = args[0]
        self._useid = args[1]


info = AllMusic

if __name__ == '__main__':
    f = get_encoding(open(sys.argv[1], 'r').read(), True)[1]
    x = parse_albumpage(f)
    print(x)
