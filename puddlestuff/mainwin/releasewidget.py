import re
import sys
import traceback
from copy import deepcopy
from functools import partial

from PyQt6 import QtCore
from PyQt6.QtCore import QModelIndex, Qt, pyqtRemoveInputHook, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QAbstractItemView, QApplication, QHeaderView, QMenu, QStyle, QTreeView, QWidget

from ..findfunc import parsefunc
from ..puddleobjects import (PuddleThread,
                            natural_sort_key)
from ..tagsources import RetrievalError
from ..translations import translate
from ..util import pprint_tag, to_string

from rapidfuzz import fuzz

CHECKEDFLAG = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
NORMALFLAG = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

RETRIEVED_ALBUMS = translate("Tag Sources", "Retrieved Albums (sorted by {})")

default_albumpattern = '%artist% - %album% $if(%__numtracks%, ' \
                       '[%__numtracks%], "")'
default_trackpattern = '$if(%discnumber%, Disc %discnumber% - , "")%track% - %title%'

no_disp_fields = ['__numtracks', '__image']

pyqtRemoveInputHook()


def _normalize_title_for_match(title):
    """Normalize title for case-insensitive matching."""
    if not title:
        return ''
    if isinstance(title, list):
        title = title[0] if title else ''
    normalized = str(title).lower().strip()
    # Remove common punctuation that might differ
    for char in '.,!?\'"-()[]':
        normalized = normalized.replace(char, '')
    return ' '.join(normalized.split())


def _title_to_text(value):
    if not value:
        return ''
    if isinstance(value, list):
        value = value[0] if value else ''
    return to_string(value)


def _split_title_subtitle(title_text):
    """Split a title into base title and trailing bracketed subtitle.

    Conservative: only trailing bracket groups are treated as subtitle.
    """
    title_text = (title_text or '').strip()
    if not title_text:
        return '', ''

    subtitle_parts = []
    pattern = re.compile(r'\s*[\(\[\{]([^\)\]\}]+)[\)\]\}]\s*$')
    base = title_text
    while True:
        m = pattern.search(base)
        if not m:
            break
        subtitle_parts.insert(0, m.group(1).strip())
        base = base[:m.start()].rstrip()

    subtitle = '; '.join([p for p in subtitle_parts if p])
    return base.strip(), subtitle.strip()


def _normalize_title_base_for_fuzzy(title_text):
    base, _subtitle = _split_title_subtitle(title_text)
    normalized = (base or '').lower().strip()
    normalized = normalized.replace('’', "'").replace('‘', "'").replace('´', "'")
    normalized = normalized.replace('&', ' and ')
    # Strip trailing featuring info.
    normalized = re.sub(r"\s+\b(feat|featuring|ft)\b\.?\s+.+$", "", normalized).strip()
    for char in '.,!?\'"-()[]{}':
        normalized = normalized.replace(char, ' ')
    return ' '.join(normalized.split())


def _normalize_subtitle_for_fuzzy(subtitle_text):
    normalized = (subtitle_text or '').lower().strip()
    normalized = normalized.replace('’', "'").replace('‘', "'").replace('´', "'")
    normalized = re.sub(r"\s+\b(feat|featuring|ft)\b\.?\s+.+$", "", normalized).strip()
    for char in '.,!?\'"-()[]{}':
        normalized = normalized.replace(char, ' ')
    return ' '.join(normalized.split())


def _album_only_tags(album_info):
    merged = {}
    for key, val in album_info.items():
        if not key.startswith('#') and key not in no_disp_fields:
            merged[key] = val
    return merged


def _prepare_retrieved_tracks_for_fuzzy(retrieved_tracks):
    processed = []
    for t in (retrieved_tracks or []):
        title_text = _title_to_text(t.get('title') or t.get('track'))
        base, subtitle = _split_title_subtitle(title_text)
        processed.append({
            'raw': t,
            'base': base,
            'subtitle': subtitle,
            'base_norm': _normalize_title_base_for_fuzzy(title_text),
            'subtitle_norm': _normalize_subtitle_for_fuzzy(subtitle),
        })
    return processed


