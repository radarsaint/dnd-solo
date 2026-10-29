"""Adventure ingestion: a player's private adventure -> a campaign-local index -> rooms
compiled just in time into Kit's existing room format (docs/architecture/ADVENTURE_INGESTION.md).

Architecture 1 from the ingestion research: index once, compile each location when play
approaches it, cache it, pre-compile its neighbours. The room loader and engine run the
result unchanged; a compiled room is an ordinary room file.

What is deterministic and what is model-assisted:

* ``ingest`` (one host step): a PDF or pasted text -> the index and the first scene.
  ``import`` (deterministic) is the index alone. A PDF is read with the stdlib text-layer
  reader (``runtime/kit_pdf.py``); ``pdftotext`` or ``pypdf`` are used only when that
  reader cannot, and only if the host has them. -> ``index.json``:
  chapters, keyed locations with character offsets and pages, NPC mentions, stat-block
  references, connections between locations, and pages that are mostly map/image.
* ``compile`` (deterministic by default): one keyed location -> a room draft. Read-aloud
  text (lines starting with ``>``) becomes visible facts; every other sentence becomes a
  hidden fact. Each connection becomes an exit whose far side ``room_link``s to the
  neighbour's cached room file. Every field carries provenance (a quote and an offset)
  in a sidecar file; a field with no source is rejected.
* ``compile --draft-file`` (model-assisted): the host model may submit a better draft
  (for example splitting a paragraph into facts, or choosing which DM text the PC can
  see) under a strict spec. The runtime validates it: every fact's quote must appear
  verbatim in that location's source span, a visible fact must quote read-aloud text,
  and anything without a quote is refused. The runtime does the checking, not the host.

The adventure text is private: it lives next to the save (``<db>.adventure/``), which is
git-ignored, and is never committed. Nothing here invents rooms, NPCs or stat blocks: a
creature the book does not stat resolves to SRD 5.1 if listed, else it is flagged
``ask_player``. Stdlib only.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

INDEX_VERSION = 1
MAP_PAGE_MAX_CHARS = 200     # a page with less text than this is treated as mostly map/image
FACT_MAX_CHARS = 400         # one fact's text; longer sentences are cut at a word boundary
HIDDEN_BUDGET_BYTES = 6000   # well under kit_rooms.DM_ONLY_ROOM_MAX_BYTES; the rest is flagged
VISIBLE_MAX = 12
READINESS = ('none', 'source_available', 'location_executable', 'campaign_playable')

CHAPTER_RE = re.compile(r'^(?:(?:chapter|part)\s+[\w-]+|appendix(?:\s+[\w-]+)?)\s*[:.\-]?\s*(.*)$', re.I)
# "1. Mill Yard", "Area 3: The Cellar", "A2. Gatehouse", "12b. Loft"
LOCATION_RE = re.compile(r'^(?:area\s+)?([A-Z]?\d{1,3}[a-z]?)\s*[.:]\s+([A-Z][^\n]{1,70})$', re.I)
AREA_REF_RE = re.compile(r'\b(?:areas?|locations?|room)\s+([A-Z]?\d{1,3}[a-z]?)\b', re.I)
STAT_HEAD_RE = re.compile(r'^([A-Z][A-Za-z\' -]{1,40})\n(?:[^\n]*\n){0,2}armor class\s+\d+', re.I | re.M)
SEE_RE = re.compile(r'\(see (?:the )?([^)]{2,60}?)(?:\'s)? (?:stat block|statistics|in the [^)]*|appendix[^)]*)\)', re.I)
# "a marsh hag (see the Monster Manual)": a creature the book points elsewhere for.
ELSEWHERE_RE = re.compile(r'\b(?:a|an|the|one|two|three|four|five|six|\d+)\s+([a-z][a-z -]{2,30}?)\s*'
                          r'\(see (?:the )?(?:monster manual|mm|bestiary|core rules)[^)]*\)', re.I)
NPC_RE = re.compile(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)?), (?:a|an|the) ((?:[a-z]+ ){0,3}[a-z]+)')
SECRET_RE = re.compile(r'\b(secret|hidden|concealed)\b', re.I)
SENTENCE_RE = re.compile(r'[^.!?]+[.!?]+(?:["\')\]]+)?|[^.!?]+$')
NOT_NPC = {'The', 'This', 'That', 'These', 'Those', 'If', 'When', 'Each', 'Any', 'Its', 'His', 'Her', 'A', 'An', 'However'}


class IngestError(ValueError):
    """An adventure step that cannot proceed; ``problems`` names why, for the host."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__('; '.join(self.problems))


# ---------------------------------------------------------------- where things live

def folder_for(db):
    """The campaign-local, git-ignored adventure folder for a save."""
    return Path(str(db) + '.adventure')


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '_', text.casefold()).strip('_')[:40] or 'x'


def _norm(text):
    return re.sub(r'\s+', ' ', text).strip()


# ---------------------------------------------------------------- PDF

NO_TEXT_LAYER = ('this PDF has no text layer (it looks scanned or image-only); '
                 'paste the text or pass --text-file. The built-in reader cannot OCR')
POOR_TEXT = ('this PDF has a text layer but the built-in reader could not read it '
             '(often a custom font encoding); extract it with pdftotext -layout or pypdf, '
             'or paste the text and pass --text-file')
NOT_PDF = 'this file is not a PDF; pass a .pdf or --text-file'


def pdf_text(data):
    """Stdlib text layer of a PDF (positions, columns, boxes). Empty when it cannot be read."""
    from .kit_pdf import extract
    return extract(data)['text']


def pdf_yield_ok(text):
    """True when extracted text is words, not a scan or a garbled encoding."""
    from .kit_pdf import text_usable
    return text_usable(text)


