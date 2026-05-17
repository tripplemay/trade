"""HTTP routers for the workbench API surface.

Each vertical-slice module exports a `router: APIRouter` registered under
the `/api` prefix in `workbench_api.app.create_app()`. F002 ships the
schema surface and 501-stub handlers; F006-F012 replace the bodies with
real implementations. Keeping the schema + route shape stable across
that handoff is what lets the OpenAPI → TypeScript pipeline (CI drift
check) catch any later breaking change before it ships.
"""