def _real_get(tags, key, default=''):
    """Get a tag value ignoring preview-mode overlays when possible."""
    if tags is None:
        return default
    if hasattr(tags, 'realvalue'):
        try:
            return tags.realvalue(key, default)
        except Exception:
            return default
    try:
        return tags.get(key, default)
    except Exception:
        return default


def _fuzzy_match_one_file(file_tags, processed_tracks, album_info, min_confidence):
    """Return (tags, score) for one file using title-only fuzzy matching."""
    merged = _album_only_tags(album_info)

    # Always match against the file's real/original title, not the previewed title.
    file_title_text = _title_to_text(_real_get(file_tags, 'title', ''))
    _file_base, file_subtitle = _split_title_subtitle(file_title_text)
    file_base_norm = _normalize_title_base_for_fuzzy(file_title_text)
    file_sub_norm = _normalize_subtitle_for_fuzzy(file_subtitle)

    if not file_base_norm:
        return merged, None

    candidates = []
    for pt in processed_tracks:
        if not pt['base_norm']:
            continue
        score = fuzz.token_sort_ratio(file_base_norm, pt['base_norm'])
        if score >= min_confidence:
            candidates.append((score, pt))

    if not candidates:
        return merged, None

    # Choose a candidate.
    chosen_score = None
    chosen = None

    if not file_sub_norm:
        # Prefer match without subtitle when file has none.
        no_sub = [(s, pt) for (s, pt) in candidates if not pt['subtitle_norm']]
        pool = no_sub if no_sub else candidates
        chosen_score, chosen = max(pool, key=lambda x: x[0])
    else:
        # Prefer best title score; break ties with subtitle similarity.
        best_score = max(s for s, _pt in candidates)
        best = [(s, pt) for (s, pt) in candidates if s == best_score]
        if len(best) == 1:
            chosen_score, chosen = best[0]
        else:
            def tie_key(item):
                _s, pt = item
                if not pt['subtitle_norm']:
                    return 0
                return fuzz.token_sort_ratio(file_sub_norm, pt['subtitle_norm'])
            chosen_score, chosen = max(best, key=tie_key)

    raw_track = chosen['raw']
    for key, val in raw_track.items():
        if key.startswith('#'):
            continue
        # Preserve file's existing track/disc numbers.
        if key in ('track', 'discnumber', 'totaltracks', 'totaldiscs'):
            continue
        merged[key] = val

    # Always write base title.
    if chosen.get('base'):
        merged['title'] = chosen['base']

    # Subtitle only when unambiguous.
    if chosen.get('subtitle'):
        best_score = max(s for s, _pt in candidates)
        best_count = sum(1 for s, _pt in candidates if s == best_score)
        if chosen_score == best_score and best_count == 1:
            merged['subtitle'] = chosen['subtitle']

    return merged, chosen_score


def _match_tracks_by_title(files, title_match_tracks, album_info, tags_to_write, mapping):
    """Match user files to retrieved tracks by title, preserving user's track numbers.
    
    Returns a list of track dicts for each file, with metadata from matched tracks
    but preserving the user's existing track/disc numbers.
    """
    if not files or not title_match_tracks:
        return []
    
    # Build lookup from normalized title -> track metadata
    track_lookup = {}
    for track in title_match_tracks:
        title = track.get('title') or track.get('track')
        if title:
            norm_title = _normalize_title_for_match(title)
            if norm_title:
                track_lookup[norm_title] = track
    
    result_tracks = []
    for file_tags in files:
        # Start with album info (this is the base for all files)
        merged = {}
        for key, val in album_info.items():
            if not key.startswith('#') and key not in no_disp_fields:
                merged[key] = val
        
        # Try to match by title
        file_title = file_tags.get('title', '')
        if isinstance(file_title, list):
            file_title = file_title[0] if file_title else ''
        norm_file_title = _normalize_title_for_match(file_title)
        
        matched_track = track_lookup.get(norm_file_title) if norm_file_title else None
        
        if matched_track:
            # Apply all matched track metadata except track/disc numbers
            for key, val in matched_track.items():
                if key.startswith('#'):
                    continue
                if key in ('track', 'discnumber', 'totaltracks', 'totaldiscs'):
                    continue
                merged[key] = val
        
        # Apply tag filtering and mapping
        if tags_to_write:
            merged = {k: v for k, v in merged.items() 
                     if k in tags_to_write or k.startswith('#')}
        if mapping:
            merged = {mapping.get(k, k): v for k, v in merged.items()}
        
        result_tracks.append(merged)
    
    return result_tracks


