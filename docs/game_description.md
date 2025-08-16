## Aquawar: The Unofficial Manual

### 1. Game Objective

Aquawar is a one-on-one, turn-based strategy game. The match is a **best-of-three**, meaning the first player to win two rounds is the ultimate victor.

Each round, players secretly select a team of 4 fish from a roster of 12. They then battle until one player's team is eliminated.

### 2. Core Concepts

#### 2.1 Fish Attributes
Every fish in the game has the following attributes:
* **Health (HP):** All fish start with **400 HP**, which is also their maximum HP. A fish is defeated and removed from combat when its HP drops to 0 or below.
* **Attack (ATK):** All fish start with **100 ATK**. This value can be increased by certain skills.
* **Passive Skill:** An ability that triggers automatically when its specific conditions are met. Players cannot choose whether or not to activate it.
* **Active Skill:** An ability that a player can choose to use during a fish's action turn instead of a Normal Attack.

#### 2.2 Hidden Identity & The Assertion Mechanism
This is the central mechanic of Aquawar.
* **Hidden Identity:** At the start of a round, all fish are in a **hidden state**. You know your own fishes' identities, but your opponent only sees generic, unidentified fish. An identity remains hidden until it is revealed through Assertion, even if the fish is defeated.
* **Assertion:** At the very beginning of your turn (before you choose a fish to act), you may choose to **Assert** the identity of **one** living, hidden enemy fish.
    * **Assertion Success:** If you correctly guess the fish's identity, that fish is permanently revealed. Additionally, **all enemy fish lose 50 HP**.
    * **Assertion Failure:** If your guess is wrong, **all of your own fish lose 50 HP**.
* **Important Note on HP Loss:** The 50 HP loss from a successful or failed Assertion is a direct health reduction. It is **not** considered "damage" or a "direct attack," and therefore will not trigger skills that react to taking damage.
* **The Mimic Fish Rule:** To successfully assert a Mimic Fish, you must declare it as a **Mimic Fish**. Guessing the identity of the fish it is imitating will result in a failed Assertion.

### 3. Game Flow

A full game consists of up to three rounds. Each round follows this sequence:

#### 3.1 First Turn
In Round 1, the player who goes first is chosen randomly. For all subsequent rounds, the **winner of the previous round will go second**.

#### 3.2 Phase 1: Selection Phase
From the pool of 12 fish, you must secretly choose 4 fish that have not been used in previous rounds.
* If you select the **Mimic Fish**, you must also secretly choose one of the other 11 fish for it to imitate.
* Once selections are made, they are locked in for the round. Both teams are placed on the battlefield in their hidden states.

#### 3.3 Phase 2: Player Turns
Players take turns until the round ends. A single player turn consists of two sub-phases:

1.  **Assertion Phase:** You decide whether to Assert an enemy's identity. You may only target one hidden, living enemy fish. You can also choose to skip this phase.
2.  **Action Phase:** You must choose one of your living fish to perform an action. The available actions are:
    * **Normal Attack:** Target a single enemy fish. Deals damage equal to 50% of the attacker's current ATK (e.g., 50 damage at the base 100 ATK).
    * **Use Active Skill:** Activate the fish's unique active skill. The effects are detailed in the "Fish Roster" section below.

#### 3.4 Winning a Round
A round ends when one of the following conditions is met:

* **Elimination:** One player has no living fish remaining. The player with surviving fish wins the round.
* **Mutual Destruction:** If an action causes all remaining fish on both teams to be defeated simultaneously, the player who performed that final action wins the round.
* **Turn Limit Reached:** A round has a maximum of **64 turns** (32 turns for each player). If the round timer expires and both players have fish remaining, the winner is decided by the following tiebreakers, in order:
    1.  The player with more fish on the field wins.
    2.  If fish counts are equal, the player with the higher total remaining HP across all their fish wins.
    3.  If total HP is also equal, the player whose single fish has the highest HP wins.
    4.  If all of the above are still tied, the player who went **second** in that round wins.

* **Forfeit by Error:** If a player's AI produces a runtime error, exceeds the 3-second time limit for any decision (Pick, Assert, or Act), or attempts an illegal move, they immediately lose the entire game.

### 4. Advanced Mechanics & Rule Clarifications