def _pdftotext(path):
    tool = shutil.which('pdftotext')
    if not tool:
        return None
    try:
        done = subprocess.run([tool, '-layout', '-enc', 'UTF-8', str(path), '-'],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.decode('utf-8', errors='replace')


def _pypdf_text(path):
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        reader = PdfReader(str(path))
        return '\f'.join((page.extract_text() or '') for page in reader.pages)
    except Exception:
        return None


def optional_pdf_text(path, reader='auto'):
    """``(text, name)`` from pdftotext and/or pypdf when the host has them, else ``(None, None)``.

    The built-in reader is the default. These run only when it cannot read the text layer,
    or when the host names one with ``--reader``.
    """
    order = ('pdftotext', 'pypdf') if reader == 'auto' else (reader,)
    for name in order:
        text = _pdftotext(path) if name == 'pdftotext' else _pypdf_text(path) if name == 'pypdf' else None
        if text and pdf_yield_ok(text):
            return text, name
    return None, None


def read_pdf(path, reader='auto'):
    """``(text, reader_name)`` from a PDF. Refuses a missing file, a non-PDF, a scan, or
    a text layer the chosen reader cannot decode. ``reader`` is auto, stdlib, pdftotext, or pypdf."""
    path = Path(path)
    if not path.is_file():
        raise IngestError(['no PDF at %s' % path])
    if reader not in ('auto', 'stdlib', 'pdftotext', 'pypdf'):
        raise IngestError(['unknown PDF reader %r (auto, stdlib, pdftotext, pypdf)' % reader])
    data = path.read_bytes()
    if not data.startswith(b'%PDF'):
        raise IngestError([NOT_PDF])
    from .kit_pdf import extract, text_readable
    found = extract(data) if reader in ('auto', 'stdlib') else {'kind': 'poor', 'text': ''}
    # Letter-spaced stdlib text ('T h e', 'F o llo wi n') is a weak read. pdftotext, when the
    # host has it, is the fallback. --reader stdlib never takes that path.
    if reader == 'auto' and found.get('kind') == 'text' and not text_readable(found.get('text')):
        alt, name = optional_pdf_text(path, 'pdftotext')
        if alt and text_readable(alt):
            return alt, name
    if reader == 'stdlib' or (reader == 'auto' and found['kind'] == 'text'):
        if found['kind'] == 'no_text_layer':
            raise IngestError([NO_TEXT_LAYER])
        if found['kind'] != 'text':
            raise IngestError([POOR_TEXT])
        return found['text'], 'stdlib'
    if reader == 'auto' and found['kind'] == 'no_text_layer':
        text, name = optional_pdf_text(path, 'auto')
        if text:
            return text, name
        raise IngestError([NO_TEXT_LAYER])
    text, name = optional_pdf_text(path, 'auto' if reader == 'auto' else reader)
    if text:
        return text, name
    if found.get('kind') == 'no_text_layer':
        raise IngestError([NO_TEXT_LAYER])
    raise IngestError([POOR_TEXT])


# ---------------------------------------------------------------- import (deterministic)

def _lines(text):
    """(offset, line) for each line."""
    at = 0
    for line in text.split('\n'):
        yield at, line
        at += len(line) + 1


def _norm_line(text):
    return re.sub(r'\d+', '#', re.sub(r'\s+', ' ', text).strip().casefold())


def _toc_line(stripped):
    """A contents entry ('4. Tower Room .... 9'), not a room you can enter."""
    if re.search(r'\.{2,}\s*\d+\s*$', stripped):
        return True
    if re.search(r'\s{3,}\d{1,3}\s*$', stripped) and len(stripped) < 80:
        return True
    return False


def strip_running_matter(text):
    """Drop a header or footer repeated on later pages. The first copy stays, so one
    'PART 1: ...' is a chapter and the copies on the next sixty pages are not."""
    pages = text.split('\f')
    if len(pages) < 2:
        return text

    def edges(page):
        raw = page.split('\n')
        idx = [i for i, line in enumerate(raw) if line.strip()]
        if not idx:
            return set()
        found = {idx[0]}
        if len(idx) > 1:
            found.add(idx[-1])
        return found

    counts = {}
    for page in pages:
        raw = page.split('\n')
        seen = set()
        for i in edges(page):
            key = _norm_line(raw[i])
            if len(key) < 4 or key in seen:
                continue
            counts[key] = counts.get(key, 0) + 1
            seen.add(key)
    repeated = {key for key, count in counts.items() if count >= 3}
    if not repeated:
        return text
    kept = set()
    out = []
    for page in pages:
        raw = page.split('\n')
        edge = edges(page)
        lines = []
        for i, line in enumerate(raw):
            key = _norm_line(line)
            if i in edge and key in repeated:
                if key in kept:
                    continue
                kept.add(key)
            lines.append(line)
        out.append('\n'.join(lines))
    return '\f'.join(out)



_DM_SECTION_RE = re.compile(
    r'^(?:developments|features|treasure|creatures|tactics|roleplaying|'
    r'adjusting|xp awards|setup|background)\b', re.I)
_SECOND_PERSON_RE = re.compile(r'\b(?:you|your|yours)\b', re.I)
_BODY_CHAPTER_RE = re.compile(
    r'(?:provides the characters|cannot be removed|see the|scrolls in his|'
    r'appendix a\)|part\s+\d+,|wave echo cave\.\)")', re.I)


def _location_name_ok(stripped):
    """Reject spell lines and sentences that LOCATION_RE still matches."""
    m = LOCATION_RE.match(stripped)
    if not m:
        return False
    name = m.group(2).strip()
    if re.search(r'\bDC\s+\d+', name):
        return False
    if name.count('.') >= 1 and len(name) > 24:
        return False
    if len(name.split()) > 8:
        return False
    if re.match(r'^(?:paralyzing|wounding|enervation|fear|fire|cold|lightning)\s+ray\b', name, re.I):
        return False
    return True


def _is_real_chapter(title):
    """A PART/Chapter heading, not a TOC crumb or a mid-sentence body bleed."""
    stripped = (title or '').strip()
    if not stripped or not CHAPTER_RE.match(stripped):
        return False
    if _toc_line(stripped):
        return False
    if len(stripped) > 70:
        return False
    if _BODY_CHAPTER_RE.search(stripped):
        return False
    if stripped.count(',') >= 1 and len(stripped) > 42:
        return False
    if not _readable_heading(stripped):
        return False
    if re.match(r'appendix\b', stripped, re.I) and (')' in stripped or len(stripped) > 40):
        return False
    if '"' in stripped or stripped.endswith(')') or '|' in stripped and len(stripped) > 30:
        return False
    return True



_READ_CUE = re.compile(
    r'\b(?:read(?:\s+or\s+paraphrase|\s+aloud|\s+the\s+following)?|boxed text)\b', re.I)


def mark_read_aloud(text):
    """Prefix player-facing lines with ``> `` when the book did not.

    A vector box or an italic face is already marked by the PDF reader. Pasted text and
    ``pdftotext -layout`` keep the box as indentation under the location heading, or as a
    'read or paraphrase' cue. When those are missing, the first second-person narrative
    paragraph under a location heading (before DEVELOPMENTS / Features / Treasure) is
    treated as read-aloud so a flush-left starter-book opening still mounts. Stat lines
    stay unmarked.
    """
    pages = []
    for page in text.split('\f'):
        lines = page.split('\n')
        marked = []
        i = 0
        cue = False
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if cue:
                if not stripped:
                    cue = False
                    marked.append(line)
                else:
                    marked.append(line if stripped.startswith('>') else '> ' + stripped)
                i += 1
                continue
            if stripped and _READ_CUE.search(stripped) and not stripped.startswith('>'):
                marked.append(line)
                cue = True
                i += 1
                continue
            loc_ok = (LOCATION_RE.match(stripped)
                      and (not stripped.endswith('.') or len(stripped) < 40)
                      and not _toc_line(stripped)
                      and _location_name_ok(stripped))
            if loc_ok:
                marked.append(line)
                indent = len(line) - len(line.lstrip(' '))
                i += 1
                while i < len(lines) and lines[i].strip():
                    nxt = lines[i]
                    nxt_indent = len(nxt) - len(nxt.lstrip(' '))
                    body = nxt.strip()
                    if (nxt_indent >= indent + 2 and not LOCATION_RE.match(body)
                            and not _toc_line(body)):
                        marked.append(nxt if body.startswith('>') else '> ' + body)
                        i += 1
                        continue
                    break
                block_lines = []
                while i < len(lines):
                    nxt = lines[i]
                    body = nxt.strip()
                    if not body:
                        block_lines.append((i, nxt, body))
                        i += 1
                        continue
                    if (LOCATION_RE.match(body) or CHAPTER_RE.match(body)
                            or _DM_SECTION_RE.match(body) or _toc_line(body)):
                        break
                    block_lines.append((i, nxt, body))
                    i += 1
                already = any(body.startswith('>') for _idx, _nxt, body in block_lines if body)
                area_in = re.compile(r'\barea\s+[A-Z]?\d', re.I)
                marking = False
                for idx, nxt, body in block_lines:
                    if not body:
                        marked.append(nxt)
                        continue
                    if already:
                        marked.append(nxt)
                        continue
                    if not marking:
                        if _SECOND_PERSON_RE.search(body) and ('.' in body or len(body) > 40):
                            marking = True
                            marked.append('> ' + body)
                        else:
                            marked.append(nxt)
                        continue
                    # Once the second-person read-aloud starts, stop at DM area refs / DC lines.
                    if area_in.search(body) or re.search(r'\bDC\s+\d+', body):
                        marking = False
                        marked.append(nxt)
                        continue
                    marked.append('> ' + body)
                continue
            marked.append(line)
            i += 1
        pages.append('\n'.join(marked))
    return '\f'.join(pages)


def prepare_source(text):
    """Running headers off, read-aloud marked. The index and the saved source are this text."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return mark_read_aloud(strip_running_matter(text))


def _strip_toc_bleed(title):
    """A contents entry ('4. Goblin Arrows .... 5') is not the adventure's name."""
    title = re.sub(r'\s*\.{2,}.*$', '', title or '').strip()
    title = re.sub(r'\s{2,}\d{1,3}$', '', title).strip()
    return title


def _readable_heading(text):
    """False for a letter-spaced fake title ('F o llo wi n g')."""
    words = re.findall(r"[A-Za-z']+", text or '')
    if not words:
        return False
    singles = sum(1 for word in words if len(word) == 1)
    if len(words) >= 3 and singles / float(len(words)) > 0.34:
        return False
    if len(words) >= 4 and sum(len(word) for word in words) / float(len(words)) < 2.4:
        return False
    return True


def _site_of(title):
    """The site slug of a clean PART heading. A chapter, an appendix, or a garbled line is not a site."""
    if not title or not re.match(r'part\b', title.strip(), re.I):
        return ''
    match = re.match(r'part\s+([\w-]+)\s*[:.\-]?\s*(.*)$', title.strip(), re.I)
    if not match:
        return ''
    name = match.group(2).strip() or ('part ' + match.group(1))
    name = name.replace('|', ' ')
    name = re.sub(r'^(?:the|a|an)\s+', '', name, flags=re.I)
    name = _strip_toc_bleed(name)
    name = re.sub(r'\s+', ' ', name).strip()
    fold = name.casefold()
    # OCR: Phandalin split or Ll-for-li
    fold = fold.replace('phan dalln', 'phandalin').replace('phandalln', 'phandalin')
    fold = fold.replace('phan_dalln', 'phandalin')
    if not _readable_heading(name) and not _readable_heading(fold):
        return ''
    slug = _slug(fold)[:24]
    return slug.replace('phan_dalln', 'phandalin')


def _index_title(title, chapters):
    if title:
        cleaned = _strip_toc_bleed(title)
        if cleaned and not _toc_line(title) and _readable_heading(cleaned):
            return cleaned
    for chapter in chapters:
        if _readable_heading(chapter['title']) and not _toc_line(chapter['title']):
            return _strip_toc_bleed(chapter['title'])
    return title or 'Adventure'


def _opening_chapter(title):
    text = (title or '').casefold()
    if 'appendix' in text:
        return False
    if re.search(r'\b(?:part|chapter)\s+1\b', text):
        return True
    return bool(re.search(r'\b(?:introduction|prologue)\b', text))


def _chapter_norm(title):
    """Collapse PART 2 OCR variants onto one key (part 2 / chapter 1)."""
    stripped = (title or '').strip()
    m = re.match(r'^(part|chapter)\s+([\w-]+)', stripped, re.I)
    if m:
        return '%s %s' % (m.group(1).casefold(), m.group(2).casefold())
    if re.match(r'^appendix\b', stripped, re.I):
        return 'appendix'
    return re.sub(r'\s+', ' ', stripped.casefold())


def _preferred_chapter_title(current, challenger):
    """Prefer the cleaner PART title when OCR variants collide."""
    if not current:
        return challenger
    if not challenger:
        return current

    def score(t):
        s = 0
        if _readable_heading(t):
            s += 2
        if '|' not in t:
            s += 1
        words = re.findall(r"[A-Za-z']+", t)
        if words:
            s += sum(1 for w in words if len(w) >= 3)
            s -= sum(1 for w in words if len(w) == 1)
        fold = re.sub(r'[^a-z]', '', t.casefold())
        if 'phandalin' in fold:
            s += 5
        if 'goblinarrows' in fold:
            s += 3
        if 'waveechocave' in fold:
            s += 3
        return s

    return challenger if score(challenger) > score(current) else current



_CREATURE_NAME = re.compile(r"^[A-Z][A-Za-z' -]{0,40}$")
_TYPE_LINE = re.compile(r'^(?:tiny|small|medium|large|huge|gargantuan)\b', re.I)
_NOT_CREATURE = re.compile(
    r'^(?:appendix|chapter|part|contents|index|introduction|prologue|epilogue|overview|credits|map)\b',
    re.I)


def _creature_name_line(line):
    line = line.strip().lstrip('>').strip()
    if not line or not line[0].isupper() or not _CREATURE_NAME.match(line):
        return False
    if LOCATION_RE.match(line) or _toc_line(line) or _NOT_CREATURE.match(line):
        return False
    if re.match(r'(?:armor|armour)\s+class|hit points|speed|str|dex|con|int|wis|cha$', line, re.I):
        return False
    return 1 <= len(line.split()) <= 6


def _stat_blocks(text, page_of):
    """Creature blocks. The name may sit more than two lines above Armor Class."""
    found = {}
    for match in re.finditer(r'(?im)^[ \t>]*((?:armor|armour)\s+class\s+\d+)', text):
        before = text[max(0, match.start() - 600):match.start()]
        name = None
        name_at = None
        lines = before.split('\n')
        consumed = 0
        for line in reversed(lines[-8:]):
            consumed += len(line) + 1
            if _TYPE_LINE.match(line.strip()):
                continue
            if _creature_name_line(line):
                name = line.strip().lstrip('>').strip()
                name_at = match.start() - consumed + (len(line) - len(line.lstrip()))
                break
        if not name:
            continue
        window = text[match.start():match.start() + 900]
        if not re.search(r'hit points\s+\d+', window, re.I):
            continue
        if _NOT_CREATURE.match(name):
            continue
        entry = {'name': name, 'offset': name_at if name_at and name_at >= 0 else match.start(),
                 'page': page_of(match.start())}
        parsed, _prov, _problems = parse_stat_block(text, entry)
        if not parsed:
            continue
        entry['stat_block'] = parsed
        found[name.casefold()] = entry
    return found


def _opening_start(chapters, locations):
    """The first keyed area of part 1 / chapter 1 / the introduction, not whichever key was seen first."""
    opening = [c for c in chapters if _opening_chapter(c['title'])]
    pool = []
    if opening:
        chosen = min(opening, key=lambda c: c['offset'])
        pool = [loc for loc in locations.values() if loc.get('chapter') == chosen['title']]
    if not pool:
        pool = [loc for loc in locations.values()
                if 'appendix' not in (loc.get('chapter') or '').casefold()]
    if not pool:
        pool = list(locations.values())
    pool.sort(key=lambda loc: loc['offset'])
    return pool[0]['key'] if pool else None


def _resolve_area(bare, loc, sentence, by_site, unique):
    """Area 4 in the hideout is the hideout's 4, not the castle's."""
    bare = bare.upper()
    site = loc.get('site') or ''
    folded = sentence.casefold()
    for (other, key), loc_key in by_site.items():
        if key == bare and other and other != site and other.replace('_', ' ') in folded:
            return loc_key
    if (site, bare) in by_site:
        return by_site[(site, bare)]
    # Never jump to another site's reused number just because the bare int is unique globally.
    if site:
        return None
    return unique.get(bare)


def build_index(text, title=None):
    """The global index of an adventure's text. Pure: same text, same index."""
    page_starts = [0] + [m.end() for m in re.finditer('\f', text)]
    page_of = lambda off: sum(1 for s in page_starts if s <= off)  # noqa: E731
    pages = []
    for number, start in enumerate(page_starts, 1):
        end = page_starts[number] - 1 if number < len(page_starts) else len(text)
        chars = len(re.sub(r'\s', '', text[start:end]))
        pages.append({'page': number, 'start': start, 'end': end, 'chars': chars,
                      'needs_map_look': chars < MAP_PAGE_MAX_CHARS})
    chapters, heads = [], []
    current = None
    for off, line in _lines(text.replace('\f', '\n')):
        stripped = line.strip()
        if not stripped or stripped.startswith('>') or _toc_line(stripped):
            continue
        lead = len(line) - len(line.lstrip())
        chapter = CHAPTER_RE.match(stripped)
        if chapter:
            if not _is_real_chapter(stripped):
                continue  # TOC crumb, body bleed, or letter-spaced fake
            norm = _chapter_norm(stripped)
            prior = next((c for c in chapters if _chapter_norm(c['title']) == norm), None)
            if prior is None:
                chapters.append({'title': re.sub(r'\s+', ' ', stripped.replace('|', ' ')).strip(), 'offset': off + lead, 'page': page_of(off)})
                current = stripped
            else:
                prior['title'] = _preferred_chapter_title(prior['title'], stripped)
                current = prior['title']
            heads.append(('chapter', off, None, None, current))
            continue
        loc = LOCATION_RE.match(stripped)
        if loc and _location_name_ok(stripped) and (not stripped.endswith('.') or len(stripped) < 40):
            name = loc.group(2).strip().rstrip('.').replace('|', ' ')
            name = re.sub(r'\s+', ' ', name).strip()
            heads.append(('location', off, loc.group(1).upper(), name, current))
    raw = []
    for i, (kind, off, key, name, chapter) in enumerate(heads):
        if kind != 'location':
            continue
        end = heads[i + 1][1] if i + 1 < len(heads) else len(text)
        body_start = text.index('\n', off) + 1 if '\n' in text[off:end] else end
        raw.append({'bare': key, 'name': name, 'offset': off, 'body': [body_start, end],
                    'page': page_of(off), 'chapter': chapter, 'site': _site_of(chapter)})
    # Carry the last real PART site forward so a body-bleed "chapter" does not orphan areas.
    last_site = ''
    for loc in raw:
        if loc.get('site'):
            last_site = loc['site']
        elif last_site and not loc.get('site'):
            loc['site'] = last_site
    bare_sites = {}
    for loc in raw:
        bare_sites.setdefault(loc['bare'], set()).add(loc['site'])
    has_part_site = any(loc.get('site') for loc in raw)
    locations = {}
    for loc in raw:
        sites = bare_sites[loc['bare']]
        # A known PART never leaves a bare int: hideout-1, not 1. A single-chapter book
        # with no PART keeps 1, 2, 3. A letter-spaced chapter is not a site.
        if loc.get('site'):
            key = loc['site'] + '-' + loc['bare']
        elif has_part_site and last_site:
            loc['site'] = last_site
            key = last_site + '-' + loc['bare']
        elif len(sites) > 1:
            key = loc['bare']
        else:
            key = loc['bare']
        if key in locations:
            continue
        loc['key'] = key
        locations[key] = loc
    stat_blocks = _stat_blocks(text, page_of)
    by_site = {(loc.get('site') or '', loc['bare']): key for key, loc in locations.items()}
    bare_keys = {}
    for key, loc in locations.items():
        bare_keys.setdefault(loc['bare'], []).append(key)
    unique = {bare: keys[0] for bare, keys in bare_keys.items() if len(keys) == 1}
    for key, loc in locations.items():
        span = text[loc['body'][0]:loc['body'][1]]
        connections = []
        for m in AREA_REF_RE.finditer(span):
            sentence = _sentence_around(span, m.start())
            target = _resolve_area(m.group(1), loc, sentence, by_site, unique)
            if target and target != key and target not in [c['to'] for c in connections]:
                connections.append({'to': target, 'offset': loc['body'][0] + m.start(),
                                    'quote': sentence, 'secret': bool(SECRET_RE.search(sentence))})
        loc['connections'] = connections
        loc['creatures'] = _creatures(span, loc['body'][0], stat_blocks)
        loc['npcs'] = sorted({m.group(1) for m in NPC_RE.finditer(span) if m.group(1).split()[0] not in NOT_NPC})
        loc['read_aloud'] = any(line.lstrip().startswith('>') for line in span.split('\n'))
    # Undirected within a site. A cross-site link stays one-way unless the quote named both.
    for key, loc in locations.items():
        for c in loc['connections']:
            other = locations[c['to']]
            if (loc.get('site') or '') != (other.get('site') or '') and not c.get('stated_in'):
                # Forward edge was an explicit cross-site name; do not invent a back edge.
                if (loc.get('site') or '').replace('_', ' ') not in (c.get('quote') or '').casefold():
                    continue
            back = other['connections']
            if key not in [b['to'] for b in back]:
                back.append({'to': key, 'offset': c['offset'], 'quote': c['quote'], 'secret': c['secret'],
                             'stated_in': key})
    npcs = sorted({n for loc in locations.values() for n in loc['npcs']})
    return {'version': INDEX_VERSION, 'title': _index_title(title, chapters),
            'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'chars': len(text),
            'chapters': chapters, 'locations': locations, 'npcs': npcs, 'stat_blocks': stat_blocks,
            'pages': pages, 'map_pages': [p['page'] for p in pages if p['needs_map_look']],
            'start': _opening_start(chapters, locations)}


def _sentence_around(span, at):
    start = max(span.rfind('.', 0, at), span.rfind('\n', 0, at)) + 1
    end_dot = span.find('.', at)
    end = len(span) if end_dot < 0 else end_dot + 1
    return _norm(span[start:end].lstrip('> '))


AC_RE = re.compile(r'Armor Class (\d+)')
HP_RE = re.compile(r'Hit Points (\d+)')
ATTACK_RE = re.compile(r'([A-Z][A-Za-z\' ]{1,30})\. (?:Melee|Ranged) (?:Weapon|Spell) Attack: \+(\d+) to hit[^.]*?'
                       r'(?:\.[^.]*?)*?Hit: (\d+) \([^)]*\) ([a-z]+) damage')
UNSUPPORTED_RE = re.compile(r'^(Multiattack|Spellcasting|Innate Spellcasting|Legendary Actions?|[A-Z][\w ]*\(Recharge[^)]*\))',
                            re.M)
COUNTS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}
ACTOR_MAX = 6
DISTURB_RE = re.compile(r"anyone who (?:touches|disturbs|opens|moves|takes|reads) (?:the |a |an )?([a-z]+)", re.I)


