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
    # Default to assuming header support; we'll detect lack of support at runtime.
    _URL_OPEN_SUPPORTS_HEADERS = True

_HEADERS_FALLBACK_LOGGED = False


class OldURLError(RetrievalError):
    pass


ALBUM_ID = 'amg_album_id'
RELEASE_ID = 'amg_release_id'

release_order = ('year', 'type', 'label', 'catalog')
search_adress = 'https://www.allmusic.com/search/albums/%s'
album_url = 'https://www.allmusic.com/album/'
ALLMUSIC_BASE = 'https://www.allmusic.com'
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
    'Release Date': 'releasedate',
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
            return '\\\\'.join(parts)
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


def _parse_date_string(date_str):
    """Parse a date string and return (full_date, year_only) tuple."""
    if not date_str:
        return None, None
    date_str = date_str.strip() if isinstance(date_str, str) else date_str[0].strip()
    
    formats = [
        ('%B %d, %Y', '%Y-%m-%d', '%Y'),
        ('%B %d %Y', '%Y-%m-%d', '%Y'),
        ('%b %d, %Y', '%Y-%m-%d', '%Y'),
        ('%b %d %Y', '%Y-%m-%d', '%Y'),
        ('%B %Y', '%Y-%m', '%Y'),
        ('%B, %Y', '%Y-%m', '%Y'),
        ('%b %Y', '%Y-%m', '%Y'),
        ('%Y', '%Y', '%Y'),
    ]
    
    for fmt, full_fmt, year_fmt in formats:
        try:
            parsed = time.strptime(date_str, fmt)
            return time.strftime(full_fmt, parsed), time.strftime(year_fmt, parsed)
        except ValueError:
            continue
    return date_str, None


def convert_year(info):
    """Convert release date to releasedate (full), date (year only), and year."""
    # Handle old 'release date' key for backwards compatibility
    if 'release date' in info:
        raw_date = info.pop('release date')
        full_date, year_only = _parse_date_string(raw_date)
        result = {}
        if full_date:
            result['releasedate'] = full_date
        if year_only:
            result['date'] = year_only
            result['year'] = year_only
        return result
    
    # Handle 'releasedate' if already mapped by spanmap
    if 'releasedate' in info:
        raw_date = info.get('releasedate')
        if isinstance(raw_date, list):
            raw_date = raw_date[0] if raw_date else None
        full_date, year_only = _parse_date_string(raw_date)
        result = {}
        if full_date:
            result['releasedate'] = full_date
        if year_only:
            result['date'] = year_only
            result['year'] = year_only
        return result
    
    return {}


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


