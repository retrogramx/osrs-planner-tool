# Achievement Diary Rewards — Editorial Review (all 48 tiers)

> **Mobile-friendly review of `data/diary_rewards.json` (Task 9).** Derived from the committed
> data + verbatim wiki blocks. Per tier: the regional item + lamp, every **captured** effect
> (`kind` · target · the verbatim wiki phrase), and every **omitted** wiki bullet (the
> granularity disclosure). Reward prose is a *starting point, not truth* — this is your gate.

**Totals:** 48 tiers · 211 captured effects · 61 omitted bullets · 2 untracked extra-unlocks (Bonecrusher, Ash sanctifier).

### What to check
1. **Captured effects** — is each one real (the quoted phrase is verbatim from the wiki) and sensibly classified (`kind`, magnitude, target)?
2. **Omitted bullets** — should any be pulled INTO the model? (Most are cosmetic / no-benefit / item-charge tweaks with no clean target.)
3. **⚑ flags** — targets anchored to an NPC's location inferred from world-knowledge (Robin→Port Phasmatys, Lundail→Mage Arena, slayer-master→Duradel/Kuradal). OK to keep, or prefer omit/skill-anchor?

---

## Ardougne

### Easy — Ardougne cloak 1 · lamp 2,500 @30
**Captured (3):**
- `access` → region · **Ardougne Monastery** — "Unlimited teleports to the Ardougne Monastery"
- `rate_multiplier` ×2 (+100%) → activity · **West Ardougne cat trade** — "twice as many death runes from trading in cats to civilians in West Ardougne"
- `behavior_toggle` → activity · **Creature Creation** — "Drops from Jubsters and Frogeels will be noted in the Creature Creation activity"
**Omitted (0).**

### Medium — Ardougne cloak 2 · lamp 7,500 @40
**Captured (7):**
- `access` → region · **Ardougne farm** — "Three daily teleports to the farming patch at the Ardougne farm"
- `behavior_toggle` → activity · **Creature Creation** — "Drops from Unicows, Newtroosts, and Spidines will be noted in the Creature Creation activity"
- `recurring_resource` → region · **Ardougne** — "Wizard Cromperty offers you 100 noted pure essence for free every day"
- `access` → region · **Ardougne** — "Ability to change the ring of life teleport location to Ardougne"
- `rate_multiplier` → activity · **Ourania Altar** — "Chance on receiving additional runes at the Ourania Altar"
- `rate_multiplier` +10% → skill · **Thieving** — "10% increased chance of successfully pickpocketing within Ardougne"
- `capacity_change` → skill · **Thieving** — "Hold up to 56 coin pouches at a time, up from 28"
**Omitted (0).**

### Hard — Ardougne cloak 3 · lamp 15,000 @50
**Captured (5):**
- `access` → region · **Ardougne farm** — "Five daily teleports to the farming patch at the Ardougne farm"
- `recurring_resource` → region · **Ardougne** — "Wizard Cromperty offers you 150 noted pure essence for free every day"
- `access` → region · **Yanille** — "Watchtower Teleport can now be used to teleport to Yanille instead"
- `rate_multiplier` +10% → skill · **Thieving** — "10% increased chance of successfully pickpocketing anywhere around Gielinor"
- `capacity_change` → skill · **Thieving** — "Hold up to 84 coin pouches at a time, up from 56"
**Omitted (0).**

### Elite — Ardougne cloak 4 · lamp 50,000 @70
**Captured (6):**
- `access` → region · **Ardougne farm** — "Unlimited teleports to the farming patch at the Ardougne farm"
- `recurring_resource` → region · **Ardougne** — "Bert automatically delivers 84 buckets of sand to your bank each day you log in"
- `recurring_resource` → region · **Ardougne** — "Wizard Cromperty offers you 250 noted pure essence for free every day"
- `rate_multiplier` +50% → activity · **Fishing Trawler** — "50% more fish from Fishing Trawler"
- `rate_multiplier` +25% → activity · **Ardougne Rooftop Course** — "25% more marks of grace from the Ardougne Rooftop Course"
- `capacity_change` → skill · **Thieving** — "Hold up to 140 coin pouches at a time, up from 84"
**Omitted (0).**

---

## Desert

### Easy — Desert amulet 1 · lamp 2,500 @30
**Captured (2):**
- `behavior_toggle` → monster · **Goat** — "Desert goat horns from goats are now noted"
- `behavior_toggle` → activity · **Artefact selling to Simon Templeton** — "Simon Templeton now also buys artefacts in noted form"
**Omitted (2):**
- ~~No benefits aside from cosmetic purposes~~
- ~~Pharaoh's sceptre will now hold up to 10 charges, up from 3~~

### Medium — Desert amulet 2 · lamp 7,500 @40
**Captured (1):**
- `access` → region · **Nardah** — "One daily teleport to Nardah"
**Omitted (1):**
- ~~Pharaoh's sceptre will now hold up to 25 charges, up from 10~~

