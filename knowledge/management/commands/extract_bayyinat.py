"""
Extract the Bayyinat PDF into data/processed/bayyinat_ar.json.

Requires PyMuPDF from requirements-tools.txt (AGPL-3.0, never installed in
Docker or production); it is imported here only, inside ``handle``.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from knowledge.extraction import bayyinat
from knowledge.extraction.text import QURAN_MARK, group_lines, order_line, line_text

HEADER_BOTTOM = 45.0  # points from the top: running header (page number, book title)
DROPPED_FONTS = ('icomoon', 'zkhref', 'Arabesque')  # decorations
HONORIFIC_FONT = 'KFGQPCArabicSymbols'  # honorific glyphs: removed (ﷺ kept)
QURAN_FONT = 'QCF'  # Quran text as private-use glyphs: replaced by [آية]
BULLET = '3'


class Command(BaseCommand):
    help = 'Extract the Bayyinat questions from data/raw/bayyinat_ar.pdf into JSON.'

    def add_arguments(self, parser):
        parser.add_argument('--pdf', default=str(settings.BASE_DIR / 'data' / 'raw' / 'bayyinat_ar.pdf'))
        parser.add_argument('--out', default=str(settings.BASE_DIR / 'data' / 'processed' / 'bayyinat_ar.json'))

    def handle(self, *args, **options):
        try:
            import pymupdf
        except ImportError as error:
            raise CommandError('PyMuPDF is missing: pip install -r requirements-tools.txt') from error
        document = pymupdf.open(options['pdf'])
        lines = []
        for number in range(document.page_count):
            lines.extend(page_lines(document[number], number))
        questions = bayyinat.parse(lines)
        out = Path(options['out'])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(questions, ensure_ascii=False, indent=1), encoding='utf-8')
        self.stdout.write(f'{len(questions)} questions written to {out}')
        warnings = bayyinat.validate(questions)
        for warning in warnings:
            self.stdout.write(self.style.WARNING(warning))
        self.stdout.write(f'{len(warnings)} warnings')


def font_class(span):
    """Classify a span by font: title, label, manal, quran, honorific, drop or body."""
    font = span['font']
    if any(name in font for name in DROPPED_FONTS):
        return 'drop'
    if HONORIFIC_FONT in font:
        return 'honorific'
    if QURAN_FONT in font:
        return 'quran'
    if 'AbdoLine' in font:
        return 'title'
    if 'DINNext' in font:
        return 'label'
    if 'Manal' in font:
        return 'manal'
    return 'body'


def page_chars(page):
    """Positioned characters of a page, header and decorations removed."""
    chars = []
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                cls = font_class(span)
                if cls == 'drop':
                    continue
                for char in span['chars']:
                    x0, y0, x1, _y1 = char['bbox']
                    if y0 < HEADER_BOTTOM:
                        continue
                    c = char['c']
                    if cls == 'honorific' and c != 'ﷺ':
                        continue
                    if cls == 'quran':
                        c = QURAN_MARK
                    chars.append({'c': c, 'x0': x0, 'x1': x1, 'y': char['origin'][1],
                                  'cls': cls, 'size': span['size']})
    return chars


def page_lines(page, number):
    """Classified ``bayyinat.Line`` objects of a page, top to bottom."""
    result = []
    pending_bullet = False  # a bullet glyph on its own baseline marks the next line
    for chars in group_lines(page_chars(page)):
        classes = {char['cls'] for char in chars if char['c'].strip()}
        if 'title' in classes:
            # Everything but the "المسألة (n)" label, so a ﷺ set in a body font stays.
            title = [char for char in chars if char['cls'] != 'manal']
            result.append(bayyinat.Line(number, chars[0]['y'], 'title', line_text(title)))
            continue
        if 'label' in classes:
            result.append(bayyinat.Line(number, chars[0]['y'], 'label', line_text(chars)))
            continue
        ordered = order_line(chars)
        visible = [char for char in ordered if char['c'].strip()]
        if len(visible) == 1 and visible[0]['c'] == BULLET:
            pending_bullet = True
            continue
        bullet = bool(visible) and visible[0]['c'] == BULLET and visible[0]['cls'] in ('manal', 'body') \
            and len(visible) > 1 and visible[0]['size'] >= 15
        if bullet:
            chars = [char for char in chars if char is not visible[0]]
        manal = [char for char in chars if char['cls'] == 'manal' and char['c'].strip()]
        kind = 'body'
        if manal and len(manal) * 2 >= len([c for c in chars if c['c'].strip()]):
            size = max(char['size'] for char in manal)
            if size >= 20:
                kind = 'part'
            elif size >= 16 and any('ء' <= char['c'] <= 'ي' for char in manal):
                kind = 'chapter'
            else:
                kind = 'sublabel'
        text = line_text(chars)
        if text:
            result.append(bayyinat.Line(number, chars[0]['y'], kind, text, bullet or pending_bullet))
            pending_bullet = False
    return result