def parse_rating(album_soup):
    """Extract AllMusic rating from 'ratingAllmusicN' class pattern."""
    rating_div = album_soup.find('div', {'class': re.compile(r'allmusicRating')})
    if rating_div is None:
        return {}
    class_attr = rating_div.element.attrib.get('class', '')
    match = re.search(r'ratingAllmusic(\d+)', class_attr)
    if match:
        rating = match.group(1)
        if rating == '0':
            return {}
        return {'amg_rating': rating}
    return {}


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

    if album_soup.find('div', {'id': 'releaseHeader'}):
        return parse_release_albumpage(page, album_soup, album_url=album_url)

    if album_soup.find('div', {'id': 'albumHeadline'}):
        return parse_modern_albumpage(page, album_soup, artist, album, album_url)

    info = {}

    def extract_artist_from_jsonld():
        release_headline = album_soup.find('div', {'id': 'releaseHeadline'})
        if release_headline is not None:
            headline_artist = release_headline.find('h2')
            if headline_artist is not None:
                anchor = headline_artist.find('a')
                if anchor is not None and anchor.string:
                    text = convert(anchor.string)
                    if text:
                        return text
                if headline_artist.string:
                    text = convert(headline_artist.string)
                    if text:
                        return text
        scripts = album_soup.find_all('script')
        for script in scripts:
            try:
                tag = script.element.tag
            except AttributeError:
                continue
            if tag != 'script':
                continue
            script_type = script.element.attrib.get('type', '')
            if script_type.lower() != 'application/ld+json':
                continue
            data = script.string or ''
            if not data.strip():
                continue
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            release_of = payload.get('releaseOf')
            if not isinstance(release_of, dict):
                continue
            by_artist = release_of.get('byArtist')
            if isinstance(by_artist, dict):
                candidates = [by_artist]
            elif isinstance(by_artist, list):
                candidates = [entry for entry in by_artist if isinstance(entry, dict)]
            else:
                continue
            for candidate in candidates:
                name = candidate.get('name')
                if isinstance(name, str) and name.strip():
                    return name.strip()
        return None

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
        artist_text = convert(artist.string) if artist is not None else None
        if artist_text is None:
            artist_text = extract_artist_from_jsonld()
        if artist_text:
            info.update({'artist': artist_text, 'album': ''})
        else:
            info.update({'album': ''})
    else:
        artist_text = convert(artist.string) if artist is not None else None
        if artist_text is None:
            artist_text = extract_artist_from_jsonld()
        if artist_text:
            info.update({'artist': artist_text, 'album': convert(album.string)})
        else:
            info.update({'album': convert(album.string)})
    if 'artist' in info:
        info['albumartist'] = info['artist']

    sidebar = album_soup.find('div', {'class': 'sidebar'})
    if sidebar is not None:
        info.update(parse_sidebar(sidebar))
    else:
        write_log('AllMusic: sidebar not found for legacy layout; continuing without sidebar metadata.')
    info.update(convert_year(info))

    content = _locate_review_section(album_soup)
    if content is None:
        ajax_soup = fetch_review_soup(album_url)
        content = _locate_review_section(ajax_soup)
    if content:
        info.update(parse_review(content))

    canonical = extract_canonical_url(album_soup)
    fallback_url = canonical or album_url
    _ensure_moods_themes(info, album_soup, fallback_url)
    _ensure_credits(info, album_soup, fallback_url)

    # swipe = main.find('div', {'id':"similar-albums", 'class':"grid-gallery"})

    # info.update(parse_similar(swipe))

    info = dict((spanmap.get(k, k), v) for k, v in info.items() if not isempty(v))

    if canonical:
        info['#canonical-url'] = canonical

    tracks = parse_tracks(album_soup, info)
    if not tracks and fallback_url:
        ajax_soup = fetch_tracklisting_soup(fallback_url)
        if ajax_soup is not None:
            ajax_tracks = parse_tracks(ajax_soup, info)
            if ajax_tracks:
                tracks = ajax_tracks
    if not tracks:
        write_log('AllMusic: No track listing found for this album; returning album-only metadata.')
        tracks = None

    return [info, tracks]


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
            seen = set()
            for div in element.find_all('div'):
                text = div.string or getattr(div, 'text', None)
                if text:
                    text_converted = convert(text)
                    if text_converted and text_converted not in seen:
                        values.append(text_converted)
                        seen.add(text_converted)
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


def _fetch_tab_soup(album_url, tab_suffix, log_label):
    global _URL_OPEN_SUPPORTS_HEADERS, _HEADERS_FALLBACK_LOGGED
    normalized = _normalize_album_url(album_url)
    if not normalized:
        return None
    ajax_url = iri_to_uri(f"{normalized}/{tab_suffix}")
    headers = {'Referer': iri_to_uri(normalized)}
    write_log(f"Fetching {log_label} via AJAX - {ajax_url}")
    log_title = log_label.capitalize()
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
                write_log(f"{log_title} fallback fetch failed: {exc}")
                return None
        except RetrievalError as exc:
            write_log(f"{log_title} AJAX fetch failed: {exc}")
            return None
    else:
        if not _HEADERS_FALLBACK_LOGGED:
            write_log("tagsources.urlopen() does not accept headers; falling back to manual request.")
            _HEADERS_FALLBACK_LOGGED = True
        try:
            track_page = _manual_urlopen_with_headers(ajax_url, headers=headers)
        except RetrievalError as exc:
            write_log(f"{log_title} fallback fetch failed: {exc}")
            return None
    track_text = decode_page(track_page)
    if isinstance(track_text, bytes):
        track_text = track_text.decode('utf-8', 'ignore')
    track_text = (track_text or '').strip()
    if not track_text:
        write_log(f"{log_title} AJAX response was empty; skipping {log_label}.")
        return None
    # AJAX responses omit charset info, so decode explicitly.
    try:
        parsed = parse_html.parse(track_text)
    except Exception as exc:
        write_log(f"{log_title} parse failed: {exc}")
        return None
    return parse_html.SoupWrapper(parsed)


def fetch_tracklisting_soup(album_url):
    return _fetch_tab_soup(album_url, 'trackListingAjax', 'track listing')


