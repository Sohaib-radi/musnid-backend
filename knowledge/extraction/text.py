"""
Turning positioned PDF characters into logical Arabic text.

The Bayyinat PDF stores characters in a visual, partly scrambled order, so
lines are rebuilt from character positions (right to left), then repaired:

* lam-alef ligatures: the alef of a ligature comes out with zero width just
  before the lam ("اإليمان" for "الإيمان"); a zero-width alef followed by
  lam is swapped back;
* the Allah ligature comes out as "هللا" (titles) or "هلل" (body) and is
  restored to "الله" / "لله";
* tanween-alef: the alef carrying fathatan is lost ("أولً" for "أولًا");
* digits and Latin runs, reversed by the right-to-left ordering, are
  reversed back; mirrored brackets are swapped.

Measured evidence for each rule: docs/rag/01-extraction-findings.md.
"""

import re

ALEF_FORMS = 'اأإآ'
LAM = 'ل'
FATHATAN = 'ً'
QURAN_MARK = '\x00'  # placeholder for a run of Quran glyphs, rendered as [آية]
QURAN_PLACEHOLDER = '[آية]'

# Fathatan is written on alef except after these letters (ة, ى, ء and alef itself).
NO_ALEF_AFTER = set('ةىءا')
LTR_RUN = re.compile(r'[0-9A-Za-z٠-٩](?:[0-9A-Za-z٠-٩./:\-]*[0-9A-Za-z٠-٩])?')
MIRRORED = str.maketrans('()[]«»', ')(][»«')


def is_zero_width(char):
    """True for a character box without width (combining marks, ligature parts)."""
    return char['x1'] - char['x0'] < 0.05


def group_lines(chars, tolerance=2.5):
    """
    Group characters into lines by baseline, top to bottom.

    Args:
        chars: dicts with ``c``, ``x0``, ``x1``, ``y`` (baseline) and ``font``.
        tolerance: maximum baseline difference within one line, in points.
    """
    lines = []
    for char in sorted(chars, key=lambda ch: ch['y']):
        if lines and abs(char['y'] - lines[-1][0]['y']) <= tolerance:
            lines[-1].append(char)
        else:
            lines.append([char])
    return lines


def order_line(line):
    """Order a line's characters right to left (stable for equal positions)."""
    indexed = list(enumerate(line))
    indexed.sort(key=lambda item: (-(item[1]['x0'] + item[1]['x1']) / 2, item[0]))
    return [char for _index, char in indexed]


def repair_ligatures(chars):
    """Swap a zero-width alef that precedes a lam (lam-alef ligature) back after it."""
    chars = list(chars)
    i = 0
    while i < len(chars) - 1:
        if chars[i]['c'] in ALEF_FORMS and is_zero_width(chars[i]) and chars[i + 1]['c'] == LAM:
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
            i += 2
        else:
            i += 1
    return chars


def fix_text(text):
    """Text-level repairs: Allah ligature, tanween-alef, LTR runs, brackets, spaces."""
    # Two forms of the Allah ligature: fully reversed (title font) and without its alef (body).
    text = text.replace('هللا', 'الله').replace('هلل', 'لله')
    # Two consecutive lam-alef ligatures after a shadda keep one alef out of place
    # ("الدَّلاالت" for "الدَّلالات"); inside a word "لاال" never occurs genuinely.
    text = re.sub(r'(?<=\S)لاال', 'لالا', text)
    # Fathatan, possibly followed by marks (matched possessively so the lookahead cannot
    # backtrack into them), not followed by alef or alef maqsura.
    text = re.sub(
        f'([^{"".join(NO_ALEF_AFTER)}\\s])({FATHATAN}[\u0651\u064c-\u0652]*+)(?![اى])', r'\1\2ا', text,
    )
    text = LTR_RUN.sub(lambda match: match.group(0)[::-1], text)
    text = text.translate(MIRRORED)
    text = re.sub(f'(?:{QURAN_MARK}[\\s{QURAN_MARK}]*)+', f' {QURAN_PLACEHOLDER} ', text)
    return re.sub(r'\s+', ' ', text).strip()


def line_text(chars):
    """Logical text of one line of characters."""
    ordered = repair_ligatures(order_line(chars))
    return fix_text(''.join(char['c'] for char in ordered))