def stat_block_span(text, entry):
    """(start, end) of the book's stat block: its name through the first blank line after Hit Points."""
    start = entry['offset']
    window = text[start:start + 1600]
    hp = re.search(r'hit points\s+\d+', window, re.I)
    search_from = hp.end() if hp else 0
    rel = window.find('\n\n', search_from)
    end = start + (rel if rel >= 0 else len(window))
    return start, min(len(text), end)


def parse_stat_block(text, entry):
    """(engine stat block, provenance {field: {quote, offset}}, unsupported) from the book's own
    stat block, or (None, {}, reasons) when it lacks AC, hit points or a usable attack. Only
    what the text states: initiative, grapple and saves keep the engine's defaults."""
    start, end = stat_block_span(text, entry)
    block = text[start:end]
    prov, problems = {}, []
    ac, hp = AC_RE.search(block), HP_RE.search(block)
    attacks = []
    for n, m in enumerate(ATTACK_RE.finditer(block)):
        attacks.append({'name': m.group(1).strip().lower(), 'to_hit': int(m.group(2)),
                        'damage': int(m.group(3)), 'type': m.group(4)})
        prov[f'attacks.{n}'] = {'offset': start + m.start(), 'quote': m.group(0)}
    unsupported = [m.group(1) for m in UNSUPPORTED_RE.finditer(block)]
    if not (ac and hp and attacks):
        problems.append('no Armor Class, Hit Points and attack line the engine can use')
        return None, {}, problems + unsupported
    prov['ac'] = {'offset': start + ac.start(), 'quote': ac.group(0)}
    prov['hp'] = {'offset': start + hp.start(), 'quote': hp.group(0)}
    return {'ac': int(ac.group(1)), 'hp': int(hp.group(1)), 'attacks': attacks}, prov, unsupported


