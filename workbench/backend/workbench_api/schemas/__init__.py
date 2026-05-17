"""Pydantic v2 response/request schemas for the workbench API surface.

B022 F002 introduces these for the 7 vertical-slice endpoints that
F006-F012 will flesh out. Defining them here (with `response_model=` on
the stub routes) is what registers their JSON Schema in the OpenAPI
document; the frontend then consumes them via the
`workbench/frontend/scripts/generate-types.sh` pipeline so every page
can `import type { components } from "@/types/api"` instead of hand-
coding interfaces (CI drift guard fails the build on divergence).
"""
