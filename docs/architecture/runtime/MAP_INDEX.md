# Mad Mage Runtime Map Index

**Purpose:** Deterministic binding between the indexed adventure, level story layers, and canonical map assets.

## Geometry Authority

For every numbered dungeon level, the canonical **DM map** is the authority for spatial geometry. The adventure keyed text is the authority for room contents and rules. Current campaign state is the authority for physical changes caused by play.

The runtime must never improvise geometry when a canonical map exists. It may not invent or relocate doors, corridors, rooms, secret passages, stairs, shafts, gates, distances, or adjacency. If a map/text mismatch is known, use the errata layer; if unresolved, preserve the mismatch rather than repairing it by invention.

Player-map assets are presentation aids only. The knowledge/spatial ledger controls what topology is actually revealed.

## Visual Asset Cross-Reference

`MAP_INDEX.md` is the canonical map/geometry binding. Non-map visual assets are indexed separately in `assets/ASSET_REGISTRY.json` (with `assets/ASSET_REGISTRY.md` as the human-readable companion). The visual registry may mirror map paths for asset discovery, but any disagreement about map identity, keyed-area binding, or geometry is resolved in favor of this map index plus current spatial state and errata.

## Level Bindings

### Level 1: Dungeon Level

- Level layer: `docs/campaign/levels/LEVEL_01_DUNGEON_LEVEL.md`

- Canonical DM map: `assets/maps/levels/map-01.01-dungeon-level-dm.png`

- Player presentation map: `assets/maps/levels/map-01.01-dungeon-level-player.jpg`

- Indexed keyed areas: 1–41

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Entry Well; 2. Hall of Many Pillars; 3. Slanted Room; 4. With Sword in Hand; 5. Grell Hideout; 6. Undertakers’ Watch Post; 7. Vampire Haven; 8. Bandit Headquarters; 9. Plundered Halls; 10. Cubicle of Skulls; 11. Room of Secrets; 12. Hall of Heroes; 13. Empty Room; 14. Little Box of Horrors; 15. Armory; 16. Manticore Den; 17. Stone Temple Pileup; 18. Troll’s Den; 19. Ye Olde Feast Halls; 20. Beyond the Green Door; 21. Hall of Mirrors; 22. Empty Room; 23. Worg’s Eye Watch Post; 24. Halls of Hopelessness; 25. Excavation Site; 26. Clean Tunnels; 27. Hidden Demiplane; 28. Grick Snack Watch Post; 29. Eye See You!; 30. Mad Elemental; 31. Delvers’ Hall; 32. VIP Suite; 33. North Dormitory; 34. South Dormitory; 35. Hall of Rats; 36. Lost Halls; 37. Map Room; 38. Secret Tunnel; 39. Big Ears Watch Post; 40. Fearful Mimicry; 41. Cracked Ceiling

### Level 2: Arcane Chambers

- Level layer: `docs/campaign/levels/LEVEL_02_ARCANE_CHAMBERS.md`

- Canonical DM map: `assets/maps/levels/map-02.01-arcane-chambers-dm.png`

- Player presentation map: `assets/maps/levels/map-02.01-arcane-chambers-player.jpg`

- Indexed keyed areas: 1–25

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Goblin Bazaar; 2. Kalabash’s Chambers; 3. Halaster Puppet; 4. Abandoned Camp; 5. Arch Gate to Level 4; 6. Music of the Dead; 7. Shocking Discoveries; 8. Fresco Cross Hall; 9. Spider Eyes Watch Post; 10. Ooze Temple; 11. Midna’s Lair; 12. Dwarven Tools; 13. Mutated Apprentices; 14. Base de Résistance; 15. Dusty Throne; 16. Partially Collapsed Room; 17. Hungry Rust Monsters; 18. Cold Storage; 19. Giant Spider Den; 20. Dead Eyes Watch Post; 21. Animated Ballistae; 22. Garrux’s Brewery; 23. Ruined Dwarven Temple; 24. Dead Adventurer; 25. Creature Storage

