# Lobby questions: pending until delivered

Kit's lobby can raise a question before play (today: "where did Nik learn to use a shield and
calligrapher's supplies?", from `kit_chargen.proficiency_sources`). Hosts run one command at a
time and can drop a reply, so a question is **never marked asked when it is generated**.

State lives in the save (`kit.sqlite`):

- `kit_pending_question`: generated, not yet known delivered (`id`, `table_line`, `shown` count,
  `carried_turn`). A changed sheet replaces the older pending question.
- `kit_asked`: delivery confirmed. Only these are suppressed.

A pending question moves to asked on either positive delivery signal:

1. **Host confirmation.** The lobby result carries `proficiency_check.question_id` and a
   `delivery` hint. After saying `table_line`, the host runs
   `python3 -m runtime.kit_agent start --db kit.sqlite --question-delivered <id>`.
2. **A committed play turn that carried it and actually asked it.** While pending, every
   `prepare` (not table talk) adds `lobby_question` to the packet, and so does the opening packet
   from `start --room` (`prepared.lobby_question`), so it rides the very first turn. Kit asks it in
   that turn's `spoken`, in her own words. When that turn's `complete`/`finish` commits, the
   runtime checks the committed `spoken` (`kit_campaign.question_asked_in`): every unsourced item
   must be named by its key terms (word-start stems, generic words like "supplies" ignored, so
   "calligraphy" names calligrapher's supplies) and the reply must ask something (a `?` or an ask
   word). Only then does the result gain `lobby_question_delivered: true`. Otherwise it gains
   `lobby_question_delivered: false` and the question stays pending for the next turn. A
   committed `spoken` is the one thing every host shows the player, so this works with no host
   support.

**Length caps.** The question is not scene talk: on a turn that carries it and really asks it,
the tight-mirror caps (110/150) and the 60-word call cap grow by the `table_line`'s word count
(`kit_voice.question_allowance`). A turn that does not ask it gets no allowance.

Until one of those happens, every lobby call raises the question again and every play packet
carries it, so a dropped reply is always asked again. Why not "mark on the next call"? The next
call arrives whether or not the player saw the reply, so it cannot tell delivery from a drop.
