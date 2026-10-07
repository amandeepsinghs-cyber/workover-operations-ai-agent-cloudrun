"""Stage O: synthetic PDF document corpus D1-D11 (SDD §10, F-10, F-14).

Pipeline (run from ``backend/``)::

    uv run python -m app.analytics.docs_pdf.render --field all
    uv run python -m app.analytics.docs_pdf.scanify --fraction 0.10 --types D1,D5
    uv run python -m app.analytics.docs_pdf.validate
    uv run python -m app.analytics.docs_pdf.index

Fact-slot rule: template text (headings, labels, prose, table headers) may not
contain a digit. Every number in a PDF enters through a fact slot filled by
``facts.py`` from the landing tables, and is recorded in ``<doc_id>.facts.json``.
"""
