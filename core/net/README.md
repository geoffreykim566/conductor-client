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
Every other failure becomes one of four fixed texts in `ERROR_TEXT` (Errors, below).

Set `CONDUCTOR_SERVER_URL` (e.g. `http://127.0.0.1:8000`) to hit a local server.

## Quirks & why
### Errors
A failed turn tells the user only whose side it's on and whether to retry; the raw cause is printed
as `[server_error]`, never shown (the old raw text once told users to reset an API key they don't have).
- `offline`: `ConnectError`, i.e. no internet, or our server is down (the client can't tell which).
- `down`: the server's error event says so (OpenAI out of credit, key rejected, outage), or a 503
  (the daily budget breaker).
- `busy`: a 429 (the server's per-IP limit) or the event says so (OpenAI's shared rate limit).
- `retry`: anything else, including an older server's raw `message` and any exception here.

The server sends `kind`; the texts live here. The server refunds a failed turn's free message, so
`_on_error` refreshes the counter (`ui/chat_turns.py`). A cancel isn't refunded.

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
