# Phase 11B BYOK decision · 15 November 2026

**Deferred. BYOK remains disabled and is not eligible to begin.** Plan v4 makes BYOK optional and requires both a passing Phase 11A and a separate privacy and consent decision. Local 11A tests used invented data and a stub. The real canary, participant task and target verification are still open. No user credential field, request contract, storage or provider routing was added.

Before approving a separate BYOK slice:

- The product and privacy owners must approve the eligible users, providers, models and destinations, including any proxy or provider retention and processing terms. Decide which dataset metadata, values, previous turns, question text and result facts may leave the application, and which categories must be blocked.
- Agree on what the reader must see and accept before transmission: provider, model, destination, exact classes of data sent, when a request may be billed, and how the request-scoped credential and Stop/Clear work. The reader must retain a manual path after declining or withdrawing consent.
- Agree on credential boundaries in the browser, proxy and backend. Keep keys request-scoped, absent from persistent browser/server storage, logs, telemetry, crash capture and exports. Define independent disabling, what can be canceled before dispatch, and what an upstream service may already have processed.
- With synthetic keys and a stub provider, verify isolation for parallel users, invalid and revoked credentials, preserved application sign-in, clear/stop, reload, session and dataset switching, stale delivery, cancellation, timeout and independent rollback. Review privacy and browser evidence before considering release.

The public investigation, D7 gate, calculator and manual analysis do not depend on this decision. See the [Phase 11A verification](phase11_verification.md) for the separate reliability evidence.
