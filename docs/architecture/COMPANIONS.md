# Companions: deterministic tactics baseline (priority 3)

Brendon's companion research recommends benchmarking a deterministic baseline before any model
plays an ally: ordered tactics (Dragon Age) with resource permissions (Pillars). This is it
(`runtime/kit_party.py`, wired into `runtime/kit_combat.py`).

* **Roster in the save.** `Runtime.add_companion(key, sheet, role, policy)` commits a
  `party_roster` event; fights commit `party_state` (hit points, status, conditions, death saves,
  resource ledger). Both replay from SQLite, so a Python reset resumes mid-fight.
* **Real combatants.** Kit rolls a companion's initiative (seeded d20 + Dex or the sheet's
  initiative); it takes its slot in the order; foes attack whoever is in melee with them
  (a defender first), else the PC; damage, 0 hp, death saves (SRD), massive damage, revival by
  healing, and incapacitating/poisoned/dodging conditions are run by the engine.
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
