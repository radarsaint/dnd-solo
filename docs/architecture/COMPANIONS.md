# Companions: deterministic tactics baseline (priority 3)

Brendon's companion research recommends benchmarking a deterministic baseline before any model
plays an ally: ordered tactics (Dragon Age) with resource permissions (Pillars). This is it
(`runtime/kit_party.py`, wired into `runtime/kit_combat.py`).

* **Roster in the save.** `Runtime.add_companion(key, sheet, role, policy)` commits a
  `party_roster` event; fights commit `party_state` (hit points, status, conditions, death saves,
  resource ledger). Both replay from SQLite, so a Python reset resumes mid-fight.
* **Real combatants.** Kit rolls a companion's initiative (seeded d20 + Dex or the sheet's
  initiative) and it takes its slot in the order. Damage, 0 hp, death saves (SRD), massive
  damage, revival by healing, and incapacitating/poisoned/dodging conditions are run by the engine.
* **Foe targeting** (`kit_party.foe_target`, deterministic). A foe attacks, in order: a standing
  companion in melee with it (a defender first); else whoever hurt it last, if that is a standing
  companion (bow shots, spell attacks, save and auto-hit spells all count; a bow shot is not
  melee); else the PC. Downed companions are left alone. "Last attacker" is sticky and naive:
  there is no threat model.
* **Downed PC.** Kit's `downed` call (main's step) is always kept: when the PC is down and a foe
  acts, Kit decides `attack` or `turn_away`. With companions standing, the call also lists them.
  `attack` keeps each foe on its own fight (as above, falling back to the PC); `turn_away` sends
  it at the standing companions. With no companions the call, and every event, is byte-identical
  to the solo path.
* **Capability isolation.** Legal actions come only from the sheet: attacks with stated to-hit
  and dice, spells the SRD table runs (slots from the sheet), Second Wind, Potion of Healing.
  `validate` refuses anything else and falls back to Dodge; the engine spends slots, uses, items.
  Damage and healing use dice averages (as NPCs do).
* **Knowledge isolation.** `decide(observe(...))` sees its own sheet/options, allies and revealed
  foes with qualitative injury and visible conditions: no AC, hit points, DCs, vulnerabilities,
  hidden creatures or room facts.
* **Turn ownership.** Companions act only in their own slots; the loop stops at the PC's.
* **Tactics.** Roles: defender, striker, healer (ordered rules, first match wins). Policies:
  conserve (slots only to raise a downed ally), balanced (slots for healing or several foes),
  aggressive (always). Fallback: Dodge.
* **Sheets.** Supplied by the player, never generated. Missing numbers are refused; unknown
  spells/features/items and a caster with slots but no prepared spells are returned as asks.

Not yet: player orders to a companion ("Odile, heal me"), companion reactions, opportunity
attacks, area spells, concentration/buffs (Bless), multiattack for companions, companion
surprise, movement/range, out-of-combat death saves, rests for companions.
