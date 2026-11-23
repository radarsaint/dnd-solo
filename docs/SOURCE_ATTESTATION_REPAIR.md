# Source-attestation repair — 22 November 2026

The working audit identified kit_rulings.for_action validating a missing/out-of-range source span against the quotation itself. A synthetic failure injection reproduced source_verified=True against unrelated source. The new regressions also exposed reordered-word acceptance and ignored/malformed offsets.

The repair requires a two-integer, nonempty in-bounds span, an integer offset matching its beginning, and identical contiguous source wording after whitespace normalization. It rejects missing source rather than self-attesting. It verifies wording/location, not semantic entailment or causal applicability.

kit_prefetch now retains the source offset it previously omitted. An existing ruling-test fixture now closes its SQLite connection before temporary-directory cleanup; the same two cleanup errors appeared on baseline and candidate before that correction.

Verification: test_kit_ruling_attestation plus test_kit_rulings: 43 tests passed, zero errors/skips, 5.208 seconds on Windows Python 3.13.3 with UTF-8 propagated to subprocesses. Initial failing and baseline comparison receipts are retained in the parent review folder. This does not establish later-room play or full-suite acceptance.

Compatibility consideration: old prefetched records lacking an offset now fail closed. Next implementation should discard/rebuild or re-resolve stale cached records from verified current source rather than silently losing an available valid ruling. Do not restore quote-as-source behavior to preserve cache hits.

The actual later-room transfer failure remains unresolved. The next task is source-to-current-situation interpretation at later locations, followed by normal entry, response, initiative, subsequent decisions, revisit and interruption checks. Opening regression tests are frozen coverage, not the acceptance target.
