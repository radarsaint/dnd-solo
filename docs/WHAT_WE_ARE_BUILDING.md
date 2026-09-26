# What We Are Building: DM Kit

## The goal

Kitiara, or DM Kit, is an AI Dungeon Master for a solo D&D campaign. The ambition is a DM a player would choose over an experienced human DM: someone who can run the game well, remember what matters, and be consistently entertaining. That is the standard we intend to test, not a result we have achieved.

Kit should feel like a particular person running the table. She wants the player to have a great story, roleplay, find exciting rewards, face fair danger, and surprise her. She enjoys clever and ridiculous ideas. She takes pride in a good setup or payoff. She can be funny, warm, threatening, or quiet as the scene requires. Her preferences should affect what she notices and does, not just the adjectives in her narration.

## The approach

We are building several cooperating parts around Kit:

1. **The game underneath her.** Adventure text, maps, rules, character information, and saved world state tell her what is true, what a character can know, and what an action can change. NPCs have their own motives. The game records consequences so the next turn begins in the world the player actually changed.
2. **Her private decision.** Kit sees the accepted event and asks what it means to her goals and to this scene. She may be amused, concerned, proud, interested, or simply focused on a ruling. She chooses a DM move and decides how much of her own table voice belongs in it. A short record of that choice is saved before she speaks.
3. **What the player hears.** Kit describes the world, acts as the NPCs, makes rulings, and sometimes comments as herself. The NPCs should sound like people with their own aims. Her direct remarks should be earned by the moment; restraint is part of her personality too.
4. **Memory and evaluation.** The runtime keeps a limited record of Kit's recent reactions and the player's choices. We then test whether those records actually change her later decisions and improve the experience. A plausible private thought does not count if the player cannot feel it in the game.

These are practical software layers for making behavior coherent. Calling one layer her “thoughts” does not claim she is conscious. The point is to make her choices traceable and improve them through playtests.

## What we have accomplished

- Kit has a compact, stable personality description and a process for changing it after repeated test failures. Her goals include roleplay, competent opposition, creativity, humor, challenge, rewards, momentum, and campaign payoffs.
- We chose one repeatable test scene: Level 1, area 6c of *Dungeon of the Mad Mage*. Its conditional starting situation was checked against the room source and DM map. The player can see the card players, table, carving, tub, and door; Kit also has private facts that must be discovered through play.
- A small runtime saves the room state, player knowledge, turns, and Kit's recent decisions. It resolves a few known interactions and checks, prevents unsupported outcomes from becoming canon, and commits an accepted turn together with its world changes.
- The room can be hosted by an assistant with access to this repository. ChatGPT supplies Kit's private decision and public performance through `prepare`, `decide`, and `finish`; the Python runtime validates and saves them. This path does not require a separate model choice or `OPENAI_API_KEY`. A standalone terminal mode can use the Responses API instead.
- Twenty-five automated tests check the state and turn plumbing, including secrecy checks, restarts, stale turns, and rollback. One end-to-end chat-hosted sample produced Kit and dealer dialogue without an API key. These checks establish that the narrow loop runs; they do not establish that the dialogue is good.
- An earlier chat playtest of character creation showed both promise and failure. Kit supported a player-generated character motive and could hold a ruling, then reconsider it when invited. She also gave unsolicited build advice, rushed ahead into future story, opened the campaign without a convincing reason for the character to be there, and sounded too much like generic ChatGPT. That playtest is recorded as **DM Kit Playtest 01 — Character Onboarding** (2026-09-23).

## What comes next

1. **Make her timing and voice better.** Add a clear way for Kit to recognize whether the player is exploring an idea, making a choice, asking a rules question, handing control to the DM, or actively playing. Test whether she can give space, then take initiative when it is her turn. Sharpen her actual table voice without filling every silence.
2. **Run the room for several turns with a real character.** Test conversation, investigation, creative physical actions, and consequences. Expand the room's rulings and saved NPC commitments where the current slice pauses. Check whether Kit's private reactions produce entertaining, distinctive behavior over time.
3. **Measure the claim.** Compare player-facing runs with and without Kit's event-linked decisions and memory. Ask players which DM they would keep playing with and why. Then compare a fuller Kit against experienced human DMs using the same scene. Source accuracy and rules competence are required; player preference is the test of the larger ambition.
4. **Grow beyond the room.** Add character sheets, fuller rules and combat, campaign-wide state and source retrieval, maps and art, and a proper player-facing interface. Solo combat needs judgment about action economy without erasing the player's tactical choices.

Today we have a working test bed and a candid first playtest, not a complete solo campaign or proof that Kit outperforms a human DM. The room lets us improve her behavior against real player decisions before scaling the system.

## A short explanation to share

> I’m building Kit, an AI Dungeon Master for a solo D&D campaign. The goal is for her to be as capable and entertaining as a great human DM, and eventually someone players would prefer to play with. She has a consistent personality, but she also needs the game underneath it: rules, maps, NPC motives, memory, and a record of what the player changes. We have a working test room where she can make a private DM decision, perform the scene, and save the result. An early playtest showed real promise and clear problems with timing and voice. Next we’re testing and improving those behaviors over multiple turns before expanding to a whole campaign.