def _present(span, name):
    """(count, offset) of the first mention that puts the creature here: a count or article
    before it ("two bandits", "a reed lurker"), or a "(see ...)" right after it. A passing
    mention ("someone called the Lantern Wight") is not a creature present."""
    pattern = rf'\b(?:(a|an|one|two|three|four|five|six|\d)\s+)?(?:the\s+)?({re.escape(name)}(?:e?s)?)\b(\s*\(see)?'
    for m in re.finditer(pattern, span, re.I):
        if m.group(1) or m.group(3):
            word = (m.group(1) or 'one').lower()
            count = int(word) if word.isdigit() else COUNTS.get(word, 1)
            return min(count, ACTOR_MAX), m.start()
    return None


def _creatures(span, base, stat_blocks):
    """Creature references and how each resolves: the book's own stat block, then SRD 5.1,
    else ask the player. Never a made-up stat line."""
    from .srd_creatures import CREATURES
    found = {}
    names = set(stat_blocks) | set(CREATURES)
    for name in sorted(names, key=len, reverse=True):
        for m in re.finditer(rf'\b{re.escape(name)}(?:e?s)?\b', span, re.I):
            found.setdefault(name, base + m.start())
    for m in SEE_RE.finditer(span):
        name = m.group(1).strip().casefold()
        name = re.sub(r'^(?:a|an|the)\s+', '', name)
        found.setdefault(name, base + m.start())
    for m in ELSEWHERE_RE.finditer(span):
        name = re.sub(r'(?<=[^s])s$', '', m.group(1).strip().casefold())
        found.setdefault(name, base + m.start(1))
    out = []
    for name, off in sorted(found.items(), key=lambda kv: kv[1]):
        if name in stat_blocks:
            how = {'resolved': 'in_book', 'offset': stat_blocks[name]['offset']}
        elif name in CREATURES:
            how = {'resolved': 'srd', 'srd': name}
        else:
            how = {'resolved': 'ask_player'}
        out.append({'name': name, 'mention_offset': off, **how})
    return out