### Level 3: Sargauth Level

- Level layer: `docs/campaign/levels/LEVEL_03_SARGAUTH_LEVEL.md`

- Canonical DM map: `assets/maps/levels/map-03.01-sargauth-level-dm.png`

- Player presentation map: `assets/maps/levels/map-03.01-sargauth-level-player.jpg`

- Indexed keyed areas: 1–23

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Catacombs; 2. Dead Explorer; 3. Grick Ambush; 4. Webbed Tunnels; 5. House Auvryndar; 6. Temple of Dumathoin; 7. Pain and Pleasure; 8. Wailing Tunnels; 9. Captain’s Grave; 10. Caves of the River Coven; 11. Recluse; 12. Boo-ty Hunters; 13. Riverside Caves; 15. Way to Wyllowwood; 16. Crossfire Caves; 17. Dangerous Paths; 18. Abandoned Cavern; 19. Chimera’s Lair; 20. Drow Town; 21. Azrok’s Hold; 22. Barrelstalk Garden; 23. Way to Skullport

### Level 4: Twisted Caverns

- Level layer: `docs/campaign/levels/LEVEL_04_TWISTED_CAVERNS.md`

- Canonical DM map: `assets/maps/levels/map-04.01-twisted-caverns-dm.png`

- Player presentation map: `assets/maps/levels/map-04.01-twisted-caverns-player.jpg`

- Indexed keyed areas: 1–24

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Fungus Forest; 2. Jibber-Jabber; 3. Death from Above; 4. The Alchemist; 5. Cave of Crystals; 6. Tangled Ropes; 7. Mad Wizard’s Retreat; 8. Crossroads; 9. Alarm System; 10. Drider Lair; 11. Drow Outpost; 12. Bat Cave; 13. Zurkhwood Grove; 14. Drow Rafts; 15. Slippery Slope; 16. Grotto of Madness; 17. Pick and Chuuls; 18. Slimy Alcove; 19. Beachhead; 20. Kuo-toa Refuge; 21. Archpriest’s Chambers; 22. Hook Horror Homestead; 23. Hook Horror Larder; 24. Troglodyte Takeover

### Level 5: Wyllowwood

- Level layer: `docs/campaign/levels/LEVEL_05_WYLLOWWOOD.md`

- Canonical DM map: `assets/maps/levels/map-05.01-wyllowwood-dm.png`

- Player presentation map: `assets/maps/levels/map-05.01-wyllowwood-player.jpg`

- Indexed keyed areas: 1–24

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. River of the Depths; 2. Forest; 3. Guardhouses; 4. Cloaker Den; 5. Inner Forest; 6. Wyllow’s Tower; 7. Alcoves of the Dead; 8. Umber Hulk Tunnel; 9. Dragon’s Platform; 10. Mossy Stone Bridge; 11. We All Float Down Here; 12. Werebat Caves; 13. Dining Cave; 14. Werebat Boss; 15. Bat Cave; 16. Werebat Caves; 17. Vool’s Refuge; 18. Abandoned Priory; 19. Looted Cloisters; 20. Malar’s Tabernacle; 21. Abandoned Barracks; 22. Mess Hall; 23. Desecrated Sanctuary; 24. Animal Cloisters

### Level 6: Lost Level

- Level layer: `docs/campaign/levels/LEVEL_06_LOST_LEVEL.md`

- Canonical DM map: `assets/maps/levels/map-06.01-lost-level-dm.png`

- Player presentation map: `assets/maps/levels/map-06.01-lost-level-player.jpg`