### Hard — Desert amulet 3 · lamp 15,000 @50
**Captured (5):**
- `fee_waiver` → region · **Kharidian Desert** — "Free carpet rides throughout the Kharidian Desert, down from a fee of 75-200 coins per ride"
- `stat_multiplier` +14% → skill · **Agility** — "Roughly 14% increased experience and 25% more marks of grace from the Pollnivneach Rooftop Course"
- `rate_multiplier` +25% → activity · **Pollnivneach Rooftop Course** — "25% more marks of grace from the Pollnivneach Rooftop Course"
- `access` → region · **Enakhra's Temple** — "Camulet can now be rubbed to teleport to the entrance of Enakhra's Temple"
- `behavior_toggle` → skill · **Herblore** — "Zahur now also cleans grimy herbs in noted form, and offers her potion-making services"
**Omitted (3):**
- ~~No new benefits~~
- ~~Pharaoh's sceptre will now hold up to 50 charges, up from 25~~
- ~~Ropes are now permanently secured once placed at the Kalphite Lair entrance and Queen's Lair~~

### Elite — Desert amulet 4 · lamp 50,000 @70
**Captured (4):**
- `access` → region · **Nardah** — "Unlimited teleports to Nardah, closer to the Elidinis Statuette than the previous amulets"
- `access` → region · **Kalphite Cave** — "Unlimited teleports to the entrance of the Kalphite Cave"
- `fee_waiver` → region · **Shantay Pass** — "Free passage through Shantay Pass and the similar pass at Ruins of Unkah, down from a fee of 5 coins"
- `access` → region · **Kalphite Lair** — "Access to the crevice shortcut in the Kalphite Lair (with 86 Agility)"
**Omitted (2):**
- ~~Fully protects against desert heat while worn~~
- ~~Pharaoh's sceptre will now hold up to 100 charges, up from 50~~

---

## Falador

### Easy — Falador shield 1 · lamp 2,500 @30
**Captured (2):**
- `recurring_resource` → skill · **Prayer** — "Can restore 25% of prayer points once a day"
- `access` → region · **Chaos Temple** — "Access to the tight-gap shortcut from Burthorpe to the Chaos Temple"
**Omitted (0).**

### Medium — Falador shield 2 · lamp 7,500 @40
**Captured (4):**
- `recurring_resource` → skill · **Prayer** — "Can restore 50% of prayer points once a day"
- `stat_multiplier` +10% → skill · **Farming** — "10% more experience from the Falador farming patch"
- `access` → activity · **Motherlode Mine** — "Access to the dark tunnel shortcut in the Motherlode Mine"
- `rate_multiplier` +21% → monster · **Guard** — "21% increased chance of receiving a medium clue scroll from a guard in Falador"
**Omitted (0).**

### Hard — Falador shield 3 · lamp 15,000 @50
**Captured (5):**
- `recurring_resource` → skill · **Prayer** — "Can restore full prayer points once a day"
- `behavior_toggle` → monster · **Giant Mole** · *while-equipped* — "Indicates the Giant Mole's location when equipped or held in the inventory in the Mole Hole"
- `behavior_toggle` → monster · **Giant Mole** — "The Giant Mole's mole skin and claw drops will be noted"
- `access` → region · **Crafting Guild** — "Access to the bank chest and bank deposit box in the Crafting Guild"
- `access` → region · **Heroes' Guild** — "Access to the shortcut to the Fountain of Heroes in the Heroes' Guild basement"
**Omitted (0).**

### Elite — Falador shield 4 · lamp 50,000 @70
**Captured (4):**
- `recurring_resource` → skill · **Prayer** — "Can restore full prayer points twice a day"
- `behavior_toggle` → region · **Falador Park** — "The tree patch in Falador Park will never get diseased"
- `access` → region · **Mining Guild** — "Access to the larger amethyst mine in the west of the Mining Guild"
- `rate_multiplier` +1% → activity · **Motherlode Mine** — "Slightly increased chance of receiving higher level ores when cleaning pay-dirt, by about 1% per ore"
**Omitted (0).**

---

## Fremennik

### Easy — Fremennik sea boots 1 · lamp 2,500 @30
**Captured (1):**
- `access` → region · **Rellekka marketplace** — "One daily teleport to the Rellekka marketplace"
**Omitted (3):**
- ~~Peer the Seer will act as a bank deposit box~~
- ~~Fossegrimen gives your enchanted lyre an extra charge per offering~~
- ~~Fossegrimen will imbue your lyre with infinite charges for 800 of each required fish, down from 1,000~~

### Medium — Fremennik sea boots 2 · lamp 7,500 @40
**Captured (2):**
- `access` → region · **Rellekka marketplace** — "Three daily teleports to the Rellekka marketplace"
- `rate_multiplier` +10% → activity · **Managing Miscellania** — "10% increased chance of gaining approval in Managing Miscellania"
**Omitted (1):**
- ~~Fossegrimen will imbue your lyre with infinite charges for 600 of each required fish, down from 800~~

