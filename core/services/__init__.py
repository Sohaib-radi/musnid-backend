"""
Service functions: business rules that span several objects.

Single-object behaviour belongs on the model or its queryset. A rule that
must look at other rows (for example "a center keeps at least one admin")
lives here, runs in a transaction and raises ``ValidationError`` with a code.
"""
