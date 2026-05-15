"""Authentication surface for the workbench backend.

NextAuth.js (Auth.js v5) on the frontend signs a session JWT with HS256 and
``NEXTAUTH_SECRET``; the backend verifies the same secret/algorithm here so
that ``/api/*`` routes can be gated by the same session as the UI. The
allowlist is intentionally a single email — the workbench is single-user by
design (PRD §5, B021 spec §2).
"""