#### 4.1 Key Terminology
* **Direct Attack:** An action in the Action Phase where a fish uses its **Normal Attack** or an **Active Skill** to inflict damage on an enemy. The acting fish is the **source**.
* **Damage:** Any loss of HP resulting from attacks or skills. This does *not* include the HP reduction from the Assertion mechanism.
* **Teammate:** Any other friendly fish on the field, not including the fish itself.
* **Delayed Effects ("Next time..."):** Some skills apply a lingering effect, such as "the next time this fish is directly attacked..." These effects do not stack with themselves (e.g., you cannot have "the next two times..." or double the potency). The effect is consumed when its condition is met.

#### 4.2 Order of Operations for Effects
When an attack occurs, multiple skills can trigger. They are resolved in this precise order:

1.  **Pre-Damage Trigger (`Before taking damage`):**
    * This is when Dodge skills (Sea Wolf, Manta Ray) and Shield skills (Sea Turtle) activate.
    * If a shield absorbs the damage or a dodge is successful, the fish is considered to have **not taken damage**. This means effects that trigger "when taking damage" or "after taking damage" will not activate.

2.  **On-Damage Trigger (`When taking damage`):**
    * This is when damage-sharing passives (Electric Eel, Sunfish) and delayed damage-reduction/damage-sharing effects activate. These only trigger from **Direct Attacks**.
    * Priority: Passive Damage Sharing > Delayed Damage Reduction > Delayed Damage Sharing.

3.  **Damage Application:**
    * The fish's HP is deducted after all "When taking damage" effects are calculated.

4.  **Post-Damage Trigger (`After taking damage`):**
    * This is when healing effects activate.
    * Priority: Delayed Healing Effect > Passive Healing Skill.

5.  **Post-Attack Trigger (`After being directly attacked`):**
    * This trigger occurs even if the damage was fully dodged or shielded.
    * This is when retaliation skills (Archerfish, Clownfish) and death-rattle skills (Hammerhead Shark) activate.
    * Priority: Low-HP Retaliation / Death-Rattle > Teammate-Protection Retaliation.

#### 4.3 Specific Interaction Rules
* **Survival Status Lock-in:** A fish's living/dead status is only updated *after* a complete action resolves. If a fish is alive at the start of an action, it is considered alive for the entire duration of that action for the purpose of skill calculations, even if it takes lethal damage midway through.
* **No Revival:** Healing effects cannot resurrect a fish. If a single instance of damage reduces a fish's HP to 0 or below, it is defeated immediately and cannot be healed back to life by post-damage healing triggers from that same action.
* **Damage Calculation Lock-in:** Damage values based on a fish's ATK are calculated using the ATK stat as it was **at the start of the action**. Any ATK increases that occur mid-action will not affect the damage of the current ongoing action.
* **Resolution Order:** When an effect targets multiple fish simultaneously (like an Area of Effect attack), the effects are resolved on each fish one by one, based on their position number (from lowest to highest, e.g., 0 -> 1 -> 2 -> 3). If resolving an effect on one fish triggers a new effect, that new effect is inserted into the queue and resolved immediately before moving to the next original target.

### 5. The Fish Roster (Skills & Abilities)

*All fish have a base of 400 HP and 100 ATK.*

---
**1. Archerfish**
* **Passive:** After a teammate is directly attacked, if its HP is below 30% (120 HP), deal 30 damage to the attacker.
* **Active:** Attacks all enemy targets, dealing damage equal to 35% of ATK to each.

---
**2. Pufferfish (喷火鱼 - "Fire-spitting fish")**
* **Passive:** After a teammate is directly attacked, if its HP is below 30% (120 HP), deal 30 damage to the attacker.
* **Active:** Deals 50 damage to one teammate, and in return, **permanently** increases its own ATK by 70.

---
**3. Electric Eel**
* **Passive:** When taking damage from a direct enemy attack, if teammates are alive, this fish takes 70% of the damage and the remaining 30% is split evenly among living teammates. For every 200 total damage this fish takes, its ATK **permanently** increases by 20.
* **Active:** Attacks all enemy targets, dealing damage equal to 35% of ATK to each.

---
**4. Sunfish**
* **Passive:** When taking damage from a direct enemy attack, if teammates are alive, this fish takes 70% of the damage and the remaining 30% is split evenly among living teammates. For every 200 total damage this fish takes, its ATK **permanently** increases by 20.
* **Active:** Deals 50 damage to one teammate, and in return, **permanently** increases its own ATK by 70.

---
**5. Sea Wolf**
* **Passive:** Has a 30% chance to dodge any incoming damage.
* **Active:** Deals 120 critical damage to a single enemy.

