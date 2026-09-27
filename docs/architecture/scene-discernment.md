# Scene Discernment for NPC Improv

**Purpose:** Give Kit a reusable private decision before she performs an NPC or frames a scene. Area 6c is its first adapter, not the definition of the method.

## The decision

After an action is adjudicated and before dialogue is written, Kit reads five things together:

1. **The player's bid:** What was actually declared or asked, and what the accepted event established. Recent public dialogue supplies conversational continuity; Kit does not infer the player's unspoken thoughts.
2. **The available story:** The current scene and explicitly active level/campaign pressures. A source adapter marks those scopes `active_here`; an unrelated or dormant through-line cannot be selected merely to add drama.
3. **The actor's own aim:** A live actor in the current location and an established `motive` or `immediate_goal`. Their knowledge and constraints remain in the DM context; the actor need not serve Kit's agenda.
4. **Kit's interest:** Her current goal, event appraisal, and relevant earlier episodes. She chooses whether to spotlight the collision, stay quiet, rule, or leave an opening.
5. **The playable collision:** Why this player's move changes what that actor might try *now*, and which permitted pressure is relevant. If there is no connection, `none` is valid for story or actor. Kit then chooses a move and a public-safe objective/tactic/visible cue/player opening. The performer improvises words from that decision and any established voice card.

This is a **selection within the existing private plan**, not another model request. The private `improv_read` records `player_bid`, `story_anchor`, `story_basis`, `actor_ref`, `actor_basis`, `connection`, and `kit_choice`. `runtime/scene_discernment.py` derives eligible references from the current source/state packet and rejects invented actors, absent goals, and inactive story scopes. `runtime/kit_agent.py` checks that an NPC reply selects the actor it claims to perform. The full private read stays out of the public performance packet; its public brief and selected move cross that boundary. The transcript and read commit with the world event.

| Situation | Plausible private selection | Player-facing consequence to test |
| --- | --- | --- |
| Nik offers to help the dealer against his rival in area 6c | Player's offer + active level leadership pressure + dealer's self-interested motive + Kit's taste for consequential roleplay | Dealer tests the value and risk of the offer in his own voice. Kit lets the possibility breathe without making a bargain or exposing the rivalry as fact. |
| A player offers to carry ledgers in a flooding archive | Player's offer + active level flood pressure + keeper's immediate goal + Kit's interest in rewarding useful initiative | Keeper reacts with urgency and a concrete request. No card-game language, Undertaker behavior, or unrelated royal-succession plot appears. |
| A player quietly examines a wall | Player's observation + scene state; actor and larger story may both be `none` | Kit describes what is fairly perceivable or calls for a relevant check. She does not summon a plot-bearing NPC to manufacture tension. |

The first and third cases still require a room/rules adapter to establish consequences; the second is a synthetic contract test. A selected anchor is a **reference**, not permission to reveal its private text or force its outcome. A social promise, deal, revelation, or world change needs its own validated state transition.

## Why this shape

[FAtiMA](https://arxiv.org/abs/2103.03020) separates an event's relation to an agent's goals from high-level action selection; Kit's appraisal and choice serve that role. [*Versu*](https://cs.uky.edu/~sgware/reading/papers/evans2014versu.pdf) lets individual characters choose among actions afforded by a current social practice; the actor's established aim and the live interaction must remain distinct from Kit's. [*Façade*](https://ojs.aaai.org/index.php/AIIDE/article/view/18722) responds to moment-by-moment player input with dramatic beats; the public brief is our much smaller, source-bounded beat direction. We have implemented none of those full systems. Their distinction between event, character choice, and dramatic presentation is the basis for this contract.

## Evaluation boundary

Automated tests prove reference eligibility, secrecy handoff, persistence, and rollback. They cannot prove that the player bid was interpreted well, that the chosen story pressure was *actually* relevant, that Kit's taste changed the turn, or that the resulting dialogue was entertaining. Review paired continuations with the same room and player move but different **valid** earlier player/Kit dialogue or active story state. Score the spoken turn first: did the NPC answer the actual move, pursue a legible aim, react differently when circumstances changed, and leave room for the player? Then inspect the private read for a causal explanation. The one-pass chat path generates decision and performance together, so use the staged path when testing whether the decision truly precedes performance. Continue to time end-to-end replies.

Area 6c still has a limited actor/speaker adapter and no general rules resolver, NPC belief updates, or durable social commitments. This contract can be reused by another room adapter, but no second playable room has been implemented.
