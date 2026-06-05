"""B036 — AI Advisor MVP (the project's first generative-AI surface).

Generates per-sleeve advisory text from grounded inputs (quant signal +
B034 news + B035 market context), with the v0.9.28 5-rule AI boundary
enforced by the system prompt AND by output validation
(``references ⊆ input set`` → otherwise ``INSUFFICIENT_GROUNDING``).

Permanent AI boundary (v0.9.28, first full generative trigger): no
auto-execution, no return-prediction numbers, never the sole basis for a
buy/sell, must cite ``quant_signal_sha`` + ``news_urls`` from the input
set, may explain / summarize / translate / aggregate. The B032 red-team
gate (``tests/safety/test_ai_advisor_red_team.py``) runs the real
advisor against 15 adversarial samples and must block 100%.
"""