- Indexed keyed areas: 1–48

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Umber Hulk Tunnel; 2. Acolytes’ Vestry; 3. Cleansing Chamber; 4. Ransacked Room; 5. Looted Reliquary; 6. Workshop; 7. Library and Scriptorium; 8. Park-and-Ride; 9. Mustering Hall; 10. Royal Armory; 11. King’s Walk; 12. Mithral Thieves; 13. High Priest’s Chambers; 14. Grand Vestibule; 15. Temple of Dumathoin; 16. Heart of the Mountain; 17. Priests’ Study; 18. Hemisphere of Horrors; 19. Mountain Shrine; 20. Wall of Gemstones; 21. Gem-Cutters’ Workshop; 22. Gem Extraction; 23. Stripped Room; 24. Arch Gate to Level 2; 25. Dwarven Den; 26. Sacred Spirits; 27. Arch Gate to Level 4; 28. False Tomb; 29. King Melair’s Lost Tomb; 30. Mummification Chamber; 31. Rest Area; 32. False Halaster; 33. Ghohlbrorn’s Grave; 34. Refectory Rampage; 35. Black Cloak; 36. Temple Maintenance; 37. Showers and Sauna; 38. Wide Alcoves; 39. Temple Reliquary; 40. Music Hall; 41. Privies; 42. Hidden Pit; 43. Umber Hulk Tunnels; 44. Acolytes’ Quarters; 45. Acolytes’ Quarters; 46. Blasted Chamber; 47. Halls of the Faithful; 48. High Priest’s Quarters

### Level 7: Maddgoth’s Castle

- Level layer: `docs/campaign/levels/LEVEL_07_MADDGOTH_S_CASTLE.md`

- Canonical DM map: `assets/maps/levels/map-07.01-maddgoths-castle-dm.png`

- Player presentation map: `assets/maps/levels/map-07.01-maddgoths-castle-player.jpg`

- Indexed keyed areas: 1–47

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Umber Shells; 2. Empty Cavern; 3. Stone Throne; 4. Silt Pit; 5. Cave of Echoes; 6. Craft Hall; 7. Silt Pit; 8. Strange Rock Formation; 9. Stone Cathedral; 10. Xorta’s Flute; 11. Disposal Cave; 12. Edible Moss; 13. Giants’ Living Quarters; 14. Cave Bear Den; 15. Qurrok’s Den; 16. Central Cavern; 17. Main Entrance; 18. Stone Hallways; 19. Southwest Storeroom; 20. Northwest Storeroom; 21. Northeast Storeroom; 22. Southeast Storeroom; 23. Courtyard; 24. Privy and Bath; 25. Maddgoth’s Study; 26. Clayworks; 27. Dining Room and Kitchen; 28. Well-Appointed Halls; 29. Southwest Guest Room; 30. Northwest Guest Room; 31. Northeast Guest Room; 32. Southeast Guest Room; 33. Slaad in the Octobass; 34. Madd­goth’s Suite; 35. Cloakroom; 36. Records; 37. Console; 38. Glittering Hall; 39. Southwest Chamber; 40. Northwest Chamber; 41. Northeast Chamber; 42. Southeast Chamber; 43. Otto’s Den; 44. Wizard’s Armory; 45. Alchemist’s Laboratory; 46. Madd­goth’s Throne; 47. Roof and Battlements

### Level 8: Slitherswamp

- Level layer: `docs/campaign/levels/LEVEL_08_SLITHERSWAMP.md`

- Canonical DM map: `assets/maps/levels/map-08.01-slitherswamp-dm.png`

- Player presentation map: `assets/maps/levels/map-08.01-slitherswamp-player.jpg`

- Indexed keyed areas: 1–24

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Precipice; 2. Bullywug Sentries; 3. Arch Gate to Level 6; 4. Dangerous Shrubbery; 5. Dry Cave; 6. Reflections; 7. Warded Cavern; 8. Dweomercore Hideout; 9. Temple of the Great Snake; 10. Rainfall Caverns; 11. Watch Post; 12. Fishery; 13. Detention Cave; 14. Fungal Farm; 15. Lair of the Spirit Nagas; 16. Lair of the Bone Naga; 17. Battlefield Cavern; 18. Serpent Gate; 19. Yuan-ti Temple; 20. Blacktongue Isle; 21. Lord of Fetid Obliteration; 22. Stables; 23. Bullywug Camp; 24. Kelp Farm

