"""
The competition's official glossary as a knowledge source (docs/rag/07-official-glossary.md).

Terms come from the official reference document («المرجعية والحزمة العلمية والبيانات -
محدث», page 7, «نماذج قاموس المصطلحات الأساسية»). Each term is one chunk of kind
``glossary``, searched separately from Bayyinat and given to the writer first when it
matches (``agents.flow``). Glossary chunks use reserved numbers from
``FIRST_NUMBER`` so ``[Q<n>]`` citations never collide with Bayyinat questions (1-263).
"""

from django.db import transaction

from knowledge.models import SourceChunk, SourceDocument
from knowledge.normalize import normalize

SLUG = 'official-glossary'
TITLE = 'المرجعية العلمية للتحدي — نماذج قاموس المصطلحات الأساسية (ص 7)'
LICENSE_NOTE = ("From the competition's official reference document "
                '(المرجعية والحزمة العلمية والبيانات - محدث), page 7')
#: Prefix of a glossary source's label shown to askers: «<prefix>: <term>» (the document's own title)
CITATION_PREFIX = 'نماذج قاموس المصطلحات الأساسية'
#: First reserved question number of glossary chunks (Bayyinat ends at 263)
FIRST_NUMBER = 9001

#: (term, English equivalent, rule), in the document's order
TERMS = [
    ('الإسلام', 'Islam',
     'دين الاستسلام لله بالتوحيد والانقياد له بالطاعة، ويُشرح بحسب السياق ولا يُختزل في معنى ثقافي عام.'),
    ('التوحيد', 'Tawhid / Oneness of God',
     'يُفضَّل إبقاء المصطلح مع شرح معناه: إفراد الله بالربوبية والألوهية، ووصفه بما جاء به الوحي من '
     'أسمائه الحسنى؛ ولا يُختزل في ترجمة قد توحي بمجرد الوحدانية العددية.'),
    ('العبادة', 'Worship',
     'تشمل أعمال القلب والقول والعمل التي يتقرب بها العبد إلى الله، ولا تُحصر في الشعائر فقط.'),
    ('النبوة', 'Prophethood',
     'تُستخدم للدلالة على اصطفاء الأنبياء بالوحي، مع التمييز بينها وبين القيادة الدينية البشرية.'),
    ('الوحي', 'Revelation',
     'يُشرح بوصفه ما أوحاه الله إلى أنبيائه، مع تجنب استعمالات فضفاضة قد توهم الإلهام الشخصي.'),
    ('الشريعة', 'Sharia / Islamic law and guidance',
     'تُشرح بحسب السياق، ولا تُختزل في العقوبات أو القانون الجنائي.'),
    ('الحديث', 'Hadith',
     'ما نُقل عن النبي ﷺ من قول أو فعل أو تقرير ونحو ذلك، مع بيان درجة الثبوت عند الاستدلال.'),
    ('السنة', 'Sunnah',
     'هدي النبي ﷺ وطريقته، ويُحدَّد المقصود بحسب السياق العلمي.'),
    ('الفتوى', 'Fatwa',
     'جواب شرعي يصدره مؤهل في واقعة أو سؤال؛ ولا يُساوى بالمعلومة العامة.'),
    ('الدعوة', "Da'wah / Invitation to Islam",
     'التعريف بالإسلام والدعوة إليه بالحكمة، ويُختار المقابل بحسب السياق والجمهور.'),
]


def chunk_text(term, english, rule):
    """The chunk text: «<term> (<english>): <rule>»."""
    return f'{term} ({english}): {rule}'


def citation_label(term):
    """What askers see as the source of a sentence from the glossary."""
    return f'{CITATION_PREFIX}: {term}'


def ingest_glossary(embedder):
    """
    Store the glossary as the document ``SLUG``, one embedded chunk per term; return the chunk count.

    Idempotent: the document is updated and its chunks replaced in one transaction, after
    the embeddings were computed (a failed embedding call changes nothing).
    """
    texts = [chunk_text(*entry) for entry in TERMS]
    normalized = [normalize(text) for text in texts]
    vectors = embedder.embed(normalized)
    if len(vectors) != len(texts):
        raise ValueError(f'expected {len(texts)} embeddings, got {len(vectors)}')
    with transaction.atomic():
        document, _created = SourceDocument.objects.update_or_create(
            slug=SLUG, defaults={'title': TITLE, 'lang': 'ar', 'url': '', 'pdf_url': '',
                                 'license_note': LICENSE_NOTE})
        document.chunks.all().delete()
        SourceChunk.objects.bulk_create([
            SourceChunk(document=document, question_number=FIRST_NUMBER + index, kind=SourceChunk.Kind.GLOSSARY,
                        lang='ar', title=term, text=text, text_norm=norm, embedding=vector,
                        metadata={'term': term, 'english': english})
            for index, ((term, english, _rule), text, norm, vector) in enumerate(zip(TERMS, texts, normalized,
                                                                                      vectors))
        ])
    return len(texts)