def inline_display(pattern, tags):
    return parsefunc(pattern, tags)


def fillItem(item, info, tracks, trackpattern):
    item.itemData = info
    if tracks is not None:
        item.itemData['__numtracks'] = str(len(tracks))
        [item.appendChild(ChildItem(track, trackpattern, item))
         for track in tracks]
        item.hasTracks = True
    else:
        item.itemData['__numtracks'] = '0'
        item.hasTracks = False
    item.dispPattern = item.dispPattern


def get_tagsources():
    from ..tagsources import exampletagsource, musicbrainz
    return exampletagsource.info[0](), musicbrainz.info[0]()


def strip(audio, taglist, reverse=False, mapping=None):
    if not taglist:
        if mapping:
            return dict([(mapping.get(key, key), audio[key]) for
                         key in audio if not key.startswith('#')])
        else:
            return dict([(key, audio[key]) for key in audio if
                         not key.startswith('#')])
    tags = taglist[::]
    if tags and tags[0].startswith('~'):
        reverse = True
        tags[0] = tags[0][1:]
    else:
        reverse = False
    if reverse:
        if mapping:
            return dict([(mapping.get(key, key), audio[key]) for key in audio if key not in
                         tags and not key.startswith('#')])
        else:
            return dict([(key, audio[key]) for key in audio if key not in
                         tags and not key.startswith('#')])
    else:
        if mapping:
            return dict([(mapping.get(key, key), audio[key]) for
                         key in taglist if key in audio and not key.startswith('#')])
        else:
            return dict([(key, audio[key]) for key in taglist if
                         key in audio and not key.startswith('#')])


def tooltip(tag, mapping=None):
    """Used to display tags in in a human parseable format."""
    if not tag:
        return translate("Tag Sources", "<b>Error in pattern</b>")
    mapping = {} if mapping is None else mapping
    tag = dict((mapping.get(k, k), v) for k, v in tag.items()
               if not k.startswith('#'))

    return pprint_tag(tag)


class Header(QHeaderView):
    sortChanged = pyqtSignal(list, name='sortChanged')

    def __init__(self, parent=None):
        QHeaderView.__init__(self, Qt.Orientation.Horizontal, parent)
        self.setSectionsClickable(True)
        self.setStretchLastSection(True)
        self.setSortIndicatorShown(True)
        self.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.sortOptions = [z.split(',') for z in
                            ['artist,album', 'album,artist', '__numtracks,album']]

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        def create_action(order):
            action = QAction('/'.join(order), menu)
            slot = lambda: self.sortChanged.emit(order[::])
            action.triggered.connect(slot)
            menu.addAction(action)

        [create_action(order) for order in self.sortOptions]
        menu.exec(event.globalPos())


class RootItem(object):

    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 1

    def data(self, column):
        return self.itemData[0]

    def parent(self):
        return None

    def row(self):
        return 0

    def sort(self, order=None, reverse=False):
        sortfunc = lambda item: natural_sort_key(''.join([
            to_string(item.itemData.get(key, '')) for key in order]).lower())
        self.childItems.sort(key=sortfunc, reverse=reverse)