### Level 9: Dweomercore

- Level layer: `docs/campaign/levels/LEVEL_09_DWEOMERCORE.md`

- Canonical DM map: `assets/maps/levels/map-09.01-dweomercore-dm.png`

- Player presentation map: `assets/maps/levels/map-09.01-dweomercore-player.jpg`

- Indexed keyed areas: 1–49

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Entry Hall; 2. Trapped Hall; 3. Medusa Junction; 4. Fresh Water Fountain; 5. Portrait of a Mad Mage; 6. Reading Niche; 7. Workroom; 8. Student Dormitories; 9. Refuse Pit; 10. Where’s Halaster?; 11. Student Dormitories; 12. Communal Showers; 13. Recreation Room; 14. Detention Hall; 15. Arcanaloth’s Sanctum; 16. Magic Cauldron; 17. Spellcasting Hall; 18. Illusory Walls; 19. Ghostly Adventurer; 20. Lecture Hall; 21. Classrooms; 22. Potion Brewery; 23. Wormriddle’s Sanctum; 24. Halaster Says What?; 26. Bent Hallway; 27. School Meals; 28. More Halaster Statues; 29. Old Books; 30. Dining Hall; 31. Halaster’s Secretary; 32. Steel-Sheathed Hall; 33. Illusion Classroom; 34. Transmutation Classroom; 35. Necromancy Classroom; 36. Wizards’ Library; 37. Professor Bring; 38. “I Just Met a Girl Named Skrianna”; 39. Study Hall; 40. Empty Room; 41. Drop to Level 10; 42. Guest Lecturer’s Quarters; 43. Dusty Alcoves; 44. Dweomercore’s Back Door; 45. Halaster’s Sanctuary; 46. Detention Area; 47. Devil on the Loose; 48. Conjuration Classroom; 49. Arch Gate to Level 14

### Level 10: Muiral’s Gauntlet

- Level layer: `docs/campaign/levels/LEVEL_10_MUIRAL_S_GAUNTLET.md`

- Canonical DM map: `assets/maps/levels/map-10.01-muirals-gauntlet-dm.png`

- Player presentation map: `assets/maps/levels/map-10.01-muirals-gauntlet-player.jpg`

- Indexed keyed areas: 1–30

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Shattered Mirrors; 2. Secret Hallway; 3. Haunted Temple of Lolth; 4. Muiral’s Laboratory; 5. Dilapidated Rooms; 6. Teleportation Statues; 7. Halls of Selvetarm; 8. The Fate of Falkir’s Fist; 9. God-Watched Gates; 10. Queen’s Parlor; 11. Lolth’s Palace; 12. Ballroom; 13. Vestibule; 14. Guest Apartment; 15. Screaming Skulls; 16. False Mirror Gate; 17. The Dark Seldarine; 18. First Blood; 19. Interrogation Room; 20. Servants’ Quarters; 21. Giant Spider Hatchery; 22. Troglodyte Turf; 23. Distant Music; 24. Collapsed Areas; 25. Auvryndar Hall; 26. Spider Queen’s Temple; 27. Vlonwelv’s Apartments; 28. Hospital and Armory; 29. Abandoned Apartment; 30. Natural Cavern

### Level 11: Troglodyte Warrens

- Level layer: `docs/campaign/levels/LEVEL_11_TROGLODYTE_WARRENS.md`

- Canonical DM map: `assets/maps/levels/map-11.01-troglodyte-warrens-dm.jpg`

- Player presentation map: `assets/maps/levels/map-11.01-troglodyte-warrens-player.jpg`

- Indexed keyed areas: 1–17

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Auvryndar Watch Post; 2. Captured Troglodytes; 3. Hungry Gnome; 4. Loathsome Limbs; 5. Trolling the Troglodytes; 6. Piercer Cavern; 7. Troglodyte Lair; 8. Illusory Front Line; 9. Contested Caves; 10. Troll Tunnels; 11. Forest of Stone; 12. Drow Battle; 13. Freth Refuge; 14. Auvryndar Watch Post; 15. Cleared-Out Caves; 16. Arch Gate to Level 7; 17. Behir Lair

