"""
Arabic normalization for retrieval (stored in ``SourceChunk.text_norm`` and
applied to queries; never to the text shown to people).

Follows the direction of Lucene's ``ArabicNormalizer``:

* ALEF WITH MADDA ABOVE, ALEF WITH HAMZA ABOVE, ALEF WITH HAMZA BELOW -> ALEF
  (plus ALEF WASLA, frequent in Quranic text: an extension of Lucene's list);
* TEH MARBUTA -> HEH;
* ALEF MAKSURA -> YEH;
* TATWEEL removed;
* harakat removed: FATHATAN, DAMMATAN, KASRATAN, FATHA, DAMMA, KASRA, SHADDA,
  SUKUN (plus SUPERSCRIPT ALEF, an extension).
"""

import re

_TABLE = str.maketrans({
    'آ': 'ا',  # ALEF WITH MADDA ABOVE
    'أ': 'ا',  # ALEF WITH HAMZA ABOVE
    'إ': 'ا',  # ALEF WITH HAMZA BELOW
    'ٱ': 'ا',  # ALEF WASLA
    'ة': 'ه',  # TEH MARBUTA -> HEH
    'ى': 'ي',  # ALEF MAKSURA -> YEH
    'ـ': None,      # TATWEEL
    **{chr(code): None for code in range(0x064B, 0x0653)},  # FATHATAN .. SUKUN
    'ٰ': None,      # SUPERSCRIPT ALEF
})
_SPACES = re.compile(r'\s+')


def normalize(text):
    """Return ``text`` normalized for matching (see the module docstring)."""
    return _SPACES.sub(' ', text.translate(_TABLE)).strip()