### Hard — Fremennik sea boots 3 · lamp 15,000 @50
**Captured (6):**
- `access` → region · **Rellekka marketplace** — "Five daily teleports to the Rellekka marketplace"
- `stat_multiplier` +18% → activity · **Rellekka Rooftop Course** — "Roughly 18% increased experience and 25% more marks of grace from the Rellekka Rooftop Course"
- `rate_multiplier` +25% → activity · **Rellekka Rooftop Course** — "25% more marks of grace from the Rellekka Rooftop Course"
- `behavior_toggle` → activity · **God Wars Dungeon** — "Adamantite bars from aviansie killed in the God Wars Dungeon are now noted"
- `access` → region · **Waterbirth Island** — "Enchanted lyre and its imbued variant can now be played to teleport to Waterbirth Island"
- `access` → region · **Troll Stronghold** — "Stony basalt now teleports you on top of the Troll Stronghold"
**Omitted (3):**
- ~~Access to Tan Leather and Recharge Dragonstone from the Lunar spellbook~~
- ~~Fossegrimen will imbue your lyre with infinite charges for 400 of each required fish, down from 600~~
- ~~Access to Bosun Zarah as a crewmate after the completion of Royal Trouble (requires 80 Sailing)~~

### Elite — Fremennik sea boots 4 · lamp 50,000 @70
**Captured (5):**
- `access` → region · **Rellekka marketplace** — "Unlimited teleports to the Rellekka marketplace"
- `behavior_toggle` → monster · **Dagannoth Kings** — "Dagannoth bones from the Dagannoth Kings are now noted"
- `rate_multiplier` +15% → activity · **Managing Miscellania** — "15% increased chance of gaining approval in Managing Miscellania"
- `access` → region · **Waterbirth Island** — "Enchanted lyre and its imbued variant can now be played to teleport to Waterbirth Island, Jatizso, and Neitiznot"
- `access` → region · **Lunar Isle** — "The seal of passage is no longer needed to interact with anyone on Lunar Isle"
**Omitted (1):**
- ~~Fossegrimen will imbue your lyre with infinite charges for 200 of each required fish, down from 400~~

---

## Kandarin

### Easy — Kandarin headgear 1 · lamp 2,500 @30
**Captured (4):**
- `rate_multiplier` ×2 (+100%) → skill · **Woodcutting** · *while-equipped* — "gain double logs from regular trees"
- `capacity_change` → skill · **Mining** — "Coal trucks can hold up to 140 coal, up from 120"
- `recurring_resource` → skill · **Crafting** — "30 noted bow strings every day for 30 noted flax"
- `rate_multiplier` +5% → activity · **Seers' Village Rooftop Course** — "5% more marks of grace from the Seers' Village Rooftop Course"
**Omitted (1):**
- ~~Acts as a light source when worn or held in the inventory~~

### Medium — Kandarin headgear 2 · lamp 7,500 @40
**Captured (5):**
- `capacity_change` → skill · **Mining** — "Coal trucks can hold up to 280 coal, up from 140"
- `recurring_resource` → skill · **Crafting** — "60 noted bow strings every day for 60 noted flax"
- `rate_multiplier` +10% → activity · **Seers' Village Rooftop Course** — "10% more marks of grace from the Seers' Village Rooftop Course"
- `stat_multiplier` +10% → skill · **Woodcutting** — "10% increased experience from cutting maple trees in Seers' Village"
- `rate_multiplier` +5% → skill · **Farming** — "5% increased chance to save a "harvest life" at the herb patch in Catherby"
**Omitted (3):**
- ~~No new benefits~~
- ~~The spinning wheel in Seers' Village spins 33% faster~~
- ~~Ropes are now permanently secured at the Baxtorian Falls (with the completion of Waterfall Quest)~~

