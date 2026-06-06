"""B044 — recommendations precompute job package.

This is the ONLY workbench_api package allowed to import the ``trade`` package
(real Master Portfolio scoring). The request path
(``routes/recommendations.py`` + ``services/recommendations.py``) must never
import ``trade`` — enforced by the §12.10 AST guard
(``tests/safety/test_recommendations_request_self_contained.py``), now that
``trade`` ships into the VM venv (B044 F001) rather than being physically
absent.
"""