### Level 12: Maze Level

- Level layer: `docs/campaign/levels/LEVEL_12_MAZE_LEVEL.md`

- Canonical DM map: `assets/maps/levels/map-12.01-maze-level-dm.jpg`

- Player presentation map: `assets/maps/levels/map-12.01-maze-level-player.jpg`

- Indexed keyed areas: 1–19

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Into the Maze; 2. Light of the Dead; 3. Dead End; 4. Faces in the Fog; 5. Demon’s Triangle; 6. Special Effects; 7. Minotaur Caves; 8. Shrine of the Horned King; 9. Foggy Caves; 10. Webbed Passage; 11. Crickets and Bats; 12. Guarded Caves; 13. Roundabout; 14. Dead End?; 15. Crickets; 16. Web-Filled Cave; 17. Demons’ Ledge; 18. Drow Fortress; 19. Spiderwatch Keep

### Level 13: Trobriand’s Graveyard

- Level layer: `docs/campaign/levels/LEVEL_13_TROBRIAND_S_GRAVEYARD.md`

- Canonical DM map: `assets/maps/levels/map-13.01-trobriands-graveyard-dm.png`

- Player presentation map: `assets/maps/levels/map-13.01-trobriands-graveyard-player.jpg`

- Indexed keyed areas: 1–12

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Tunnels and Trenches; 2. Vast Cavern; 3. Junkyard; 4. Pretty Big Hate Machine; 5. Scrap Metal Warren; 6. Back Tunnel; 7. Clammersham Palace; 8. Smithy; 9. Metal Pools; 10. Resting Cave; 11. Hobgoblin Base Camp; 12. Paradise Lost

### Level 14: Arcturiadoom

- Level layer: `docs/campaign/levels/LEVEL_14_ARCTURIADOOM.md`

- Canonical DM map: `assets/maps/levels/map-14.01-arcturiadoom-dm.png`

- Player presentation map: `assets/maps/levels/map-14.01-arcturiadoom-player.jpg`

- Indexed keyed areas: 1–41

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Carrion crawler; 2. Chimera; 3. Fire elemental; 4. Gelatinous cube; 5. Gorgon; 6. Hook horror; 7. Manticore; 8. Otyugh; 9. Owlbear; 10. Wyvern; 1. Entrance to Arcturiadoom; 2. Natural Caves; 3. Foyer; 4. Prison; 5. Side Chambers; 6. Statue of Arcturia; 7. Statue of Halaster; 8. Dwarven Crypt; 9. Death’s Head Watch Post; 10. Dwarves’ Den; 11. Smithy; 12. Melairkyn Foundry; 13. Transmutorium; 14. More Scrap Iron; 15. Mecha-Halaster; 16. Death’s Head Looters; 17. Hidden Storeroom; 18. Death’s Head Guard Post; 19. Storerooms; 20. Supplies; 21. Night and Day; 22. Arcane Scribblings; 23. Experiments; 24. Empty Classroom; 25. Hobgoblin Guards; 26. Apprentice’s Quarters; 27. Dead Apprentice; 28. Specimens; 29. Laboratory; 30. Hideous Transmutation; 31. Illithid’s Assistant; 32. Death’s Head Barracks; 33. Doomcrown’s Quarters; 34. Shrieking Gas Spore; 35. Rallying Hall; 36. Death’s Head Training; 37. Weapon of Mass Disintegration; 38. Guest Quarters; 39. Arcturia’s Boudoirs; 40. Arcturia’s Chambers; 41. Watchful Pillars

### Level 15: Obstacle Course

- Level layer: `docs/campaign/levels/LEVEL_15_OBSTACLE_COURSE.md`

- Canonical DM map: `assets/maps/levels/map-15.01-obstacle-course-dm.png`

- Player presentation map: `assets/maps/levels/map-15.01-obstacle-course-player.jpg`