def import_adventure(db, text=None, pdf=None, title=None, reader='auto'):
    """Write the private source and its index next to the save. Returns the import report."""
    if text is None and pdf is None:
        raise IngestError(['give --text-file (extracted text) or --pdf'])
    if text is None:
        text, _how = read_pdf(pdf, reader=reader)
    text = prepare_source(text)
    index = build_index(text, title)
    if not index['locations']:
        raise IngestError(['no keyed locations found (headings like "1. Mill Yard" or "Area 3: Cellar")'])
    folder = folder_for(db)
    (folder / 'rooms').mkdir(parents=True, exist_ok=True)
    (folder / 'source.txt').write_text(text, encoding='utf-8')
    _write_json(folder / 'index.json', index)
    return {'stage': 'adventure_imported', 'title': index['title'], 'locations': len(index['locations']),
            'chapters': len(index['chapters']), 'npcs': len(index['npcs']),
            'stat_blocks_in_book': len(index['stat_blocks']), 'map_pages': index['map_pages'],
            'start_location': index['start'], 'folder': str(folder), **readiness(db)}


# ---------------------------------------------------------------- compile

def room_file(db, key):
    return folder_for(db) / 'rooms' / f'{_slug(key)}.json'


def _load(db):
    folder = folder_for(db)
    if not (folder / 'index.json').is_file():
        raise IngestError(['no adventure imported for this save; run adventure import first'])
    return _read_json(folder / 'index.json'), (folder / 'source.txt').read_text(encoding='utf-8')


def _cut(text):
    text = _norm(text)
    if len(text) <= FACT_MAX_CHARS:
        return text
    return text[:FACT_MAX_CHARS].rsplit(' ', 1)[0] + '…'


