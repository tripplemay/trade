"""B054 F-news — Simplified-Chinese headline translation (generative).

This package lives **outside** ``workbench_api/news/`` on purpose: the news
package is locked non-generative by ``tests/safety/test_b034_no_generative_ai.py``
(it may call ``LLMGateway.embed`` only, never ``advise``). Headline
translation is a generative ``advise`` call, so it sits here — exactly as
the embedding precompute and the B043 explanation jobs are separate from the
non-generative request/serving path.

The translation is **off the request path** (a manual batch job, like the
news ingest CLI) and writes the pre-computed ``news.title_zh`` column; the
``/api/news/latest`` and sleeve-news serving paths only *read* that column,
so they stay non-generative. Translation is no-AI boundary rule (e)
(translate only — never advise / predict / execute).
"""