- Indexed keyed areas: 1–40

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. On Your Mark! Get Set! Go!; 2. Clacking Floor; 3. Stuffed Monsters; 4. Caught in the Tentacles; 5. Antechamber; 6. Looted Chest; 8. Teleport Trap; 10. Roller-Dragon; 11. Dead End; 13. Hidden Traps; 14. Sepulchers; 15. Ruined Armory; 16. Spectral Bridge; 17. Ruined Chamber; 18. Ruined Shrine; 19. Grabby Pillars; 21. Destroyed Room; 22. Teleport Traps; 24. Githzerai Retreat; 25. Abandoned Smithy; 26. Statue of Moradin; 27. Mark of Death; 28. Statue of Tharmekhûl; 29. Trapped Halls; 30. Halaster’s Handiwork; 31. Hall of Embers; 32. Empty Junction; 33. Shots in the Dark; 34. Chasm’s Edge; 35. Scythe-Seeing; 37. Harmless Halaster Statue; 38. Zombie Horde; 39. Netherskull’s Sanctum; 40. Netherskull’s Chasm

### Level 16: Crystal Labyrinth

- Level layer: `docs/campaign/levels/LEVEL_16_CRYSTAL_LABYRINTH.md`

- Canonical DM map: `assets/maps/levels/map-16.01-crystal-labyrinth-dm.jpg`

- Player presentation map: `assets/maps/levels/map-16.01-crystal-labyrinth-player.jpg`

- Indexed keyed areas: 1–32

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Entry Hall; 2. Western Cavern; 3. Main Cavern; 4. Barracks; 5. Prison Cell; 6. Eastern Cavern; 7. Anti-Illithid Defense; 8. Officer Quarters; 9. Trophy Room; 10. Golem Laboratory; 11. Stardock Gate; 12. Dragons’ Domain; 13. Jerath’s Quarters; 14. Infernexus’s Quarters; 15. Githyanki Trainees; 16. Nursery; 17. War Wizards; 18. Library; 19. Warehouse; 20. Dock; 21. Warrior Quarters; 22. Al’chaia’s Quarters; 23. Observation Room; 24. Knights’ Quarters; 25. Memorial Hall; 26. Kitchen; 27. Mess Hall; 28. Armory; 29. Prison; 30. Warrior Training; 31. Observation Room; 32. Graduation Chamber

### Level 17: Seadeeps

- Level layer: `docs/campaign/levels/LEVEL_17_SEADEEPS.md`

- Canonical DM map: `assets/maps/levels/map-17.01-seadeeps-dm.png`

- Player presentation map: `assets/maps/levels/map-17.01-seadeeps-player.jpg`

- Indexed keyed areas: 1–20

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Tunnel Plexus; 2. Dripping Cave; 3. Halaster’s Maw; 4. Flumph Cloister; 5. Githyanki Grave; 6. Battleground; 7. Githyanki Stronghold; 8. Operation: Eat Them All; 9. Guard Post; 10. Detention Facility; 11. Halaster Is Glowing; 12. Dynamo; 13. Back Door; 14. Psipod Nexus I; 15. Psipod Nexus II; 16. Old Dwarven Halls; 17. Crumbling Bridge; 18. Gray Mold; 19. Unguarded Area; 20. River Branches

### Level 18: Vanrakdoom

- Level layer: `docs/campaign/levels/LEVEL_18_VANRAKDOOM.md`

- Canonical DM map: `assets/maps/levels/map-18.01-vanrakdoom-dm.png`

- Player presentation map: `assets/maps/levels/map-18.01-vanrakdoom-player.jpg`