class TreeItem(RootItem):

    def __init__(self, data, pattern, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []
        self._display = ''
        self.dispPattern = pattern
        self.hasTracks = True
        self.expanded = False
        self.retrieving = False

    def data(self, column):
        return self._display

    @property
    def dispPattern(self):
        return self._pattern

    @dispPattern.setter
    def dispPattern(self, pattern):
        self._pattern = pattern
        self._display = inline_display(pattern, self.itemData)

    def exact_matches(self):
        ret = []
        for c in self.childItems:
            if c.exact is not None:
                track = c.track()
                track['#exact'] = c.exact
                ret.append(track)
        return ret

    def tracks(self):
        if self.hasTracks:
            info = self.itemData.copy()
            if '__numtracks' in info:
                del (info['__numtracks'])

            def get_track(item):
                track = info.copy()
                track.update(item.itemData.copy())
                return track

            return [get_track(item) for item in self.childItems]
        else:
            return None

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0


class ChildItem(RootItem):

    def __init__(self, data, pattern, parent=None):
        self.parentItem = parent
        self.itemData = data
        if '#exact' in data:
            self.checked = True
            self.exact = data['#exact']
        else:
            self.exact = None
        self.childItems = []
        self._display = ''
        self.dispPattern = pattern
        self.hasTracks = False

    def data(self, column):
        return self._display

    @property
    def dispPattern(self):
        return self._pattern

    @dispPattern.setter
    def dispPattern(self, pattern):
        self._pattern = pattern
        self._display = inline_display(pattern, self.itemData)

    def track(self):
        track = self.parentItem.itemData.copy()
        if '__numtracks' in track:
            del (track['__numtracks'])
        track.update(self.itemData.copy())
        return track

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0


class TreeModel(QtCore.QAbstractItemModel):
    retrieving = pyqtSignal(name='retrieving')
    statusChanged = pyqtSignal(str, name='statusChanged')
    collapse = pyqtSignal(QModelIndex, name='collapse')
    retrievalDone = pyqtSignal(name='retrievalDone')
    exactChanged = pyqtSignal(object, name='exactChanged')
    exactMatches = pyqtSignal(list, name='exactMatches')

    def __init__(self, data=None, album_pattern=None,
                 track_pattern=default_trackpattern, tagsource=None, parent=None):
        QtCore.QAbstractItemModel.__init__(self, parent)

        self.mapping = {}
        rootData = [translate("Tag Sources", 'Retrieved Albums')]
        self.rootItem = RootItem(rootData)

        self._albumPattern = ''
        if album_pattern is None:
            self.albumPattern = default_albumpattern
        else:
            self.albumPattern = album_pattern
        self._sortOrder = ['album', 'artist']
        self._trackPattern = ''
        self.trackPattern = track_pattern
        self.tagsource = tagsource
        icon = QWidget().style().standardIcon
        self.expandedIcon = icon(QStyle.StandardPixmap.SP_DirOpenIcon)
        self.collapsedIcon = icon(QStyle.StandardPixmap.SP_DirClosedIcon)

        if data:
            self.setupModelData(data)

    @property
    def albumPattern(self):
        return self._albumPattern

    @albumPattern.setter
    def albumPattern(self, value):
        self._albumPattern = value
        for item in self.rootItem.childItems:
            item.dispPattern = value
        parent = QModelIndex()
        top = self.index(0, 0, parent)
        bottom = self.index(self.rowCount(parent) - 1, 0, parent)
        self.dataChanged.emit(top, bottom)

    @property
    def sortOrder(self):
        return self._sortOrder

    @sortOrder.setter
    def sortOrder(self, value):
        self._sortOrder = value
        self.sort()

    @property
    def trackPattern(self):
        return self._trackPattern

    @trackPattern.setter
    def trackPattern(self, value):
        self._trackPattern = value
        for row, parent_item in enumerate(self.rootItem.childItems):
            if parent_item.childItems and parent_item.hasTracks:
                for track in parent_item.childItems:
                    track.dispPattern = value
                parent_index = self.index(row, 0, QModelIndex())
                top = self.index(0, 0, parent_index)
                bottom = self.index(self.rowCount(parent_index)
                                    -1, 0, parent_index)
                self.dataChanged.emit(top, bottom)

    def canFetchMore(self, index):
        item = index.internalPointer()
        if item in self.rootItem.childItems and not item.childItems \
                and item.hasTracks:
            return True
        return False

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            item = index.internalPointer()
            return item.data(index.column())
        elif role == Qt.ItemDataRole.ToolTipRole:
            item = index.internalPointer()
            return tooltip(item.itemData, self.mapping)
        elif role == Qt.ItemDataRole.DecorationRole:
            item = index.internalPointer()
            if self.isTrack(item):
                return None
            if item.expanded:
                return self.expandedIcon
            else:
                return self.collapsedIcon
        elif role == Qt.ItemDataRole.CheckStateRole:
            item = index.internalPointer()
            if self.isTrack(item) and '#exact' in item.itemData:
                if item.checked:
                    return Qt.CheckState.Checked
                else:
                    return Qt.CheckState.Unchecked
        return None

    def fetchMore(self, index):
        item = index.internalPointer()
        if item.retrieving:
            return
        self.retrieving.emit()

        def fetch_func():
            try:
                return self.tagsource.retrieve(item.itemData)
            except RetrievalError as e:
                self.statusChanged.emit(
                    translate("Tag Sources", "An error occured: {}").format(str(e)))
                return
            except Exception as e:
                traceback.print_exc()
                self.statusChanged.emit(
                    translate("Tag Sources", "An unhandled error occured: {}").format(str(e)))
                return

        item.retrieving = True
        thread = PuddleThread(fetch_func, self)
        self.statusChanged.emit(translate("Tag Sources", "Retrieving album tracks..."))
        thread.start()
        while thread.isRunning():
            QApplication.processEvents()
        val = thread.retval
        if val:
            info, tracks = val
            fillItem(item, info, tracks, self.trackPattern)
            self.statusChanged.emit(translate("Tag Sources", "Retrieval complete."))
            item.retrieving = False
        else:
            if not item.childCount():
                self.collapse.emit(index)
        self.retrievalDone.emit()

    def hasChildren(self, index):
        item = index.internalPointer()
        if not item:
            return True
        if not item.hasTracks:
            return False
        if (item == self.rootItem) or (item in self.rootItem.childItems):
            if not item.retrieving:
                return True
        return False

    def isTrack(self, item):
        if (item == self.rootItem) or (item in self.rootItem.childItems):
            return False
        return True

    def flags(self, index):
        item = index.internalPointer()
        if self.isTrack(item) and '#exact' in item.itemData:
            return CHECKEDFLAG
        return NORMALFLAG

    def headerData(self, section, orientation, role):
        if orientation == Qt.Orientation.Horizontal and \
                role == Qt.ItemDataRole.DisplayRole:
            ret = RETRIEVED_ALBUMS.format(' / '.join(self.sortOrder))

            return ret

        return None

    def index(self, row, column, parent):
        if row < 0 or column < 0 or row >= self.rowCount(parent) or \
                column >= self.columnCount(parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def retrieve(self, index, fin_func=None):
        item = index.internalPointer()
        if (not self.tagsource) or (item not in self.rootItem.childItems) or \
                (item.childItems) or not item.hasTracks:
            return
        self.retrieving.emit()

        def retrieval_func():
            try:
                return self.tagsource.retrieve(item.itemData)
            except RetrievalError as e:
                self.statusChanged.emit(
                    translate("Tag Sources", "An error occured: {}").format(str(e)))
                return None
            except Exception as e:
                traceback.print_exc()
                self.statusChanged.emit(
                    translate("Tag Sources", "An unhandled error occured: {}").format(str(e)))
                return None

        def finished(val):
            if val is None:
                self.retrievalDone.emit()
                return
            fillItem(item, val[0], val[1], self.trackPattern)
            item.retrieving = False
            self.dataChanged.emit(index, index)
            self.statusChanged.emit(translate("Tag Sources", "Retrieval complete."))
            self.retrievalDone.emit()
            if fin_func:
                fin_func()

        item.retrieving = True
        self.statusChanged.emit(translate("Tag Sources", "Retrieving tracks..."))
        thread = PuddleThread(retrieval_func, parent=self)
        thread.threadfinished.connect(finished)
        thread.start()

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def setData(self, index, value, role=Qt.ItemDataRole.CheckStateRole):
        if index.isValid() and self.isTrack(index):
            item = index.internalPointer()
            item.checked = not item.checked
            self.exactChanged.emit(item)
            return True

    def setupModelData(self, data):
        exact_matches = []
        self.rootItem.childItems = []
        for info, tracks in data:
            parent = TreeItem(info, self.albumPattern, self.rootItem)
            fillItem(parent, info, tracks, self.trackPattern)
            exact_matches.extend(parent.exact_matches())
            self.rootItem.appendChild(parent)
        self.sort()
        if exact_matches:
            self.exactMatches.emit(exact_matches)

    def sort(self, column=0, order=Qt.SortOrder.AscendingOrder):
        self.beginResetModel()
        if order == Qt.SortOrder.AscendingOrder:
            self.rootItem.sort(self.sortOrder)
        else:
            self.rootItem.sort(self.sortOrder, True)
        self.endResetModel()


class ReleaseWidget(QTreeView):
    exact = pyqtSignal(dict, name='exact')
    exactMatches = pyqtSignal(dict, name='exactMatches')
    preview = pyqtSignal(object, name='preview')
    infoChanged = pyqtSignal(str, name='infoChanged')
    statusChanged = pyqtSignal(str, name='statusChanged')
    retrieving = pyqtSignal(name='retrieving')
    retrievalDone = pyqtSignal(name='retrievalDone')
    itemSelectionChanged = pyqtSignal(name='itemSelectionChanged')

    def __init__(self, status, tagsource, parent=None):
        QTreeView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setExpandsOnDoubleClick(False)
        self._tagSource = tagsource
        self._status = status
        self.tagsToWrite = []
        self.reEmitTracks = self.selectionChanged
        self.lastSortIndex = 0
        self.mapping = {}

        self.trackBound = 0.7
        self.albumBound = 0.7
        self.jfdi = True
        self.matchFields = ['artist', 'title']

        self.fuzzyMatch = False
        self.fuzzyBound = 90
        self._fuzzyCacheKey = None
        self._fuzzyCache = {}
        self._fuzzyPrevThreshold = None

        header = Header(self)
        header.sortChanged.connect(self.sort)
        self.setHeader(header)
        model = TreeModel()
        self.setModel(model)

    def resetFuzzyCache(self):
        self._fuzzyCacheKey = None
        self._fuzzyCache = {}
        self._fuzzyPrevThreshold = None

    def _fuzzy_album_key(self, album_item):
        info = getattr(album_item, 'itemData', {}) or {}
        extrainfo = info.get('#extrainfo')
        if isinstance(extrainfo, (list, tuple)) and len(extrainfo) == 2:
            return to_string(extrainfo[1])
        for k in ('amg_url', 'url', 'album_url'):
            if info.get(k):
                return to_string(info.get(k))
        return to_string(info.get('artist', '')) + '|' + to_string(info.get('album', ''))

    def _fuzzy_file_key(self, file_obj):
        if hasattr(file_obj, 'filepath') and getattr(file_obj, 'filepath'):
            return to_string(getattr(file_obj, 'filepath'))
        tags = getattr(file_obj, 'tags', None)
        if isinstance(tags, dict):
            for k in ('__path', '__filename'):
                if tags.get(k):
                    return to_string(tags.get(k))
        return str(id(file_obj))

    def _fuzzy_previews_for_album(self, album_item):
        selected_files = self._status['selectedfiles']
        file_keys = [self._fuzzy_file_key(f) for f in selected_files]
        cache_key = (self._fuzzy_album_key(album_item), tuple(file_keys))
        if cache_key != self._fuzzyCacheKey:
            self.resetFuzzyCache()
            self._fuzzyCacheKey = cache_key

        processed_tracks = _prepare_retrieved_tracks_for_fuzzy(
            [c.itemData for c in album_item.childItems])

        current_threshold = int(self.fuzzyBound)
        prev_threshold = self._fuzzyPrevThreshold

        previews = []
        new_cache = {}
        for f in selected_files:
            f_key = self._fuzzy_file_key(f)
            cached = self._fuzzyCache.get(f_key)

            locked = False
            if cached and prev_threshold is not None:
                cached_score = cached.get('score')
                if current_threshold < prev_threshold:
                    locked = (cached_score is not None and cached_score >= prev_threshold)
                elif current_threshold > prev_threshold:
                    locked = (cached_score is not None and cached_score >= current_threshold)
                else:
                    locked = True

            if locked and cached:
                tags = cached.get('tags', {})
                score = cached.get('score')
            else:
                tags, score = _fuzzy_match_one_file(
                    f, processed_tracks, album_item.itemData, current_threshold)

            previews.append(tags)
            new_cache[f_key] = {'tags': tags, 'score': score}

        self._fuzzyCache = new_cache
        self._fuzzyPrevThreshold = current_threshold
        return previews

    @property
    def albumPattern(self):
        return self._albumPattern

    @albumPattern.setter
    def albumPattern(self, value):
        self._albumPattern = value
        self.model().albumPattern = value

    @property
    def trackPattern(self):
        return self._trackPattern

    @trackPattern.setter
    def trackPattern(self, value):
        self._trackPattern = value
        self.model().trackPattern = value

    @property
    def tagSource(self):
        return self._tagSource

    @tagSource.setter
    def tagSource(self, source):
        self._tagSource = source
        self.model().tagsource = source
        self.resetFuzzyCache()

    def cleanTrack(self, track):
        return strip(track, self.tagsToWrite, mapping=self.mapping)

    def emitExactMatches(self, item, files):
        if not item.hasTracks:
            return
        preview = {}
        from ..masstag import match_files
        tracks = item.tracks()
        copies = []
        for f in files:
            cp = deepcopy(f)
            cp.cls = f
            copies.append(cp)

        exact = match_files(copies, tracks, self.trackBound, self.matchFields,
                            self.jfdi, False)
        ret = {}
        for f, t in exact.items():
            t = strip(t, self.tagsToWrite, mapping=self.mapping)
            ret[f] = t
        self.exact.emit(ret)
        return ret

    def emitInitialExact(self, exact):
        ret = {}

        for track in exact:
            ret[track['#exact']] = self.cleanTrack(track)

        self.exactMatches.emit(ret)

    def emitTracks(self, tracks):
        tracks = list(map(dict, tracks))
        tracks = list(map(self.cleanTrack, tracks))
        # import pdb
        # pdb.set_trace()
        if tracks:
            self.preview.emit(
                tracks[:len(self._status['selectedrows'])])
        else:
            rows = self._status['selectedrows']
            self.preview.emit([{} for x in rows])

    def exactChanged(self, item):
        if item.checked:
            track = strip(item.itemData, self.tagsToWrite,
                          mapping=self.mapping)
            self.preview.emit({item.itemData['#exact']: track})
        else:
            self.preview.emit({item.itemData['#exact']: {}})

    def selectionChanged(self, selected=None, deselected=None):
        if selected or deselected:
            QTreeView.selectionChanged(self, selected, deselected)
        model = self.model()
        isTrack = model.isTrack

        items = [index.internalPointer() for index in self.selectedIndexes()]
        if len(items) == 1 and not isTrack(items[0]) \
                and not items[0].hasTracks:
            item = items[0]
            # Check for title-based matching tracks (from releases with no track listing)
            title_match_tracks = item.itemData.get('#title_match_tracks')
            if title_match_tracks:
                # Match user files to tracks by title, preserving track numbers
                files = [f.tags for f in self._status['selectedfiles']]
                tracks = _match_tracks_by_title(
                    files, title_match_tracks, item.itemData,
                    self.tagsToWrite, self.mapping)
            else:
                # No title matching - just copy album info to all files
                copytag = item.itemData.copy
                tags = self.tagsToWrite
                tracks = [strip(copytag(), tags, mapping=self.mapping) for z in
                          self._status['selectedrows']]
            if '#extrainfo' in item.itemData:
                desc, url = item.itemData['#extrainfo']
                self.infoChanged.emit(
                    '<a href="%s">%s</a>' % (url, desc))
        else:
            singles = []
            albums = []
            [singles.append(item) if isTrack(item) else
             albums.append(item) for item in items]
            if self.fuzzyMatch and len(albums) == 1 and albums[0].hasTracks:
                # Fuzzy match is opt-in; ignore selected track rows.
                tracks = self._fuzzy_previews_for_album(albums[0])
            else:
                tracks = []
                for item in singles:
                    if not item.parentItem in albums:
                        tracks.append(item.track())
                [tracks.extend(item.tracks()) for item in albums
                 if item.hasTracks]
            for item in albums:
                if '#extrainfo' in item.itemData:
                    desc, url = item.itemData['#extrainfo']
                    self.infoChanged.emit(
                        '<a href="%s">%s</a>' % (url, desc))
                    break
        self.emitTracks(tracks)
        self.itemSelectionChanged.emit()

    def _setCollapsedFlag(self, index):
        item = index.internalPointer()
        item.expanded = False

    def _setExpandedFlag(self, index):
        item = index.internalPointer()
        item.expanded = True

    def setModel(self, model):
        QTreeView.setModel(self, model)
        connect = lambda signal, slot: getattr(self, signal).connect(
            slot)
        modelconnect = lambda signal, slot: getattr(model, signal).connect(slot)
        func = partial(model.retrieve, fin_func=self.selectionChanged)
        # connect('activated', func)
        connect('expanded', self._setExpandedFlag)
        connect('collapsed', self._setCollapsedFlag)
        connect('clicked', func)
        model.statusChanged.connect(self.statusChanged)
        model.exactChanged.connect(self.exactChanged)
        modelconnect('exactMatches', self.emitInitialExact)
        modelconnect('retrieving', self.retrieving)
        modelconnect('retrievalDone', self.retrievalDone)
        modelconnect('retrieving', lambda: self.setEnabled(False))
        modelconnect('retrievalDone', lambda: self.setEnabled(True))
        modelconnect('collapse', self.collapse)
        model.tagsource = self.tagSource
        model.mapping = self.mapping

    def setReleases(self, releases, files=None):
        from ..masstag import find_best
        self.model().setupModelData(releases)
        # FIXME: The expander isn't shown if I don't do this. However
        # I can still click on it...Qt bug probably.
        QApplication.processEvents()

        if files:
            matches = find_best(releases, files, self.albumBound)
            if not matches:
                self.statusChanged.emit(translate(
                    'WebDB', 'No matching albums were found.'))
            elif len(matches) > 1:
                self.statusChanged.emit(translate(
                    'WebDB', 'More than one album matches. None will be retrieved.'))
            else:
                self.statusChanged.emit(translate(
                    'WebDB', 'Retrieving album.'))
                model = self.model()
                children = [z.itemData for z in model.rootItem.childItems]
                if children:
                    row = children.index(matches[0][0])
                    index = model.index(row, 0, QModelIndex())
                    x = lambda: self.emitExactMatches(
                        model.rootItem.childItems[row], files)
                    model.retrieve(index, x)

    def setSortOptions(self, options):
        self.header().sortOptions = options

    def sort(self, order):
        self.model().sortOrder = order
        self.model().sort()
        if order in self.header().sortOptions:
            self.lastSortIndex = self.header().sortOptions.index(order)

    def setMapping(self, mapping):
        self.model().mapping = mapping
        self.mapping = mapping
        self.resetFuzzyCache()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    model = TreeModel()
    model.setupModelData(data)

    view = ReleaseWidget(1, get_tagsources()[0])
    view.setModel(model)
    view.setWindowTitle("Simple Tree Model")
    view.show()
    sys.exit(app.exec())