def fetch_review_soup(album_url):
    return _fetch_tab_soup(album_url, 'reviewAjax', 'review')


def _locate_review_section(soup):
    if soup is None:
        return None
    review_section = soup.find('div', {'id': 'review'})
    if review_section is not None:
        return review_section
    return soup.find('section', {'class': 'review read-more'})


def _fetch_track_review_text(track_url):
    normalized = _normalize_album_url(track_url)
    if not normalized:
        return None
    write_log(f"Fetching track review - {normalized}")
    review_section = None

    def _download_track_page(url):
        try:
            with _AllMusicUserAgent():
                page = urlopen(iri_to_uri(url))
        except (urllib.error.URLError, RetrievalError) as exc:
            write_log(f"Track review fetch failed: {exc}")
            return None
        review_text = decode_page(page)
        if isinstance(review_text, bytes):
            review_text = review_text.decode('utf-8', 'ignore')
        review_text = (review_text or '').strip()
        if not review_text:
            write_log("Track review response was empty; skipping track review.")
            return None
        try:
            return parse_html.SoupWrapper(parse_html.parse(review_text))
        except Exception as exc:
            write_log(f"Track review parse failed: {exc}")
            return None

    review_soup = _download_track_page(normalized)
    if review_soup is not None:
        review_section = _locate_review_section(review_soup)

    if review_section is None:
        ajax_soup = _fetch_tab_soup(normalized, 'reviewAjax', 'track review')
        if ajax_soup is not None:
            review_section = _locate_review_section(ajax_soup)

    if review_section is None:
        return None

    parsed = parse_review(review_section)
    review_text = parsed.get('review')
    if review_text:
        return review_text.strip()
    return None


def _populate_track_reviews(tracks):
    cache = {}
    for track in tracks:
        if not track.get('#has_review'):
            track.pop('#has_review', None)
            track.pop('#trackreviewurl', None)
            continue
        review_url = track.get('#trackreviewurl') or track.get('#trackurl')
        normalized = _normalize_album_url(review_url)
        if not normalized:
            continue
        if normalized not in cache:
            cache[normalized] = _fetch_track_review_text(normalized)
        review_text = cache.get(normalized)
        if review_text:
            track['track_review'] = review_text
            title = track.get('title') or track.get('track') or normalized
            write_log(
                "Stored track review for %s (%d chars)." %
                (title, len(review_text)))
        else:
            title = track.get('title') or track.get('track') or normalized
            write_log("No review text returned for %s." % title)
        track.pop('#has_review', None)
        track.pop('#trackreviewurl', None)


def fetch_moods_themes_soup(album_url):
    return _fetch_tab_soup(album_url, 'moodsThemesAjax', 'moods/themes')


def _fetch_main_album_info(main_album_url):
    """Fetch and parse the main album page to extract basic info fields."""
    if not main_album_url:
        return {}
    write_log("Fetching main album page for missing fields - %s" % main_album_url)
    try:
        with _AllMusicUserAgent():
            album_page, code = urlopen(main_album_url, False, True)
            album_page = decode_page(album_page)
            album_soup = parse_html.SoupWrapper(parse_html.parse(album_page))
            info = parse_basic_info_meta(album_soup)
            info.update(convert_year(info))
            info.update(parse_rating(album_soup))
            # Also capture the album title from the main album page
            title = album_soup.find('h1', {'id': 'albumTitle'})
            if title is not None and title.string:
                info['album'] = convert(title.string)
            return info
    except Exception as exc:
        write_log("Failed to fetch main album page: %s" % exc)
        return {}


# Fields to skip when saving 'original' versions from main album
_SKIP_ORIGINAL_FIELDS = frozenset(['duration', '__length', '#cover-url', '#canonical-url', 'date'])


def _normalize_value_for_compare(value):
    """Normalize a value for comparison (handles lists vs strings)."""
    if isinstance(value, list):
        return tuple(sorted(str(v).strip().lower() for v in value if v))
    if value is None:
        return ()
    return (str(value).strip().lower(),)


def _find_existing_key(info, target_lower):
    """Find the actual key in info dict matching target (case-insensitive)."""
    for key in info:
        if key.lower() == target_lower:
            return key
    return None


# Map of fields to their 'original' tag names (when values differ)
_ORIGINAL_FIELD_NAMES = {
    'releasedate': 'originaldate',
    'year': 'originalyear',
}