- Indexed keyed areas: 1–33

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Entrance; 2. Dusty Emptiness; 3. Statue of Shar; 4. Old Friends; 5. Umbraxakar’s Gift; 6. Cultists’ Quarters; 7. Halls of Worship; 8. Scintilmorn’s Rest; 9. Shadow Vigil; 10. Ritual Chamber; 11. Tunnels and Caverns; 12. Candlelit Halls; 13. Vampire Dens; 14. Temple Chandlery; 15. Shattered Throne; 16. Arch Gate to Level 15; 17. Lost Dwarven Horn; 18. Shadow’s Edge; 19. Hall of Death; 20. Any Moonstars in Here?; 21. Clutter; 22. Under Black Sheets; 23. Decrepit Dining Hall; 24. Decrepit Kitchen; 25. Prisoner of Darkness; 26. Vampire Boss; 27. Altars of Loss; 28. Forgotten Chambers; 29. Foggy Hall; 30. Path to the Tomb; 31. Vampire’s Tomb; 32. Umbraxakar’s Lair; 33. Dragon’s Hoard

### Level 19: Caverns of Ooze

- Level layer: `docs/campaign/levels/LEVEL_19_CAVERNS_OF_OOZE.md`

- Canonical DM map: `assets/maps/levels/map-19.01-caverns-of-ooze-dm.png`

- Player presentation map: `assets/maps/levels/map-19.01-caverns-of-ooze-player.jpg`

- Indexed keyed areas: 1–16

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. The Resplendent Grotto of Ichthyglug the Voluminous; 2. Space Orogs; 3. Ooze There?; 4. The Weeping Eye; 5. In the Grip of Ghaunadaur; 6. Cave with a View; 7. Standing Gate to Level 21; 8. Thanks for the Memories; 9. High Ground; 10. Culvert; 11. The Glittering Caverns of Jarûk the Prismatic; 12. Ghaunadaur Shrine; 13. The Scavenger; 14. Ooze Den; 15. Standing Gate to Level 17; 16. Tunnel to Level 20

### Level 20: Runestone Caverns

- Level layer: `docs/campaign/levels/LEVEL_20_RUNESTONE_CAVERNS.md`

- Canonical DM map: `assets/maps/levels/map-20.01-runestone-caverns-dm.png`

- Player presentation map: `assets/maps/levels/map-20.01-runestone-caverns-player.jpg`

- Indexed keyed areas: 1–23

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Desiccating Symbol; 2. Mad Golem’s Lair; 3. Sunken Paradise; 4. Myconid Colony; 5. Giggling Chasm; 6. Lair of the Mummy Lord; 7. Crypt Raiders; 8. Made of Stone; 9. Way to the Gate; 10. Mad Mage’s Puzzle; 11. Weird Magic; 12. Old Behir Lair; 13. Runestone Caverns; 14. The Runestone; 15. Outer Door and Foyer; 16. Animated Staff; 17. Lich’s Study; 18. Gnomes’ Landing; 19. Ezzat’s Scrying Mirror; 20. Laboratory; 21. Lit Landing; 22. Rooms of Magic; 23. Ezzat’s Phylactery

### Level 21: Terminus Level

- Level layer: `docs/campaign/levels/LEVEL_21_TERMINUS_LEVEL.md`

- Canonical DM map: `assets/maps/levels/map-21.01-terminus-level-dm.png`

- Player presentation map: `assets/maps/levels/map-21.01-terminus-level-player.jpg`

- Indexed keyed areas: 1–24

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Entrance; 2. Ore-Filled Cart; 3. Depleted Mine; 4. Deeper Mines; 5. Rubble-Strewn Cavern; 6. Duergar Outpost; 7. Cleric’s End; 8. Mining Equipment; 9. Miners’ Quarters; 10. Common Areas; 11. Kitchen and Pantry; 12. Miners’ Potty; 13. Grand Vestibule; 14. Shrine of Laduguer; 15. Valtagar’s Quarters; 16. Fire and Iron; 17. Hammers and Anvils; 18. Iron Mine; 19. Outpost; 20. Poisonous Mine; 21. Clean Air Station; 22. Guard Post; 23. Fazrian’s Court; 24. Secret Vault

### Level 22: Shadowdusk Hold

- Level layer: `docs/campaign/levels/LEVEL_22_SHADOWDUSK_HOLD.md`