def _split(span, base):
    """(read_aloud, dm) lists of (offset, sentence) from a location's body."""
    read, dm, at = [], [], 0
    for line in span.split('\n'):
        stripped = line.strip()
        target = read if stripped.startswith('>') else dm
        content = stripped.lstrip('>').strip()
        if content:
            inner = line.find(content)
            for m in SENTENCE_RE.finditer(content):
                s = m.group(0).strip()
                lead = len(m.group(0)) - len(m.group(0).lstrip())
                if len(s) > 1:
                    target.append((base + at + inner + m.start() + lead, s))
        at += len(line) + 1
    return read, dm


def draft_room(db, key, index, text):
    """The deterministic room draft and its provenance for one keyed location."""
    loc = index['locations'].get(key)
    if loc is None:
        raise IngestError([f'no keyed location {key!r} in the index'])
    start, end = loc['body']
    read, dm = _split(text[start:end], start)
    here = 'here'
    called = loc['name'].lower()
    areas = {here: {'name': loc['name'], 'called': called if called.startswith('the ') else 'the ' + called}}
    prov = {'areas.here.name': {'offset': loc['offset'], 'quote': loc['name']}}
    exits, facts, flags = {}, {}, []
    for c in loc['connections']:
        other = index['locations'][c['to']]
        side = f'to_{_slug(c["to"])}'
        areas[side] = {'name': f'Toward {other["name"]}', 'outside': True, 'beyond': True,
                       'room_link': {'room': str(room_file(db, c['to'])), 'area': f'to_{_slug(key)}',
                                     'adventure': {'db': str(db), 'location': c['to']}}}
        exits[f'way_{_slug(c["to"])}'] = {
            'name': f'the way to {other["name"]}', 'areas': [here, side], 'secret': c['secret'],
            'labels': {here: f'The way to {other["name"]}.', side: f'The way back to {loc["name"]}.'}}
        for path in (f'areas.{side}', f'exits.way_{_slug(c["to"])}'):
            prov[path] = {'offset': c['offset'], 'quote': c['quote']}
    for n, (off, sentence) in enumerate(read[:VISIBLE_MAX], 1):
        facts[f'seen_{n}'] = {'area': here, 'visible': True, 'text': _cut(sentence)}
        prov[f'facts.seen_{n}'] = {'offset': off, 'quote': sentence}
    if len(read) > VISIBLE_MAX:
        flags.append(f'{len(read) - VISIBLE_MAX} read-aloud sentences left out (cap {VISIBLE_MAX})')
    if not read:
        flags.append('no read-aloud text found: nothing in this location is player-visible until Kit reveals it')
    used = 0
    for n, (off, sentence) in enumerate(dm, 1):
        cut = _cut(sentence)
        used += len(cut.encode()) + 60
        if used > HIDDEN_BUDGET_BYTES:
            flags.append(f'{len(dm) - n + 1} DM sentences left out to stay inside the room context cap')
            break
        facts[f'dm_{n}'] = {'area': here, 'visible': False, 'text': cut}
        prov[f'facts.dm_{n}'] = {'offset': off, 'quote': sentence}
    if not facts:
        raise IngestError([f'location {key} has no text to compile'])
    page = next((p for p in index['pages'] if p['page'] == loc['page']), None)
    if page and page['needs_map_look']:
        flags.append(f"page {loc['page']} is mostly map/image: look at the map for layout")
    actors, triggers = {}, []
    from .srd_creatures import CREATURES
    for creature in loc['creatures']:
        name = creature['name']
        found = _present(text[start:end], name)
        if creature['resolved'] == 'ask_player' or found is None:
            continue
        count, rel = found
        if creature['resolved'] == 'in_book':
            block, stat_prov, unsupported = parse_stat_block(text, index['stat_blocks'][name])
            if block is None:
                flags.append(f'{name}: book stat block unusable ({"; ".join(unsupported)}); not a combatant')
                continue
            if unsupported:
                flags.append(f'{name}: not run by the engine: {", ".join(unsupported)}')
        elif name in CREATURES:
            block, stat_prov = {'srd': name}, {'srd': {'srd': name}}
        else:
            continue
        mention = _sentence_around(text[start:end], rel)
        # Player-visible only when the read-aloud text names it; otherwise hidden until its trigger.
        seen = any(name.lower() in sentence.lower() for _, sentence in read)
        woken = []
        for n in range(1, count + 1):
            akey = _slug(name) + (f'_{n}' if count > 1 else '')
            actors[akey] = {'name': name.title() if count == 1 else f'{name.title()} {n}', 'location': here,
                            'status': 'alive' if seen else 'hidden', 'visible': seen, 'stat_block': block}
            woken.append(akey)
            prov[f'actors.{akey}'] = {'offset': start + rel, 'quote': mention}
            for field, entry in stat_prov.items():
                prov[f'actors.{akey}.stat_block.{field}'] = entry
        if not seen:
            # The book's own condition when it names a thing here ("attack anyone who touches the
            # ledger"); otherwise the creature shows itself when the PC arrives.
            follow = next((t for o, t in dm if o > start + rel and o - (start + rel) < len(mention) + 3), '')
            follow = follow if re.match(r'(?:They|It|He|She)\b', follow) else ''
            on, cond = {'enter': here}, DISTURB_RE.search(mention + ' ' + follow)
            target = cond and next((fk for fk, fact in facts.items()
                                    if re.search(rf"\b{re.escape(cond.group(1))}\b", fact['text'], re.I)), None)
            if target:
                facts[target].setdefault('handling', {'nouns': [cond.group(1).lower()]})
                prov[f'facts.{target}.handling'] = {'offset': start + rel, 'quote': mention}
                on = {'disturb': target}
            prov[f'triggers.reveal_{_slug(name)}'] = {'offset': start + rel, 'quote': mention}
            triggers.append({'id': f'reveal_{_slug(name)}', 'on': on, 'actors': woken,
                             'reveal': f'{name[0].upper() + name[1:]} reveals itself.' if count == 1
                             else f'{count} {name}s reveal themselves.'})
    room = {'id': f"adv-{index['sha256'][:8]}-{_slug(key)}",
            'source_ref': f"{index['title']} / {key}. {loc['name']} (p. {loc['page']})",
            'starting_area': here, 'areas': areas, 'exits': exits, 'facts': facts, 'actors': actors}
    if triggers:
        room['triggers'] = triggers
    sidecar = {'location': key, 'source_sha256': index['sha256'], 'fields': prov,
               'creatures': loc['creatures'],
               'ask_player': [c['name'] for c in loc['creatures'] if c['resolved'] == 'ask_player'],
               'flags': flags, 'compiled_by': 'deterministic'}
    return room, sidecar


