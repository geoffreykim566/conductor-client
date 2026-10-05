# core/net

Everything that talks to the network: the Conductor server API (identity, chat streaming,
ratings, profile) and GitHub Releases for update checks, plus the QThread workers that run
those calls off the UI thread.

## Files
- `auth.py` - register for a server-minted token, `ensure_token()`, `headers()`; `RegistrationThrottled`.
- `chat_stream.py` - `stream_chat()` over SSE from `POST /v3/chat`; `CancelToken`; `FreeLimitReached`.
- `account.py` - ratings, `get_me` (usage), `put_me` (onboarding answers), `delete_me`; async variants.
- `llm_client.py` - `StreamWorker` (one chat turn with screenshots + AX context) and `MeWorker`.
- `update_checker.py` - `UpdateChecker` QThread comparing the latest GitHub release to `config.VERSION`.

## How it works
Every request carries the token as `X-Conductor-Id`. User-facing calls (chat, `get_me`)
register lazily on first use; fire-and-forget calls (ratings, `put_me`, `delete_me`) skip when
no token exists rather than burn a registration. A 401 clears the token and retries once (a
loop, not recursion, so a broken server can't cause a register storm). The chat `history` is
opaque: whatever the last `done` event carried is sent back verbatim next turn.

`stream_chat` yields `(kind, payload)`: `chunk`, `status`, `research_prompt` (stream ends; resume
with `resume="allow_research"|"deny_research"`), `done`, `cancelled`, `error`. 402 raises
`FreeLimitReached`; 413/422 become a friendly error (detail logged); a timeout yields a canned reply.

Set `CONDUCTOR_SERVER_URL` (e.g. `http://127.0.0.1:8000`) to hit a local server.

## Quirks & why
### Cancelling a stream
Esc must unblock a worker stuck in an SSE read. `CancelToken.cancel()` flags the token and
closes the response; the dropped connection is what tells the server to abort the turn.
`socket.shutdown(SHUT_RDWR)` runs before `close()`: on macOS `close()` alone left the blocked
`recv()` waiting until the read timeout (2026-09-13). Works on the TLS socket too.

### 422 detail is logged
The 422 body names which server validator fired; it used to be discarded, which left an
oversized-screenshot incident (2026-09-09) to be reconstructed by hand.

## Adding an endpoint
Put user-visible calls that may register in the relevant module using `ensure_token()`;
fire-and-forget calls use `identity.get_token()` and return early on None. Never call the
network from the UI thread: wrap it in a QThread (see `llm_client.py`) or a daemon thread.
