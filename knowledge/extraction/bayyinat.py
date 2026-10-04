"""
Parsing "Bayyinat" (selected questions about Islam) into questions.

Input: the pages' lines, each a ``Line`` built by the extraction command from
positioned characters. The book's structure is carried by fonts
(docs/rag/01-extraction-findings.md):

* AbdoLine: question title (one per question);
* DINNext: the labels "السؤال" (question) and "الجواب" (answer);
* (AH)-Manal-High: part (>= 20pt), chapter (16-18pt with letters) and section
  labels (13-15pt) such as "مختصر الإجابة";
* body fonts: everything else.

Questions are numbered by order (1..263): the printed "المسألة (n)" labels
are too garbled by the PDF to be read reliably.
"""

import re
from dataclasses import dataclass, field

EXPECTED_QUESTIONS = 263
PARAGRAPH_GAP = 26.0  # points between baselines; body lines are about 22-23 apart

# Section labels (diacritics removed) mapped to answer_sections keys.
SECTION_LABELS = [
    ('عبارات مشابهة', 'alternatives'),
    ('مضمون السؤال', 'content'),
    ('مختصر الإجابة', 'summary'),
    ('مختصر الجواب', 'summary'),
    ('الجواب التفصيلي', 'detailed'),
    ('خاتمة الجواب', 'conclusion'),
]
ANSWER_SECTIONS = ['content', 'summary', 'detailed', 'conclusion']
DIACRITICS = re.compile(r'[ً-ْـ]')


@dataclass
class Line:
    """One reconstructed line of a page."""

    page: int
    y: float
    kind: str  # title, label, part, chapter, sublabel, body
    text: str
    bullet: bool = False


@dataclass
class Question:
    """A question being assembled."""

    number: int
    part: str
    chapter: str
    title: str
    page_start: int
    page_end: int
    parts: dict = field(default_factory=dict)  # section -> list of paragraphs
    alternatives: list = field(default_factory=list)

    def as_dict(self):
        """The JSON object of the question (see docs/rag/02-pipeline.md)."""
        sections = {key: '\n'.join(self.parts[key]) for key in ANSWER_SECTIONS if self.parts.get(key)}
        return {
            'number': self.number,
            'part': self.part,
            'chapter': self.chapter,
            'title': self.title,
            'question': ' '.join(self.parts.get('question', [])),
            'alternative_phrasings': self.alternatives,
            'keywords': [],
            'answer_sections': sections,
            'answer_summary': sections.get('summary', ''),
            'page_start': self.page_start,
            'page_end': self.page_end,
        }


def plain(text):
    """Text without diacritics or tatweel, for matching labels."""
    return DIACRITICS.sub('', text)


def section_for(label):
    """The section key for a section label, or None (e.g. the "المسألة" label)."""
    bare = plain(label)
    for prefix, key in SECTION_LABELS:
        if prefix in bare:
            return key
    return None


def parse(lines):
    """
    Assemble questions from lines in reading order.

    Returns:
        A list of question dicts (``Question.as_dict``).
    """
    questions, current = [], None
    part = chapter = ''
    section, previous = None, None
    for line in lines:
        if line.kind == 'part':
            part, chapter = line.text, ''
            continue
        if line.kind == 'chapter':
            chapter = line.text
            continue
        if line.kind == 'title':
            if previous is not None and previous.kind == 'title' and current is not None:
                current.title = f'{current.title} {line.text}'
            else:
                current = Question(len(questions) + 1, part, chapter, line.text, line.page, line.page)
                questions.append(current)
                section = None
            previous = line
            continue
        if current is None:
            continue  # front matter before the first question
        current.page_end = line.page
        if line.kind == 'label':
            section = 'question' if plain(line.text).startswith('السؤال') else 'answer'
        elif line.kind == 'sublabel':
            section = section_for(line.text) or section
        elif line.kind == 'body' and section:
            _add_body(current, section, line, previous)
        previous = line
    return [question.as_dict() for question in questions]


def _add_body(question, section, line, previous):
    if section == 'alternatives':
        if line.bullet or not question.alternatives:
            question.alternatives.append(line.text)
        else:
            question.alternatives[-1] = f'{question.alternatives[-1]} {line.text}'
        return
    paragraphs = question.parts.setdefault(section, [])
    same_page = previous is not None and previous.page == line.page
    gap = line.y - previous.y if same_page else 0
    if not paragraphs or line.bullet or gap > PARAGRAPH_GAP or previous.kind != 'body':
        paragraphs.append(line.text)
    else:
        paragraphs[-1] = f'{paragraphs[-1]} {line.text}'


def validate(questions):
    """
    Return warnings about the extracted questions (empty when all is well).

    Checks: the number of questions, and per question an empty title,
    question or summary, no alternative phrasings, and residual unrepaired
    ligature patterns.
    """
    warnings = []
    if len(questions) != EXPECTED_QUESTIONS:
        warnings.append(f'expected {EXPECTED_QUESTIONS} questions, found {len(questions)}')
    for q in questions:
        for name in ('title', 'question', 'answer_summary'):
            if not q[name]:
                warnings.append(f'question {q["number"]}: empty {name}')
        if not q['alternative_phrasings']:
            warnings.append(f'question {q["number"]}: no alternative phrasings')
        if 'detailed' not in q['answer_sections']:
            warnings.append(f'question {q["number"]}: no detailed answer')
        body = ' '.join([q['title'], q['question'], *q['answer_sections'].values()])
        # Unrepaired lam-alef leaves two adjacent alefs ("اإل" for "الإ").
        if re.search(r'[اأإآ][اأإآ]', body) or 'هلل' in body:
            warnings.append(f'question {q["number"]}: possible unrepaired ligature')
    return warnings
