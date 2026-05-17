"""Service-layer helpers for the workbench API.

Route handlers stay thin; the actual aggregation / file-system / repository
choreography lives here so it can be unit-tested without a FastAPI app.
"""