def validate(room, sidecar, index, text):
    """The runtime's checks on any draft, deterministic or model-assisted. Names every
    problem: a field with no source, a quote not in the location's text, a visible fact
    that quotes DM-only text, a fact that leaves its location, or a room the loader refuses."""
    from . import kit_rooms
    problems = []
    loc = index['locations'].get(sidecar.get('location'))
    if loc is None:
        return [f"provenance names no keyed location {sidecar.get('location')!r}"]
    if sidecar.get('source_sha256') != index['sha256']:
        problems.append('provenance is for a different source text')
    span = text[loc['body'][0]:loc['body'][1]]
    flat, flat_read = _norm(span.replace('>', ' ')), _norm(' '.join(
        l.strip().lstrip('>') for l in span.split('\n') if l.strip().startswith('>')))
    conn_quotes = {_norm(c['quote']) for c in loc['connections']}
    fields = sidecar.get('fields') or {}
    must = ['areas.here.name'] + [f'areas.{a}' for a in room.get('areas', {}) if a != 'here'] + \
        [f'exits.{e}' for e in room.get('exits', {})] + [f'facts.{f}' for f in room.get('facts', {})]
    for path in must:
        entry = fields.get(path)
        if not (isinstance(entry, dict) and isinstance(entry.get('quote'), str) and entry['quote'].strip()
                and isinstance(entry.get('offset'), int)):
            problems.append(f'{path} has no source quote and offset')
            continue
        quote = _norm(entry['quote'].lstrip('> '))
        if path == 'areas.here.name':
            if quote != _norm(loc['name']):
                problems.append(f'{path} does not match the location heading')
        elif path.startswith(('areas.', 'exits.')):
            if quote not in conn_quotes:
                problems.append(f'{path} quotes no connection stated in the source')
        elif quote not in flat:
            problems.append(f'{path} quote is not in location {loc["key"]}\'s text')
    for key, fact in (room.get('facts') or {}).items():
        entry = fields.get(f'facts.{key}') or {}
        quote = _norm(str(entry.get('quote', '')).lstrip('> '))
        if not isinstance(fact, dict):
            continue
        if fact.get('area') != 'here':
            problems.append(f'fact {key} must sit in this location')
        if fact.get('visible') and quote and quote not in flat_read:
            problems.append(f'fact {key} is visible but quotes DM-only text (secrets stay hidden)')
        body = _norm(str(fact.get('text', '')).rstrip('…'))
        if quote and body and body not in quote and not _words_from(body, quote):
            problems.append(f'fact {key} text says more than its quote')
    problems += _actor_problems(room, fields, flat, index, text)
    if not problems:
        import warnings
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            try:
                kit_rooms.check_room(json.loads(json.dumps(room)), sidecar.get('location'))
            except kit_rooms.RoomMountError as exc:
                problems += exc.problems
        # Loader warnings (an alarm with no responders the book names) are gaps, not errors:
        # carried as flags so Kit asks rather than invents.
        sidecar.setdefault('flags', []).extend(
            str(w.message).split(': ', 1)[-1] for w in caught if issubclass(w.category, kit_rooms.RoomWarning))
    return problems


def _actor_problems(room, fields, flat, index, text):
    """Every combatant is sourced: its presence quotes this location, and every stat quotes the
    book's own stat block for it (and states that number) or names an SRD creature the runtime ships."""
    from .srd_creatures import CREATURES
    problems = []
    for key, actor in (room.get('actors') or {}).items():
        where = fields.get(f'actors.{key}') or {}
        if not (isinstance(where.get('quote'), str) and _norm(where['quote']) in flat):
            problems.append(f'actors.{key} has no source quote in this location')
        block = actor.get('stat_block') if isinstance(actor, dict) else None
        if not isinstance(block, dict):
            problems.append(f'actors.{key} has no stat_block')
            continue
        if set(block) == {'srd'}:
            if str(block['srd']).casefold() not in CREATURES or \
                    (fields.get(f'actors.{key}.stat_block.srd') or {}).get('srd') != block['srd']:
                problems.append(f'actors.{key} stat_block cites no SRD creature the runtime ships')
            continue
        entry = index['stat_blocks'].get(str(actor.get('name', '')).rstrip(' 0123456789').strip().casefold())
        if entry is None:
            problems.append(f'actors.{key} has inline stats but the book has no stat block named {actor.get("name")!r}')
            continue
        lo, hi = stat_block_span(text, entry)
        book = _norm(text[lo:hi])
        checks = [('ac', block.get('ac')), ('hp', block.get('hp'))] + \
            [(f'attacks.{n}', a) for n, a in enumerate(block.get('attacks') or [])]
        extra = set(block) - {'ac', 'hp', 'attacks'}
        if extra:
            problems.append(f'actors.{key} stat_block has unsourced fields: {", ".join(sorted(extra))}')
        for field, value in checks:
            quote = _norm(str((fields.get(f'actors.{key}.stat_block.{field}') or {}).get('quote', '')))
            if not quote or quote not in book:
                problems.append(f'actors.{key}.stat_block.{field} has no source quote in its stat block')
                continue
            numbers = [value] if isinstance(value, int) else \
                [value.get('to_hit'), value.get('damage')] if isinstance(value, dict) else [None]
            if not all(isinstance(v, int) and re.search(rf'(?<![\d]){v}(?![\d])', quote) for v in numbers):
                problems.append(f'actors.{key}.stat_block.{field} states a number its quote does not')
    return problems


def _words_from(body, quote):
    """A paraphrase may only reuse the quote's own words (no new nouns or numbers)."""
    words = lambda s: set(re.findall(r"[a-z0-9']+", s.casefold()))  # noqa: E731
    return words(body) <= words(quote)


def _canon_key(key, locations):
    text = str(key)
    if text in locations:
        return text
    folded = {name.casefold(): name for name in locations}
    found = folded.get(text.casefold())
    if found:
        return found
    upper = text.upper()
    return upper if upper in locations else text


def compile_location(db, key, draft=None, neighbours=True):
    """Compile (or accept a host draft for) one location, validate it, cache it. Then
    pre-compile the locations it connects to, so the next move is already executable."""
    index, text = _load(db)
    key = _canon_key(key, index['locations'])
    clock = time.perf_counter()
    if draft is None:
        room, sidecar = draft_room(db, key, index, text)
    else:
        room, sidecar = draft.get('room'), draft.get('provenance')
        if not (isinstance(room, dict) and isinstance(sidecar, dict)):
            raise IngestError(['a draft is {"room": {...}, "provenance": {"location", "source_sha256", "fields"}}'])
        sidecar = {**sidecar, 'location': key, 'compiled_by': 'host_draft'}
    problems = validate(room, sidecar, index, text)
    if problems:
        raise IngestError(problems)
    path = room_file(db, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, room)
    scene_ms = round((time.perf_counter() - clock) * 1000, 3)
    scene_bytes = path.stat().st_size
    loc = index['locations'].get(key) or {}
    sidecar['page'] = loc.get('page')
    sidecar['scene_ms'] = scene_ms
    sidecar['scene_bytes'] = scene_bytes
    _write_json(path.with_suffix('.provenance.json'), sidecar)
    precompiled = []
    if neighbours:
        for c in index['locations'][key]['connections']:
            if not room_file(db, c['to']).is_file():
                try:
                    compile_location(db, c['to'], neighbours=False)
                    precompiled.append(c['to'])
                except IngestError:
                    pass
    return {'stage': 'location_compiled', 'location': key, 'room': str(path), 'room_id': room['id'],
            'compiled_by': sidecar['compiled_by'], 'precompiled': precompiled,
            'page': sidecar.get('page'), 'scene_ms': scene_ms, 'scene_bytes': scene_bytes,
            'ask_player': sidecar.get('ask_player', []), 'flags': sidecar.get('flags', []), **readiness(db)}