def _ensure_basic_info(info, main_album_url):
    """Ensure basic info fields are present, fetching from main album if needed.
    
    - Fields missing from release are filled in from main album
    - Fields present in both are kept from release, with main album's version
      saved as 'original<field>' only if the values differ
    """
    if not main_album_url:
        return
    main_info = _fetch_main_album_info(main_album_url)
    if not main_info:
        return
    existing_keys = {k.lower() for k in info.keys()}
    for field, value in main_info.items():
        if isempty(value):
            continue
        field_lower = field.lower()
        if field_lower.startswith('#') or field_lower in _SKIP_ORIGINAL_FIELDS:
            continue
        if field_lower in existing_keys:
            # Release has this field - check if values differ
            actual_key = _find_existing_key(info, field_lower)
            existing_value = info.get(actual_key) if actual_key else None
            # Compare normalized values
            if _normalize_value_for_compare(existing_value) != _normalize_value_for_compare(value):
                original_field = _ORIGINAL_FIELD_NAMES.get(field_lower, 'original' + field_lower)
                info[original_field] = value
                write_log("Saved main album '%s' as '%s'." % (field, original_field))
        else:
            # Release doesn't have this field - fill it in
            info[field] = value
            existing_keys.add(field_lower)
            write_log("Filled in '%s' from main album page." % field)


def _collect_mood_theme_values(container, node_id):
    if container is None:
        return []
    target = container.find('div', {'id': node_id})
    if target is None:
        target = container.find('div', {'class': node_id})
    if target is None:
        return []
    anchors = target.find_all('a')
    values = [element_text(anchor) for anchor in anchors]
    return [value for value in values if value]


def _extract_moods_themes(soup):
    if soup is None:
        return {}
    container = soup.find('div', {'id': 'moodsThemes'})
    if container is None:
        tab_content = soup.find('div', {'class': 'tabContent moodsThemes'})
        if tab_content is not None:
            nested = tab_content.find('div', {'id': 'moodsThemes'})
            container = nested or tab_content
    if container is None:
        return {}
    info = {}
    moods = _collect_mood_theme_values(container, 'moodsGrid')
    if moods:
        info['mood'] = moods
    themes = _collect_mood_theme_values(container, 'themesGrid')
    if themes:
        info['theme'] = themes
    return info


def _ensure_moods_themes(info, album_soup, *album_urls):
    additions = _extract_moods_themes(album_soup)
    if not additions:
        for candidate_url in album_urls:
            if not candidate_url:
                continue
            ajax_soup = fetch_moods_themes_soup(candidate_url)
            additions = _extract_moods_themes(ajax_soup)
            if additions:
                break
    if not additions:
        return
    for field, values in additions.items():
        if not values:
            continue
        existing = info.get(field)
        if existing:
            continue
        info[field] = values


def fetch_credits_soup(album_url):
    return _fetch_tab_soup(album_url, 'creditsAjax', 'credits')


def _extract_credit_table(soup):
    if soup is None:
        return None
    container = soup.find('div', {'id': 'credits'})
    if container is None:
        tab_content = soup.find('div', {'class': 'tabContent credits'})
        if tab_content is not None:
            nested = tab_content.find('div', {'id': 'credits'})
            container = nested or tab_content
    if container is None:
        return None
    table = container.find('table')
    if table is None:
        return None
    return table


def _split_roles(roles_text):
    if not roles_text:
        return []
    parts = [part.strip() for part in roles_text.split(',')]
    return [part for part in parts if part]


def _normalize_role_tag(role):
    if not role:
        return None
    cleaned = role.strip()
    if not cleaned:
        return None
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.lower()
    cleaned = re.sub(r'[^0-9a-z]+', '_', cleaned)
    cleaned = cleaned.strip('_')
    return cleaned or None


def _extract_credits(soup):
    table = _extract_credit_table(soup)
    if table is None:
        return []
    entries = []
    rows = table.find_all('tr')
    for row in rows:
        cell = row.find('td', {'class': 'singleCredit'})
        if cell is None:
            continue
        name_block = cell.find('span', {'class': 'artist'})
        name = element_text(name_block)
        artist_url = None
        if name_block is not None:
            anchor = name_block.find('a')
            if anchor is not None:
                href = anchor.element.attrib.get('href')
                if href:
                    if href.startswith('/'):
                        artist_url = ALLMUSIC_BASE + href
                    else:
                        artist_url = iri_to_uri(href)
        role_block = cell.find('span', {'class': 'artistCredits'})
        roles_text = element_text(role_block)
        if not name and not roles_text:
            continue
        entry_text = name if not roles_text else f"{name} - {roles_text}"
        entries.append({
            'entry': entry_text,
            'name': name or entry_text,
            'roles': _split_roles(roles_text),
            'artist_url': artist_url,
        })
    return entries


