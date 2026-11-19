# Automatic question replenishment

The backend schedules generation after a quiz fetch or answer submission when a user has at most two unanswered multiple-choice questions across a course. A background task attempts five new questions. They appear on a subsequent fetch.

## Single generator source

`question-ai/src/qgen` is the only generator package. The backend installs it as an editable local dependency (`../question-ai`) and imports its agents, schemas, retrieval, checks, and prompts. The backend supplies the existing Claude client as a call adapter. Changes to the generator should be made in `question-ai/`; do not copy its modules into `backend/app/`.

The source question schema includes an explanation, a lecture evidence sentence, and selected concept names. The site passes the chapter's valid concept names to the generator. The question is saved only when the selected names are valid, the independent solver and reviewer approve it, and the normalized evidence occurs on the cited lecture page. Normalization removes whitespace and punctuation. A question without a valid concept is discarded; there is no first-concept fallback.

## Cost guard

The guard is per course. It prevents another run while generation is active, waits one hour after a run saving zero questions or raising an exception, enforces ten minutes between runs, and allows at most five starts per UTC day. This follows PR #17. The guard state is in server memory; a restart resets it. If the service is scaled to multiple processes or instances, move this state to a database-backed reservation before relying on these limits as a strict cross-instance budget.

## Deployment

Set `ANTHROPIC_API_KEY` on the Render backend service. Without it, scheduling is disabled. `QGEN_MODEL` can override the default `claude-haiku-5-5`.

The backend depends on the sibling `question-ai` directory. Render's service root directory must therefore be the repository root. `render.yaml` uses repository-root build and start commands that enter `backend`. If the existing Render service was configured manually with Root Directory `backend`, update that dashboard setting and its build/start commands before deploying this branch; files outside a Render root directory are unavailable during build and runtime.

An approved lecture material and at least one concept must exist for a chapter. Generated problems are saved with `origin="llm"` and a source material/page reference. Live model calls require a separate smoke test; automated tests use simulated responses.