def ingest_adventure(db, text=None, pdf=None, title=None, reader='auto'):
    """One host step: a PDF or pasted text -> the private index and the first scene.

    Later scenes compile when play reaches them (``ensure_compiled``). The report carries
    ingest and first-scene time in milliseconds, the byte sizes, the page of the first
    scene, and ``next_command`` — what to run when the player says begin.
    """
    if text is None and pdf is None:
        raise IngestError(['ingest needs a PDF path or --text-file'])
    if text is not None and pdf is not None:
        raise IngestError(['give a PDF or --text-file, not both'])
    clock = time.perf_counter()
    how = 'text'
    if text is None:
        text, how = read_pdf(pdf, reader=reader)
    report = import_adventure(db, text=text, title=title)
    ingest_ms = round((time.perf_counter() - clock) * 1000, 3)
    compiled = compile_location(db, report['start_location'], neighbours=False)
    room_body = _read_json(compiled['room'])
    visible = [fact for fact in (room_body.get('facts') or {}).values()
               if isinstance(fact, dict) and fact.get('visible') and str(fact.get('text') or '').strip()]
    if not visible:
        Path(compiled['room']).unlink()
        side = Path(compiled['room']).with_suffix('.provenance.json')
        if side.is_file():
            side.unlink()
        raise IngestError(['the first scene has no player-visible read-aloud; refusing an opening that would '
                           'only say "The newcomer arrives". Mark the boxed, italic, or indented text, '
                           'or pass text whose read-aloud lines start with "> "'])
    import shlex
    q = shlex.quote(str(db))
    room = shlex.quote(compiled['room'])
    return {
        'stage': 'adventure_ingested', 'reader': how, 'title': report['title'],
        'locations': report['locations'], 'chapters': report['chapters'],
        'start_location': report['start_location'], 'start_room': compiled['room'],
        'room_id': compiled['room_id'], 'first_scene_page': compiled.get('page'),
        'ingest_ms': ingest_ms, 'first_scene_ms': compiled['scene_ms'],
        'source_bytes': (folder_for(db) / 'source.txt').stat().st_size,
        'index_bytes': (folder_for(db) / 'index.json').stat().st_size,
        'first_scene_bytes': compiled['scene_bytes'],
        'next_command': (f'python3 -m runtime.kit_agent start --db {q} --room {room} '
                         '--sheet <sheet.json>'),
        'begin': ('When the player says begin, run next_command with their sheet. '
                  'The next scene compiles on arrival; do not hand-build rooms.'),
        'ask_player': compiled.get('ask_player', []), 'flags': compiled.get('flags', []),
        **readiness(db),
    }


def ensure_compiled(link):
    """Loader hook: a room_link into an adventure location whose room is not cached yet is
    compiled now (deterministically), so moving on never needs the host to engineer it."""
    meta = link.get('adventure') if isinstance(link, dict) else None
    if not isinstance(meta, dict) or Path(link['room']).is_file():
        return
    try:
        compile_location(meta['db'], meta['location'])
    except (IngestError, OSError, KeyError):
        pass  # the loader then reports the missing room in its plain way


# ---------------------------------------------------------------- readiness

def readiness(db, mounted_id=None):
    """none / source_available / location_executable / campaign_playable.

    campaign_playable: the mounted room is a compiled location and every location it
    connects to is compiled too (the next move is executable)."""
    folder = folder_for(db)
    if not (folder / 'index.json').is_file():
        return {'adventure_readiness': 'none'}
    index = _read_json(folder / 'index.json')
    compiled = sorted(k for k in index['locations'] if room_file(db, k).is_file())
    out = {'adventure_title': index['title'], 'locations_total': len(index['locations']),
           'locations_compiled': compiled, 'map_pages': index['map_pages'],
           'start_room': str(room_file(db, index['start'])) if index['start'] in compiled else None}
    if not compiled:
        level = 'source_available'
        out['adventure_next'] = (f'python3 -m runtime.kit_agent adventure compile --db {db} '
                                 f'--location {index["start"]}')
    else:
        level = 'location_executable'
        here = next((k for k in compiled if mounted_id and _read_json(room_file(db, k)).get('id') == mounted_id), None)
        if here and all(room_file(db, c['to']).is_file() for c in index['locations'][here]['connections']):
            level = 'campaign_playable'
        out['mounted_location'] = here
    out['adventure_readiness'] = level
    return out


# ---------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(prog='kit_agent adventure', description=__doc__.split('\n\n')[0])
    parser.add_argument('action', choices=['import', 'compile', 'status', 'ingest'])
    parser.add_argument('path', nargs='?', help='ingest: the adventure PDF (or pass --pdf)')
    parser.add_argument('--db', default='kit.sqlite')
    parser.add_argument('--text-file', help='import/ingest: the adventure as UTF-8 text (form feed between pages; '
                                             'boxed read-aloud lines prefixed "> ")')
    parser.add_argument('--pdf', help='import/ingest: a PDF. The built-in reader uses the text layer; '
                                      'pdftotext or pypdf run only when that reader cannot')
    parser.add_argument('--reader', choices=['auto', 'stdlib', 'pdftotext', 'pypdf'], default='auto',
                        help='PDF reader. auto uses the built-in text layer, then pdftotext, then pypdf')
    parser.add_argument('--title')
    parser.add_argument('--location', help='compile: the location key, e.g. 1 or A2')
    parser.add_argument('--draft-file', help='compile: a host-model draft {"room", "provenance"} to validate')
    args = parser.parse_args(argv)
    try:
        if args.action == 'import':
            text = Path(args.text_file).read_text(encoding='utf-8') if args.text_file else None
            result = import_adventure(args.db, text=text, pdf=args.pdf, title=args.title, reader=args.reader)
        elif args.action == 'ingest':
            pdf = args.pdf or args.path
            if args.text_file and pdf:
                raise IngestError(['give a PDF or --text-file, not both'])
            text = Path(args.text_file).read_text(encoding='utf-8') if args.text_file else None
            if text is None and not pdf:
                raise IngestError(['ingest needs a PDF path or --text-file'])
            result = ingest_adventure(args.db, text=text, pdf=pdf, title=args.title, reader=args.reader)
        elif args.action == 'compile':
            if not args.location:
                raise IngestError(['compile needs --location'])
            draft = _read_json(args.draft_file) if args.draft_file else None
            result = compile_location(args.db, args.location, draft=draft)
        else:
            from . import kit_lifecycle
            result = {'stage': 'adventure_status', **readiness(args.db, kit_lifecycle.mounted_room_id(args.db))}
    except IngestError as exc:
        print(json.dumps({'stage': 'rejected', 'committed': False, 'problems': exc.problems},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
