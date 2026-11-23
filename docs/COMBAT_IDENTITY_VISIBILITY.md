# KIR-51: private combat roster and public identity

An active unseen opponent was included in initiative and public names but omitted from combat HP. Source visibility flags also failed to constrain public target offers consistently. The regression was reproduced on b039bdf before this change.

Native HP and private initiative now retain active opponents in the current area independently of visibility. Actors whose status is hidden remain inactive until revealed by the existing source/play mechanism. Public initiative, wounds and target offers use current observation. Unseen attack narration uses an unidentified opponent label while private traces retain actor IDs. Companion observation and public rendering follow the same visibility boundary. No new hiding, advantage or targeting rule is inferred from the source.

Explicit actor reveal now clears visibility and hiding flags even when the actor is already alive, rather than only when its status is hidden. The existing dead-to-alive rejection is preserved. A timed return retains the previously visible actor identity when its native return occurs.

Eight focused regressions cover private HP, public names, existing visibility markers, unseen action, explicit reveal, inactive hidden status, companion order rendering and restart. The companion test double now supplies the source, locality and label interface required by the real Fight. Selected combat/source/party/room-loader/timed-procedure suite: 147 tests passed. The baseline focused suite failed nine assertions/subcases before implementation. This is local verification, not independent host evaluation or deployment.
