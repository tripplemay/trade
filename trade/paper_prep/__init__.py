"""B012 Paper Trading prep boundary.

This package only defines the research-to-paper interface boundary used to convert backtest
results into a Target Positions schema and to journal them through an abstract Broker
Adapter. It must not import or contact any real paper or live broker SDK; that work belongs
to a later batch. Every artifact emitted here is research-only and never authorizes any
paper or live trading action.
"""
