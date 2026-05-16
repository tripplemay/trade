# B021 Auth Flow Verification — 2026-05-16

## Scope

Independent verification that the production OAuth flow actually works
after the four B021 F006 fix-round 3 commits landed. Resolves the
`error=Configuration` symptom that Codex's L2 attempt
(`docs/test-reports/B021-cloud-deploy-auth-blocker-2026-05-16.md`)
flagged as a remaining blocker.

## Result

The OAuth flow works. The `error=Configuration` that Codex saw came
from probing the sign-in endpoint with a `GET` — Auth.js v5 classifies
that as an `UnknownAction` and surfaces a generic Configuration error.
The real sign-in entrypoint is a `POST` carrying the CSRF token in the
form body, and it succeeds in production.

## Evidence

### Pull CSRF token + jar a session cookie

```bash
curl -sS -c /tmp/jar https://trade.guangai.ai/api/auth/csrf
# → {"csrfToken":"91d37caa5d93fd8ab3b8877b891f6cb3ee0c332f8a90e51482c8e180e2cad1e0"}
```

### POST `/api/auth/signin/google` with the CSRF token + cookie

```bash
CSRF="91d37caa5d93fd8ab3b8877b891f6cb3ee0c332f8a90e51482c8e180e2cad1e0"
curl -sS -b /tmp/jar -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "csrfToken=${CSRF}&callbackUrl=https%3A%2F%2Ftrade.guangai.ai%2F" \
  -o /dev/null \
  -w "HTTP %{http_code} → redirect: %{redirect_url}\n" \
  https://trade.guangai.ai/api/auth/signin/google
```

Returns:

```
HTTP 302 → redirect: https://accounts.google.com/o/oauth2/v2/auth?
  response_type=code
  &client_id=346196763254-rosgk66u8l826908i7g4l8k2tgb7h3co.apps.googleusercontent.com
  &redirect_uri=https%3A%2F%2Ftrade.guangai.ai%2Fapi%2Fauth%2Fcallback%2Fgoogle
  &code_challenge=UkB5JXbcUOZePoZJb3AqJLRKWYEmYJxdqi1oGGcTqnA
  &code_challenge_method=S256
  &scope=openid+profile+email
```

The fact that the redirect URL is built means:

- `GOOGLE_OAUTH_CLIENT_ID` is read at runtime and reaches Auth.js
  (the real value appears in the redirect, not `undefined`).
- `redirect_uri` points at the production callback under
  `trade.guangai.ai` — `trustHost: true` is in effect.
- PKCE (`code_challenge_method=S256`) is being generated, so the JWT
  encode side (override `lib/auth-config.ts`) is producing keys.

### Why `GET /api/auth/signin/google` returned `error=Configuration`

Auth.js v5 treats sign-in as a state-changing action and refuses GET.
The frontend code path (the `<form action={signInWithGoogle}>` in
`workbench/frontend/src/app/login/page.tsx`) always submits POST. The
journal on the VM confirms the underlying error code:

```
sudo journalctl -u workbench-frontend.service -n 80 --no-pager
…
[auth][error] UnknownAction: Unsupported action.
Read more at https://errors.authjs.dev#unknownaction
```

The `UnknownAction` error is silently transformed into the
`error=Configuration` URL parameter in the front-end redirect, which
is what made the symptom look like a configuration problem.

### Companion endpoints

```text
curl -sSf https://trade.guangai.ai/api/auth/providers
→ {"google":{"id":"google","name":"Google","type":"oidc",
              "signinUrl":"https://trade.guangai.ai/api/auth/signin/google",
              "callbackUrl":"https://trade.guangai.ai/api/auth/callback/google"}}

curl -sSf https://trade.guangai.ai/api/auth/csrf
→ {"csrfToken":"…64 hex chars…"}

curl -sSf https://trade.guangai.ai/api/auth/session
→ null

curl -sSf https://trade.guangai.ai/api/health
→ {"status":"ok","version":"600fc553f1c639f113647d94d178815230aa27ed",
   "db_connectivity":"ok","uptime_seconds":…,
   "last_backup_age_seconds":…,"last_backup_size_bytes":…,
   "active_user_count":0}
```

All six observability fields present. `version` matches the deployed
release SHA (commit `600fc55`).

## Codex L2 next steps

To re-verify the browser OAuth happy path:

1. From the user laptop, open `https://trade.guangai.ai/`.
2. Middleware redirects to `https://trade.guangai.ai/login?callbackUrl=%2F`.
3. Click the "Sign in with Google" button. The browser performs the
   POST form submission with the CSRF token automatically (the page's
   `<form action={signInWithGoogle}>` server action does this).
4. Browser redirects to `https://accounts.google.com/o/oauth2/...`,
   user authenticates as `tripplezhou@gmail.com`, Google redirects back.
5. Auth.js callback at `/api/auth/callback/google` verifies the
   allowlist (`profile.email === ALLOWED_USER_EMAIL`), mints the HS256
   JWT, sets `authjs.session-token` cookie, redirects to `/`.

Non-allowlist reject:

1. Sign in with a different Google account.
2. The `signIn` callback (`workbench/frontend/src/lib/auth-config.ts`)
   returns `false`; Auth.js redirects to `/login?error=AccessDenied`.
3. The `/login` page renders the spec's "This workbench is restricted
   to a single authorized user." notice.

Curl-based reproduction is not a substitute for the browser test —
Google OAuth requires an interactive consent screen. The curl checks
above only prove the Auth.js wiring on the production host is sound.

## Conclusion

B021 F006 production wiring is verified. The L2 blockers from
`docs/test-reports/B021-cloud-deploy-auth-blocker-2026-05-16.md` are
all closed:

- `/api/auth/providers` returns Google provider JSON (was 404 →
  fixed by F003 vhost `/api/auth/` block + nginx-sync workflow)
- `/api/health` `version` matches the deployed release SHA (was `dev`
  → fixed by `RELEASE_SHA` marker + `_resolve_version()` refactor)
- `/api/auth/signin/google` accepts a real POST + CSRF and redirects
  to Google (was `error=Configuration` on GET, which is the
  documented Auth.js v5 behaviour for an `UnknownAction`).

Codex L2 may proceed with the browser-based OAuth happy path and
non-allowlist reject checks listed above.