### Hard — Kandarin headgear 3 · lamp 15,000 @50
**Captured (8):**
- `access` → region · **Sherlock** — "One daily teleport to Sherlock"
- `capacity_change` → skill · **Mining** — "Coal trucks can hold up to 308 coal, up from 280"
- `recurring_resource` → skill · **Crafting** — "120 noted bow strings every day for 120 noted flax"
- `rate_multiplier` +15% → activity · **Seers' Village Rooftop Course** — "15% more marks of grace from the Seers' Village Rooftop Course"
- `rate_multiplier` +10% → skill · **Farming** — "10% increased chance to save a "harvest life" at the herb patch in Catherby"
- `fee_waiver` +25% → activity · **Thormac's enchanting services** — "25% discount on Thormacs' enchanting services"
- `rate_multiplier` +10% → activity · **Barbarian Assault** — "10% more honour points from Barbarian Assault"
- `access` → region · **Seers' Village bank** — "Camelot Teleport can now be used to teleport to Seers' Village bank instead"
**Omitted (1):**
- ~~10% increased chance to trigger the special effect of enchanted bolts, even in PvP (stacks additively with other increases, such as that of the Armadyl crossbow's special attack)~~

### Elite — Kandarin headgear 4 · lamp 50,000 @70
**Captured (5):**
- `access` → region · **Sherlock** — "Unlimited teleports to Sherlock"
- `recurring_resource` → skill · **Mining** — "first 200 coal placed in the coal trucks every day will automatically be transported to your bank"
- `recurring_resource` → skill · **Crafting** — "250 noted bow strings every day for 250 noted flax"
- `rate_multiplier` +15% → skill · **Farming** — "15% increased chance to save a "harvest life" at the herb patch in Catherby"
- `fee_waiver` +50% → activity · **Thormac's enchanting services** — "50% discount on Thormacs' enchanting services"
**Omitted (0).**

---

## Karamja

### Easy — Karamja gloves 1 · lamp 1,000 @any-level
**Captured (2):**
- `fee_waiver` → region · **Brimhaven** · *while-equipped* — "boat trips cost 15 coins instead of 30 coins"
- `fee_waiver` → region · **Karamja** · *while-equipped* — "items in various shops around Karamja are sold at a discounted rate and bought for more"
**Omitted (0).**

### Medium — Karamja gloves 2 · lamp 5,000 @30
**Captured (2):**
- `stat_multiplier` +10% → skill · **Agility** · *while-equipped* — "10% additional Agility experience from all obstacles in the Brimhaven Agility Arena"
- `access` → region · **Shilo Village mine** — "Access to the underground portion of the Shilo Village mine"
**Omitted (0).**

### Hard — Karamja gloves 3 · lamp 10,000 @40
**Captured (2):**
- `access` → region · **Shilo Village mine** — "Unlimited teleports to the underground portion of the Shilo Village mine"
- `fee_waiver` → region · **Karamja** — "are now also affected by the gloves' discounted store prices"
**Omitted (0).**

### Elite — Karamja gloves 4 · lamp 50,000 @70
**Captured (9):**
- `access` → region · **Duradel/Kuradal** ⚑ — "Unlimited teleports to Duradel/Kuradal"
- `rate_multiplier` +10% → activity · **Brimhaven Agility Arena** — "10% chance of receiving two Agility arena tickets and Brimhaven vouchers"
- `fee_waiver` → region · **Shilo Village** — "Free usage of Shilo Village's furnace, down from a fee of 20 coins per use"
- `fee_waiver` → region · **Hardwood Grove** — "Free access to the Hardwood Grove, down from a fee of 100 trading sticks"
- `fee_waiver` → region · **Shilo Village** — "Free cart rides between Brimhaven and Shilo Village, down from a fee of 10-200 coins"
- `behavior_toggle` → region · **Brimhaven Dungeon** — "Red dragonhide from red dragons in the Brimhaven Dungeon is now noted"
- `behavior_toggle` → region · **Brimhaven Dungeon** — "Bars from metal dragons in the Brimhaven Dungeon are now noted"
- `rate_multiplier` ×2 (+100%) → activity · **Fight Cave** — "Double Tokkul from the TzHaar Fight Cave, the Inferno, and TzHaar-Ket-Rak's Challenges"
- `recurring_resource` → activity · **Fight Cave** — "Resurrect with full health and restored stats once per day when you reach 0 hitpoints in the TzHaar Fight Cave"
**Omitted (0).**

---

## Kourend & Kebos

### Easy — Rada's blessing 1 · lamp 2,500 @30
**Captured (7):**
- `access` → region · **Kourend Woodland** — "Three daily teleports to the Kourend Woodland"
- `rate_multiplier` +2% → skill · **Fishing** · *while-equipped* — "2% chance to catch two fish at once anywhere when equipped"
- `fee_waiver` → region · **Crabclaw Isle** — "Entrance fee for the Crabclaw Isle lowered to 5,000 coins, down from 10,000 coins"
- `rate_multiplier` ×2 (+100%) → monster · **Lizardman** — "Doubled chance at receiving a Xeric's talisman from lizardmen"
- `fee_waiver` +20% → activity · **Eodan's tanning services** — "20% discount on Eodan's tanning services"
- `access` → region · **Hosidius Kitchen** — "Access to the cooking ranges in the Hosidius Kitchen"
- `behavior_toggle` → region · **Hosidius** — "The farming patches in Hosidius, south of the church, will never get diseased"
**Omitted (0).**

### Medium — Rada's blessing 2 · lamp 7,500 @40
**Captured (6):**
- `access` → region · **Kourend Woodland** — "Five daily teleports to the Kourend Woodland"
- `rate_multiplier` +4% → skill · **Fishing** · *while-equipped* — "4% chance to catch two fish at once anywhere when equipped"
- `fee_waiver` → region · **Crabclaw Isle** — "Free access to Crabclaw Isle, down from a fee of 5,000 coins"
- `fee_waiver` +40% → activity · **Eodan's tanning services** — "40% discount on Eodan's tanning services"
- `rate_multiplier` +5% → skill · **Mining** — "5% chance to mine two dense essence blocks at once"
- `recurring_resource` → activity · **Thirus dynamite** — "Thirus offers you 20 dynamite for free every day"
**Omitted (1):**
- ~~Has a Prayer bonus of +1 when equipped, similar to the god blessings~~

### Hard — Rada's blessing 3 · lamp 15,000 @50
**Captured (6):**
- `access` → region · **Kourend Woodland** — "Unlimited teleports to the Kourend Woodland"
- `access` → region · **Mount Karuulm** — "Three daily teleports to the top of Mount Karuulm"
- `rate_multiplier` +6% → skill · **Fishing** · *while-equipped* — "6% chance to catch two fish at once anywhere when equipped"
- `fee_waiver` +60% → activity · **Eodan's tanning services** — "60% discount on Eodan's tanning services"
- `rate_multiplier` +5% → skill · **Farming** — "5% increased chance to save a "harvest life" at the herb patches in Hosidius and the Farming Guild"
- `recurring_resource` → activity · **Thirus dynamite** — "Thirus offers you 40 dynamite for free every day"
- 🎁 extra-unlock (untracked): **Ash sanctifier** — Ash sanctifier, claimable from Tyss
**Omitted (4):**
- ~~Has a Prayer bonus of +1 when equipped, similar to the god blessings~~
- ~~An additional item that, when carried, causes demonic ashes dropped from killed monsters to be automatically scattered, granting half the Prayer experience that would have been granted for scattering them normally~~
- ~~This item is charged with death runes~~
- ~~Any slayer helmet can be used in place of a Shayzien helm (5) for its protection against lizardman shamans, after talking to Captain Cleive (requires having the helm in your collection log)~~

### Elite — Rada's blessing 4 · lamp 50,000 @70
**Captured (10):**
- `access` → region · **Mount Karuulm** — "Unlimited teleports to the top of Mount Karuulm"
- `rate_multiplier` +8% → skill · **Fishing** · *while-equipped* — "8% chance to catch two fish at once anywhere when equipped"
- `rate_multiplier` +11% → skill · **Slayer** — "Roughly 11% more slayer reward points from Konar quo Maten's tasks"
- `rate_multiplier` +10% → region · **Hosidius Kitchen** — "10% additive success rate when using the cooking ranges in the Hosidius Kitchen"
- `behavior_toggle` → region · **Karuulm Slayer Dungeon** — "Permanent protection from the burning effect in the Karuulm Slayer Dungeon without the need for protective footwear"
- `behavior_toggle` → skill · **Prayer** — "Ashes scattered via the Ash sanctifier now grant full Prayer experience"
- `fee_waiver` +80% → activity · **Eodan's tanning services** — "80% discount on Eodan's tanning service"
- `rate_multiplier` +10% → activity · **False blood altar** — "10% additional blood runes from the false blood altar"
- `rate_multiplier` +10% → activity · **Blast Mine** — "10% increased chance of obtaining higher-tier ores in the Blast mine"
- `recurring_resource` → activity · **Thirus dynamite** — "Thirus offers you 80 dynamite for free every day"
**Omitted (1):**
- ~~Has a Prayer bonus of +2, up from +1, the highest of any item in the ammunition slot~~

---

## Lumbridge & Draynor

### Easy — Explorer's ring 1 · lamp 2,500 @30
**Captured (2):**
- `recurring_resource` → skill · **Agility** — "Can restore 50% of run energy twice a day"
- `recurring_resource` → skill · **Magic** — "Allows 30 casts of Low Level Alchemy without runes each day"
**Omitted (0).**

### Medium — Explorer's ring 2 · lamp 7,500 @40
**Captured (2):**
- `recurring_resource` → skill · **Agility** — "Can restore 50% of run energy three times a day"
- `access` → region · **South Falador Farm** — "Three daily teleports to the cabbage patch of South Falador Farm"
**Omitted (0).**

### Hard — Explorer's ring 3 · lamp 15,000 @50
**Captured (3):**
- `recurring_resource` → skill · **Agility** — "Can restore 50% of run energy four times a day"
- `access` → region · **South Falador Farm** — "Unlimited teleports to the cabbage patch of South Falador Farm"
- `stat_multiplier` +10% → activity · **Tears of Guthix** — "10% increased experience from Tears of Guthix"
**Omitted (0).**

### Elite — Explorer's ring 4 · lamp 50,000 @70
**Captured (6):**
- `recurring_resource` → skill · **Agility** — "Can restore full run energy three times a day"
- `recurring_resource` → skill · **Magic** — "Allows 30 casts of High Level Alchemy without runes each day"
- `fee_waiver` +20% → region · **Culinaromancer's Chest** — "20% discount on items in the Culinaromancer's Chest"
- `rate_multiplier` ×2 (+100%) → skill · **Thieving** — "Steal twice as many cave goblin wires in Dorgesh-Kaan"
- `access` → activity · **Fairy rings** — "Ability to use fairy rings without the need of a Dramen or Lunar staff"
- `access` → skill · **Slayer** — "Unlocks the seventh slot for blocking Slayer tasks"
**Omitted (0).**

---

## Morytania

### Easy — Morytania legs 1 · lamp 2,500 @30
**Captured (2):**
- `access` → region · **Pool of Slime** — "Two daily teleports to the Pool of Slime beneath the Ectofuntus"
- `stat_multiplier` +2.5% → skill · **Slayer** — "2.5% more Slayer experience in the Slayer Tower while on a Slayer task"
**Omitted (1):**
- ~~Ghasts in the Mort Myre Swamp will ignore you half of the time~~

### Medium — Morytania legs 2 · lamp 7,500 @40
**Captured (3):**
- `access` → region · **Pool of Slime** — "Five daily teleports to the Pool of Slime beneath the Ectofuntus"
- `recurring_resource` → region · **Port Phasmatys** ⚑ — "Robin exchanges 13 bones of any kind daily for a bucket of slime and a pot of bonemeal each"
- `stat_multiplier` +5% → skill · **Slayer** — "5% more Slayer experience in the Slayer Tower while on a Slayer task"
**Omitted (1):**
- ~~Acts as a ghostspeak amulet when worn~~

### Hard — Morytania legs 3 · lamp 15,000 @50
**Captured (6):**
- `access` → region · **Burgh de Rott** — "Unlimited teleports to Burgh de Rott"
- `recurring_resource` → region · **Port Phasmatys** ⚑ — "Robin exchanges 26 bones of any kind daily for a bucket of slime and a pot of bonemeal each"
- `rate_multiplier` ×2 (+100%) → region · **Mort Myre Swamp** — "Double Mort myre fungi when casting Bloom"
- `stat_multiplier` +50% → skill · **Prayer** — "50% more Prayer experience from burning shade remains"
- `rate_multiplier` +50% → activity · **Barrows** — "50% more runes from the Barrows chest"
- `stat_multiplier` +7.5% → skill · **Slayer** — "7.5% more Slayer experience in the Slayer Tower while on a Slayer task"
- 🎁 extra-unlock (untracked): **Bonecrusher** — Bonecrusher, claimable from a ghost disciple while wearing a ghostspeak amulet or Morytania legs 3+
**Omitted (2):**
- ~~An additional item that, when carried, causes bones dropped from killed monsters to be automatically buried, granting half the usual Prayer experience that would have been granted for burying them normally~~
- ~~This item is charged with a small amount of ecto-tokens~~

### Elite — Morytania legs 4 · lamp 50,000 @70
**Captured (6):**
- `access` → region · **Pool of Slime** — "Unlimited teleports to the Pool of Slime beneath the Ectofuntus"
- `recurring_resource` → region · **Port Phasmatys** ⚑ — "Robin exchanges 39 bones of any kind daily for a bucket of slime and a pot of bonemeal each"
- `stat_multiplier` +50% → skill · **Firemaking** — "50% more Firemaking experience when burning shade remains"
- `behavior_toggle` → skill · **Prayer** — "Bones buried via the Bonecrusher now grant full Prayer experience"
- `access` → region · **Harmony Island** — "Access to the disease-free herb patch on Harmony Island"
- `stat_multiplier` +10% → skill · **Slayer** — "10% more Slayer experience in the Slayer Tower while on a Slayer task"
**Omitted (1):**
- ~~Prevents ghasts from turning your food into rotten food when worn~~

---

## Varrock

### Easy — Varrock armour 1 · lamp 2,500 @30
**Captured (3):**
- `rate_multiplier` +10% → skill · **Mining** · *while-equipped* — "10% chance of mining double clay, limestone, guardian fragments, tephra, and ores up to and including gold"
- `rate_multiplier` +10% → skill · **Smithing** · *while-equipped* — "10% chance of smelting 2 bars at once, up to steel, when using the Edgeville furnace"
- `recurring_resource` → region · **Varrock** — "Zaff will sell you 15 noted battlestaves as a single stack every day"
**Omitted (2):**
- ~~The skull sceptre will now hold up to 14 charges, up from 10~~
- ~~Individual parts used to make the skull sceptre now give an extra bone fragment per component when chiselled~~

### Medium — Varrock armour 2 · lamp 7,500 @40
**Captured (4):**
- `rate_multiplier` +10% → skill · **Mining** · *while-equipped* — "10% chance of mining double ores up to and including mithril"
- `rate_multiplier` +10% → skill · **Smithing** · *while-equipped* — "10% chance of smelting 2 bars at once, up to and including mithril, when using the Edgeville furnace"
- `recurring_resource` → region · **Varrock** — "Zaff will sell you 30 noted battlestaves as a single stack every day"
- `access` → region · **Grand Exchange** — "toggle the destination of Varrock Teleport from Varrock Square to the Grand Exchange"
**Omitted (2):**
- ~~The skull sceptre will now hold up to 18 charges, up from 14~~
- ~~Individual parts used to make the skull sceptre now give two extra bone fragments per component when chiselled~~

### Hard — Varrock armour 3 · lamp 15,000 @50
**Captured (5):**
- `access` → region · **Cooks' Guild** · *while-equipped* — "Can be worn in place of a chef's hat to access the Cooks' Guild"
- `rate_multiplier` +10% → skill · **Mining** · *while-equipped* — "10% chance of mining double ores up to and including adamantite"
- `rate_multiplier` +10% → skill · **Smithing** · *while-equipped* — "10% chance of smelting 2 bars at once, up to and including adamantite, when using the Edgeville furnace"
- `recurring_resource` → region · **Varrock** — "Zaff will sell you 60 noted battlestaves as a single stack every day"
- `access` → region · **Cooks' Guild** — "Access to the bank in the Cooks' Guild and a range at only 2 tiles away from it"
**Omitted (2):**
- ~~The skull sceptre will now hold up to 22 charges, up from 18~~
- ~~Individual parts used to make the skull sceptre now give three extra bone fragments per component when chiselled~~

### Elite — Varrock armour 4 · lamp 50,000 @70
**Captured (3):**
- `rate_multiplier` +10% → skill · **Mining** · *while-equipped* — "10% chance of mining double of any ore"
- `rate_multiplier` +10% → skill · **Smithing** · *while-equipped* — "10% chance of smelting 2 bars at once, of any kind, when using the Edgeville furnace"
- `recurring_resource` → region · **Varrock** — "Zaff will sell you 120 noted battlestaves as a single stack every day"
**Omitted (3):**
- ~~Can be worn in place of a prospector jacket for clue steps, and provides the experience bonus of the full outfit~~
- ~~The skull sceptre will now hold up to 26 charges, up from 22~~
- ~~Individual parts used to make the skull sceptre now give four extra bone fragments per component when chiselled~~

---

## Western Provinces

### Easy — Western banner 1 · lamp 2,500 @30
**Captured (2):**
- `rate_multiplier` +25% → activity · **Chompy bird hunting** — "25% chance of two chompy birds appearing at once when chompy bird hunting"
- `recurring_resource` → activity · **Chompy bird hunting** — "Rantz offers you 25 ogre arrows for free every day"
**Omitted (2):**
- ~~Depicts a chompy bird~~
- ~~No benefits aside from being a crush weapon~~

### Medium — Western banner 2 · lamp 7,500 @40
**Captured (2):**
- `rate_multiplier` +50% → activity · **Chompy bird hunting** — "50% chance of two chompy birds appearing at once when chompy bird hunting"
- `recurring_resource` → activity · **Chompy bird hunting** — "Rantz offers you 50 ogre arrows for free every day"
**Omitted (2):**
- ~~Depicts King Awowogei~~
- ~~The crystal saw will now hold up to 56 charges, up from 28~~

### Hard — Western banner 3 · lamp 15,000 @50
**Captured (4):**
- `access` → region · **Piscatoris Fishing Colony** — "One daily teleport to the Piscatoris Fishing Colony"
- `recurring_resource` → activity · **Chompy bird hunting** — "Rantz offers you 100 ogre arrows for free every day"
- `access` → region · **Temple of Marimbo Dungeon** — "Access to the room with the monkey skull in the Temple of Marimbo Dungeon"
- `access` → region · **Red chinchompa hunting ground** — "Access to the Hunting expert's private Red chinchompa hunting ground"
**Omitted (4):**
- ~~Depicts a gnome child~~
- ~~Teleport crystals will now hold up to 5 charges, up from 3~~
- ~~The void knight top and robe can now be upgraded into an elite void top and robe for 200 commendation points each, by speaking to the Elite Void Knight~~
- ~~Islwyn now sells Crystal halberds for 750,000 coins, which can be wielded with 70 Attack and 35 Strength, and you gain the ability to create them yourself (with 78 Crafting and 78 Smithing)~~

### Elite — Western banner 4 · lamp 50,000 @70
**Captured (3):**
- `access` → region · **Piscatoris Fishing Colony** — "Unlimited teleports to the Piscatoris Fishing Colony"
- `rate_multiplier` ×2 (+100%) → activity · **Chompy bird hunting** — "Two chompy birds will always appear at once when chompy bird hunting"
- `recurring_resource` → activity · **Chompy bird hunting** — "Rantz offers you 150 ogre arrows for free every day"
**Omitted (4):**
- ~~Depicts an elven pattern~~
- ~~Chance of receiving a chompy chick when chompy bird hunting, at a rate of 1/500~~
- ~~Nieve/Steve now grant as many slayer reward points as Duradel/Kuradal~~
- ~~Resurrect with full health and restored stats once per day when you reach 0 hitpoints against Zulrah, allowing you to continue on with the fight (the task list of this diary will show you whether you've used this daily resurrection, and this is considered a "safe death" for Hardcore Ironman players)~~

---

## Wilderness

### Easy — Wilderness sword 1 · lamp 2,500 @30
**Captured (2):**
- `access` → region · **Edgeville** — "use the Wilderness lever to teleport to Edgeville"
- `recurring_resource` → region · **Mage Arena** ⚑ — "Lundail offers you 40 random runes for free every day"
**Omitted (2):**
- ~~Always slashes webs successfully~~
- ~~Identical stats to an iron sword~~

### Medium — Wilderness sword 2 · lamp 7,500 @40
**Captured (10):**
- `fee_waiver` → region · **Resource Area** — "Entrance fee for the Resource Area lowered to 6,000 coins"
- `capacity_change` → activity · **God Wars Dungeon** — "Possess up to 4 ecumenical keys at a time, up from 3"
- `recurring_resource` → region · **Mage Arena** ⚑ — "Lundail offers you 80 random runes for free every day"
- `access` → region · **Deep Wilderness Dungeon** — "Access to the crevice shortcut in the Deep Wilderness Dungeon"
- `access` → monster · **Callisto** — "Access to Callisto, Venenatis, and Vet'ion"
- `access` → monster · **Venenatis** — "Access to Callisto, Venenatis, and Vet'ion"
- `access` → monster · **Vet'ion** — "Access to Callisto, Venenatis, and Vet'ion"
- `rate_multiplier` +15% → activity · **Fallen ents** — "15% more chance to receive drops from cutting fallen ents"
- `access` → region · **Rogues' Castle** — "Ability to obtain loot from chests in the Rogues' Castle"
- `rate_multiplier` +50% → monster · **Zombie pirate** — "Zombie pirates you kill have a 50% chance of dropping something in addition to their bones"
**Omitted (1):**
- ~~Identical stats to a steel sword~~

### Hard — Wilderness sword 3 · lamp 15,000 @50
**Captured (10):**
- `access` → region · **Fountain of Rune** — "One daily teleport to the Fountain of Rune"
- `fee_waiver` → region · **Resource Area** — "Entrance fee for the Resource Area lowered to 3,750 coins"
- `capacity_change` → activity · **God Wars Dungeon** — "Possess up to 5 ecumenical keys at a time, up from 4"
- `recurring_resource` → region · **Mage Arena** ⚑ — "Lundail offers you 120 random runes for free every day"
- `rate_multiplier` +50% → activity · **Grinding lava scales** — "50% more lava shards from grinding lava scales"
- `rate_multiplier` +67% → region · **Rogues' Castle** — "67% more loot from chests in the Rogues' Castle"
- `behavior_toggle` → region · **Deep Wilderness Dungeon** — "Wine of zamorak taken from the Chaos Temple (hut) and Deep Wilderness Dungeon will now be noted"
- `access` → monster · **Spindel** — "Access to Spindel, Artio, and Calvar'ion"
- `access` → monster · **Artio** — "Access to Spindel, Artio, and Calvar'ion"
- `access` → monster · **Calvar'ion** — "Access to Spindel, Artio, and Calvar'ion"
**Omitted (4):**
- ~~Identical stats to a mithril sword (only weighs negligibly more)~~
- ~~Ecumenical keys can now be sold to the Lesser Fanatic in Edgeville for 61,500 coins each~~
- ~~You can now select your destination when using Wilderness obelisks, instead of being teleported to a random obelisk~~
- ~~You'll no longer have a delay of 3 ticks (1.8 seconds) when using a teleport in the Revenant Caves or any of the Wilderness boss caves.~~

### Elite — Wilderness sword 4 · lamp 50,000 @70
**Captured (5):**
- `access` → region · **Fountain of Rune** — "Unlimited teleports to the Fountain of Rune"
- `fee_waiver` → region · **Resource Area** — "Free access to the Resource Area, down from a fee of 3,750 coins"
- `recurring_resource` → region · **Mage Arena** ⚑ — "Lundail offers you 200 random runes for free every day"
- `behavior_toggle` → region · **Wilderness** — "Dragon bones from dragons killed in the Wilderness are now noted"
- `rate_multiplier` +112.5% → skill · **Fishing** — "Catch rate of dark crabs increased by 112.5%"
**Omitted (1):**
- ~~Identical stats to an adamant sword (only weighs negligibly less)~~

---