- Canonical DM map: `assets/maps/levels/map-22.01-shadowdusk-hold-dm.png`

- Player presentation map: `assets/maps/levels/map-22.01-shadowdusk-hold-player.jpg`

- Indexed keyed areas: 1–41

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. Grand Foyer; 2. Twisted Gallery; 3. West Wing; 4. Decayed Quarters; 5. Storeroom; 6. Kitchen; 7. Derelict Shrine; 8. Nothic’s Niche; 9. East Wing; 10. Noble Quarters; 11. Melissara’s Study; 12. Lounge; 13. Walking Dead; 14. Training Room; 15. Fountain; 16. Arcane Sanctum; 17. Vertrand’s Room; 18. Berlain’s Suite; 19. Shadowdusk Hold Fresco; 20. Pillared Hall; 21. Parlor; 22. Torm’s Shrine; 23. Meditation Rooms; 24. Nothic Warrens; 25. Abandoned Chamber; 26. Hoarded Secrets; 27. Privy; 28. Legacy of Xerrion; 29. Landing; 30. Lower Halls; 31. Approach to Madness; 32. Far and Gone; 33. Shrine; 34. Zalthar’s Chambers; 35. Eyes of Stone; 36. Vacant Rooms; 37. Secret Room; 38. Dezmyr’s Chambers; 39. Dracolich’s Phylactery; 40. Lynnorax’s Lair; 41. Shadowdusk Vault

### Level 23: Mad Wizard’s Lair

- Level layer: `docs/campaign/levels/LEVEL_23_MAD_WIZARD_S_LAIR.md`

- Canonical DM map: `assets/maps/levels/map-23.01-mad-wizards-lair-dm.png`

- Player presentation map: `assets/maps/levels/map-23.01-mad-wizards-lair-player.jpg`

- Indexed keyed areas: 1–36

- Room binding: source area number ↔ same-numbered map area.

- Indexed room headings: 1. No Retreat; 2. Reversed Library; 3. Talking Heads; 4. Helmed Horrors; 5. Magical Repository; 6. Wizardly Wards; 7. Teleportation Pillars; 8. Teleportation Pillars; 9. Vaults; 10. Arcane Display; 11. Trobriand’s Workshop; 12. Gate to the Stone Bridge; 13. The Metal Mage; 14. Man with the Rabbit’s Head; 15. Gate to Neverlight Grove; 16. Broom Room; 17. Arcturia’s Court; 18. Animated Hallway; 19. Double Door Roulette; 20. Hidden Helm; 21. Displaced Vault; 22. Tower Entrance; 23. Gnome with No Name; 24. Potion Brewery; 25. Factory; 26. Gate to Icewind Dale; 27. Rantantar’s Wand; 28. Hidden Treasure; 29. Apprentice Portraits; 30. Scrying Room; 31. Art Studio; 32. Jhesiyra’s Warning; 33. Mad Mage Showdown; 34. Flying Saucer; 35. Exercise Room; 36. Gate to Triboar

## Skullport Bindings

### Skull Island
- Canonical DM map: `assets/maps/skullport/map-24.01-skull-island-dm.png`
- Player presentation map: `assets/maps/skullport/map-24.01-skull-island-player.jpg`

### Skullport Lower and Middle Levels
- Canonical DM map: `assets/maps/skullport/map-24.02-skullport-lower-and-middle-levels-dm.png`
- Player presentation map: `assets/maps/skullport/map-24.02-skullport-lower-and-middle-levels-player.jpg`

### Skullport Upper Level
- Canonical DM map: `assets/maps/skullport/map-24.03-skullport-upper-level-dm.png`
- Player presentation map: `assets/maps/skullport/map-24.03-skullport-upper-level-player.jpg`

## Runtime Load Rule

When entering or resuming a level, resolve `level_id` through this index, load the corresponding level story layer and canonical DM map, then retrieve the current keyed-room text. Navigation and spatial adjudication must use the map, not remembered prose or improvised layout.