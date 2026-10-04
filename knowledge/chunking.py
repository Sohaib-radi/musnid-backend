"""
Chunking of extracted questions (docs/rag/02-pipeline.md).

Per question:

* one ``question`` chunk: title, question and alternative phrasings. It
  matches how people ask; it is used for finding only, never as evidence;
* one ``summary`` chunk: the title and the short answer;
* ``answer`` chunks: each answer section (content, detailed, conclusion)
  split on paragraph boundaries into pieces of about ``TARGET_WORDS`` words,
  each prefixed with the title so it stands alone.
"""

from dataclasses import dataclass, field

TARGET_WORDS = 400
ANSWER_SECTIONS = ['content', 'detailed', 'conclusion']


@dataclass
class ChunkSpec:
    """A chunk to be embedded and stored."""

    question_number: int
    kind: str
    title: str
    text: str
    metadata: dict = field(default_factory=dict)


def split_words(text, target=TARGET_WORDS):
    """
    Split ``text`` into pieces of at most about ``target`` words.

    Paragraphs (newline-separated) are kept whole when they fit; a paragraph
    longer than ``target`` is cut on word boundaries.
    """
    pieces, current = [], []
    for paragraph in filter(None, (p.strip() for p in text.split('\n'))):
        words = paragraph.split()
        while len(words) > target:
            if current:
                pieces.append(current)
                current = []
            pieces.append(words[:target])
            words = words[target:]
        if current and len(current) + len(words) > target:
            pieces.append(current)
            current = []
        current = current + (['\n'] if current else []) + words
    if current:
        pieces.append(current)
    return [' '.join(piece).replace(' \n ', '\n') for piece in pieces]


def chunk_question(question):
    """Return the ``ChunkSpec`` list of one extracted question dict."""
    number, title = question['number'], question['title']
    base = {'part': question['part'], 'chapter': question['chapter'],
            'page_start': question['page_start'], 'page_end': question['page_end']}
    finding = '\n'.join(filter(None, [title, question['question'], *question['alternative_phrasings']]))
    chunks = [ChunkSpec(number, 'question', title, finding, {**base})]
    if question['answer_summary']:
        chunks.append(ChunkSpec(number, 'summary', title, f'{title}\n{question["answer_summary"]}',
                                {**base, 'section': 'summary', 'position': 0}))
    position = 0
    for section in ANSWER_SECTIONS:
        for piece in split_words(question['answer_sections'].get(section, '')):
            position += 1
            chunks.append(ChunkSpec(number, 'answer', title, f'{title}\n{piece}',
                                    {**base, 'section': section, 'position': position}))
    return chunks
