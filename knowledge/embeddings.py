"""
Text embeddings.

``OpenAIEmbedder`` calls the OpenAI embeddings endpoint with the standard
library (no SDK dependency). The key comes from
``core.services.credentials.get_openai_key()`` and is never logged or put in
an error message. Tests use a fake embedder with the same ``embed`` method.
"""

import json
import urllib.error
import urllib.request

from django.views.decorators.debug import sensitive_variables

from core.services import credentials

MODEL = 'text-embedding-3-small'
ENDPOINT = 'https://api.openai.com/v1/embeddings'
BATCH_SIZE = 100


class EmbeddingError(RuntimeError):
    """The provider refused or failed; the message never contains the key."""


class OpenAIEmbedder:
    """Embeds texts with OpenAI ``text-embedding-3-small`` (1536 dimensions)."""

    model = MODEL

    def embed(self, texts):
        """Return one vector per text, in order, calling the API by batches of 100."""
        vectors = []
        for start in range(0, len(texts), BATCH_SIZE):
            vectors.extend(self._embed_batch(texts[start:start + BATCH_SIZE]))
        return vectors

    @sensitive_variables('key', 'request')
    def _embed_batch(self, batch):
        key = credentials.get_openai_key()
        if not key:
            raise EmbeddingError('No OpenAI API key: add one in the admin (Configuration > API Keys).')
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps({'model': self.model, 'input': batch}).encode(),
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            raise EmbeddingError(f'OpenAI embeddings request failed with HTTP {error.code}.') from None
        except urllib.error.URLError as error:
            raise EmbeddingError(f'OpenAI embeddings request failed: {error.reason}.') from None
        return [item['embedding'] for item in sorted(payload['data'], key=lambda item: item['index'])]