def _ensure_credits(info, album_soup, *album_urls):
    credits = _extract_credits(album_soup)
    if not credits:
        for candidate_url in album_urls:
            if not candidate_url:
                continue
            ajax_soup = fetch_credits_soup(candidate_url)
            credits = _extract_credits(ajax_soup)
            if credits:
                break
    if not credits:
        return

    artist_urls = []
    for entry in credits:
        link = entry.get('artist_url')
        if link and link not in artist_urls:
            artist_urls.append(link)
    if artist_urls:
        existing_urls = info.get('amg_artists')
        if not existing_urls:
            info['amg_artists'] = artist_urls
        else:
            if not isinstance(existing_urls, list):
                existing_urls = [existing_urls]
                info['amg_artists'] = existing_urls
            for link in artist_urls:
                if link not in existing_urls:
                    existing_urls.append(link)

    credit_pairs = []
    for entry in credits:
        roles = entry['roles'] or []
        primary_value = entry.get('name') or entry.get('entry')
        if not primary_value:
            continue
        for role in roles:
            tag = _normalize_role_tag(role)
            if tag is None:
                continue
            credit_pairs.append(f"{tag}={primary_value}")
    if credit_pairs:
        info['amg_credits'] = '\\\\'.join(credit_pairs)


def parse_release_albumpage(page, album_soup, album_url=None):
    info = {}

    release_headline = album_soup.find('div', {'id': 'releaseHeadline'})
    if release_headline is not None:
        title = release_headline.find('h1', {'id': 'releaseTitle'})
        if title is not None:
            info['album'] = convert(title.string)
            release_id = title.element.attrib.get('data-releaseid')
            if release_id:
                info[RELEASE_ID] = release_id.strip().lower()
        artist_block = release_headline.find('h2')
        artist_text = extract_linked_text(artist_block)
        if artist_text:
            info['artist'] = artist_text
            info['albumartist'] = artist_text
        detail_block = release_headline.find('h3')
        detail_text = element_text(detail_block)
        if detail_text:
            info['release'] = detail_text

    main_album_section = album_soup.find('div', {'id': 'mainAlbum'})
    if main_album_section is not None:
        anchor = main_album_section.find('a')
        if anchor is not None:
            href = anchor.element.attrib.get('href')
            if href:
                if href.startswith('/'):
                    full_url = ALLMUSIC_BASE + href
                else:
                    full_url = iri_to_uri(href)
                info['#main-album-url'] = full_url
                album_id = extract_album_id_from_url(href)
                if album_id:
                    info[ALBUM_ID] = album_id

    info.update(parse_basic_info_meta(album_soup))
    info.update(convert_year(info))

    cover_info = parse_modern_cover(album_soup, page)
    if cover_info:
        info.update(cover_info)

    info.update(parse_rating(album_soup))

    canonical = extract_canonical_url(album_soup)
    if canonical:
        info['#canonical-url'] = canonical

    fallback_urls = [info.get('#canonical-url') or album_url,
                     info.get('#main-album-url')]

    _ensure_basic_info(info, info.get('#main-album-url'))
    _ensure_moods_themes(info, album_soup, *fallback_urls)
    _ensure_credits(info, album_soup, *fallback_urls)

    review_section = _locate_review_section(album_soup)
    if review_section is None:
        for ajax_source in fallback_urls:
            if not ajax_source:
                continue
            ajax_soup = fetch_review_soup(ajax_source)
            review_section = _locate_review_section(ajax_soup)
            if review_section is not None:
                break
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
    if not tracks:
        write_log('AllMusic: No track listing found for this release; returning album-only metadata.')
        tracks = None

    return [info, tracks]


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

    info.update(parse_rating(album_soup))

    canonical = extract_canonical_url(album_soup)
    if canonical:
        info['#canonical-url'] = canonical

    _ensure_moods_themes(info, album_soup, info.get('#canonical-url') or album_url)
    _ensure_credits(info, album_soup, info.get('#canonical-url') or album_url)

    review_section = _locate_review_section(album_soup)
    if review_section is None:
        ajax_source = info.get('#canonical-url') or album_url
        ajax_soup = fetch_review_soup(ajax_source)
        review_section = _locate_review_section(ajax_soup)
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
    if not tracks:
        write_log('AllMusic: No track listing found for this album; returning album-only metadata.')
        tracks = None

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
        review_anchor = title_block.find('a', {'class': 'hasReviewLink'})
        if review_anchor is not None:
            track['#has_review'] = True
            review_href = review_anchor.element.attrib.get('href')
            if review_href:
                normalized_href = iri_to_uri(review_href)
                if normalized_href.startswith('/'):
                    normalized_href = 'https://www.allmusic.com' + normalized_href
                track['#trackreviewurl'] = normalized_href
            elif '#trackurl' in track:
                track['#trackreviewurl'] = track['#trackurl']

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


