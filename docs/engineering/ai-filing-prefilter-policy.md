# AI Filing Prefilter Policy

## Purpose

This policy defines the boundary for future AI news and filing risk analysis. It responds to the audit finding that sending all SEC filings or news items directly to an LLM is expensive, slow, and likely to hit rate limits.

## Core Rule

News and filings must pass through deterministic prefilters before any LLM analysis.

Acceptable prefilters include:

- Keyword/rule filters.
- Traditional NLP classifiers.
- Bloom-filter-like membership checks for known risk terms.
- Filing type filters, such as SEC 8-K and 10-Q prioritization.

## LLM Boundary

LLM calls should be reserved for documents that match risk criteria. Reports must distinguish deterministic prefilter results from LLM-generated analysis.

AI must not:

- Buy or sell.
- Place, cancel, or replace orders.
- Change strategy parameters.
- Allocate capital.
- Override Portfolio Manager, risk, or kill-switch decisions.
- Claim a document was reviewed if it was filtered out before LLM analysis.

## B006 Boundary

B006 Global ETF Backtest MVP does not need to implement AI filing analysis. If any AI-related stub exists, it must be non-executing and must preserve the no-buy/no-autoparameter boundary.