---
**6. Manta Ray**
* **Passive:** Has a 30% chance to dodge any incoming damage.
* **Active:** Choose a teammate (can be self). The next time it takes damage from a direct attack, the damage is reduced by 70%. Using this skill also **permanently** increases this fish's own ATK by 20.

---
**7. Sea Turtle**
* **Passive:** Starts with 3 shields. Each shield completely blocks one instance of incoming damage. After all 3 shields are gone, this fish gains a 30% chance to dodge any incoming damage.
* **Active:** Choose a teammate. The next time it takes damage from a direct attack, if it survives, it will heal for 20 HP afterward. **Additionally**, if this is one of the first three times you have used this active skill, you also deal 120 critical damage to one enemy.

---
**8. Octopus**
* **Passive:** After taking damage, if this fish is still alive, it heals for 20 HP.
* **Active:** Choose a teammate (can be self). The next time it takes damage from a direct attack, the damage is reduced by 70%. Using this skill also **permanently** increases this fish's own ATK by 20.

---
**9. Great White Shark**
* **Passive:** After taking damage, if this fish is still alive, it heals for 20 HP.
* **Active:** Attacks the enemy with the lowest current HP. Deals damage equal to 120% of ATK. If the target's HP is below 40% (160 HP), it deals 140% of ATK instead.

---
**10. Hammerhead Shark**
* **Passive:** If this fish is defeated by a direct attack, it explodes, dealing 40 damage to the attacker. When this fish's HP is below 20% (80 HP), its ATK is increased by 15.
* **Active:** Attacks the enemy with the lowest current HP. Deals damage equal to 120% of ATK. If the target's HP is below 40% (160 HP), it deals 140% of ATK instead.

---
**11. Clownfish**
* **Passive:** After this fish is directly attacked, if its HP is below 30% (120 HP), it deals 30 damage to the attacker.
* **Active:** Choose a teammate. The next time it takes damage from a direct attack, it will only take 70% of the damage, and the remaining 30% will be split evenly among other living teammates. **Additionally**, if this is one of the first three times you have used this active skill, you also deal damage equal to 35% of ATK to all enemies.

---
**12. Mimic Fish**
* **Passive:** Before the battle begins (during the Selection Phase), choose one of the other 11 fish. This fish copies the passive and active skills of the chosen fish for the entire round.
* **Active:** None (uses the copied skill).

### Information Disclosure: What You Know

This game involves hidden information. Here is exactly what is revealed to both players during the game:

* **Selection Phase:** You see nothing about your opponent's choices.
* **Assertion Phase:** The result of an assertion (success or failure) is public knowledge. If successful, the revealed fish's identity is known to both players.
* **Enemy Action Phase:**
    * You **know** which enemy fish is acting and whether it used a Normal Attack or an Active Skill.
    * If a **Normal Attack** was used, the target and damage dealt are known.
    * If an **Active Skill** was used, you know its general category:
        1.  **AoE Attack:** You know all targets and the damage dealt to each.
        2.  **Harm Teammate Skill:** You know which enemy fish was damaged by its own teammate.
        3.  **Critical Strike Skill:** You know the target and the damage dealt.
        4.  **No Obvious Effect Skill:** A skill was used, but it had no immediate visible impact (e.g., applying a future damage reduction or healing buff). You receive no further information about targets or specifics.
* **Triggered Effects:** Whenever a passive or delayed skill triggers, its type and the fish it affected are public knowledge. The known categories are:
    * **Retaliation Damage:** You know which fish retaliated.
    * **Damage Sharing:** You know which fish initiated the damage sharing.
    * **Damage Reduction:** You know which fish received less damage than expected.
    * **Healing:** You know which fish healed itself.
    * **Death Rattle:** You know when a Hammerhead (or its mimic) has triggered its on-death explosion.

Any information not explicitly described above remains hidden.

***

### Potential Contradictions or Points of Ambiguity

The provided rules are remarkably detailed and consistent. There is one area that, while not a direct contradiction, requires careful reading to avoid misinterpretation:

The active skills of the **Sea Turtle** and **Clownfish** have two parts: a primary effect (applying a buff) and a secondary, offensive effect (dealing damage) that only occurs if the skill has been used three or fewer times in the game. The rules state that the player "should also choose to deal... damage" or "should also deal... damage". This phrasing implies that the buffing part of the skill can still be used after the third time, but it will no longer have the additional damage component. This isn't a contradiction, but it's a critical nuance that makes these skills change in function over the course of a game.