def _locate_performance_title(row):
    parent = row.element.getparent()
    while parent is not None:
        class_attr = parent.attrib.get('class', '') or ''
        classes = class_attr.split()
        if 'performanceParts' in classes:
            wrapper = parse_html.SoupWrapper(parent)
            title_row = wrapper.find('div', {'class': 'performanceTitleRow'})
            if title_row is not None:
                text = element_text(title_row)
                if text:
                    return text
            break
        parent = parent.getparent()
    return None


def parse_classical_disc(disc):
    rows = disc.find_all('div', {'class': re.compile(r'(?:^|\s)resultRow(?:\s|$)')})
    if not rows:
        return []
    tracks = []
    for row in rows:
        track = {}

        number_block = row.find('div', {'class': 'trackNum'})
        if number_block is not None:
            track_number = element_text(number_block)
            if track_number:
                track['track'] = track_number

        title_block = row.find('div', {'class': 'title'})
        if title_block is not None:
            link = title_block.find('a')
            if link is not None and link.string:
                track['title'] = convert(link.string)
                href = link.element.attrib.get('href')
                if href:
                    track['#trackurl'] = iri_to_uri(href)
            else:
                title_text = element_text(title_block)
                if title_text:
                    track['title'] = title_text

        performance_title = _locate_performance_title(row)
        if performance_title and track.get('title'):
            track['title'] = f"{performance_title}: {track['title']}"

        composer_block = row.find('div', {'class': 'composer'})
        if composer_block is not None:
            composer_text = extract_linked_text(composer_block)
            if composer_text:
                track['composer'] = composer_text

        performer_block = row.find('div', {'class': 'performer'})
        if performer_block is not None:
            performer_text = extract_linked_text(performer_block)
            if performer_text:
                track['performer'] = performer_text

        duration_block = row.find('div', {'class': 'duration'})
        if duration_block is not None:
            duration = element_text(duration_block)
            if duration:
                track['__length'] = duration

        favorite = row.find('button', {'class': re.compile(r'(?:^|\s)songFavoriteIcon(?:\s|$)')})
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

        finalized = dict((spanmap.get(k, k), v) for k, v in track.items()
                          if spanmap.get(k, k) and not isempty(v))
        if finalized:
            tracks.append(finalized)

    return tracks


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
            if not disc_tracks:
                disc_tracks = parse_classical_disc(disc)
        for track in disc_tracks:
            if disc_info:
                track.update(disc_info)
            replace_feat(album_info, track)

        tracks.extend(disc_tracks)
    _populate_track_reviews(tracks)
    return tracks


def retrieve_album(url, coverurl=None, id_field=ALBUM_ID):
    write_log('Opening Album Page - %s' % url)
    cover = None
    with _AllMusicUserAgent():
        album_page, code = urlopen(url, False, True)
        if album_page.find(b"featured new releases") >= 0:
            raise OldURLError("Old AMG URL used.")

        album_page = decode_page(album_page)
        info, tracks = parse_albumpage(album_page, album_url=url)
        resolved_url = info.get('#canonical-url', url)
        info['#albumurl'] = resolved_url
        # Set appropriate URL tag based on whether this is a release or main album
        if RELEASE_ID in info:
            info['amg_release_url'] = resolved_url
            main_url = info.get('#main-album-url')
            if main_url:
                info['amg_album_url'] = main_url
        else:
            info['amg_album_url'] = resolved_url

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
            # Prefer release ID over album ID when available
            for field in ('amg_rovi_id', 'amg_pop_id', 'amgsqlid', 'amg_release_id', 'amg_album_id',):
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

        searchpage = decode_page(searchpage)
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
