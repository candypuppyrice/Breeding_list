# Impossible Animals on Roblox — Breeding Tracker

A Python memory tool for the Roblox game **Impossible Animals**. Track animals, record breeding pairs and star scores, suggest pairs you have not tried, and find your highest-star combinations.

This tool does not control Roblox or scan game icons.

## Setup

Python 3.10 or newer is recommended. The memory and pair planner need no extra packages.

## Run on this computer

1. Double-click `SEND_COMMAND.bat` to open the command menu. It stays open for repeated commands; choose `0` to exit.
2. The menu starts the processor automatically and displays its response. You do not need to open `START_CONTROLLER.bat` first.
3. Animal names and breeding history are saved in `impossible_animals_memory.json`; the latest structured response is saved in `result.json`.
4. Menu option 1 shows the animal count, tried/untried/total pairs, and the number of distinct pairs at each best-star score.
5. Menu option 5 shows how many distinct pairs have each best-star score, then lets you choose one exact star score and how many matching pairs to display.
6. Menu option 6 lets you select a current star score, choose a numbered pair from that group, and enter its corrected score.
7. Menu option 7 asks for one animal name and shows the five recorded pairs involving it with the highest star scores.

The menu is a local folder-based interface. It does not accept commands from this chat automatically. Add animals and record observed results. The system normalizes pair order, so `Cat + Dragon` and `Dragon + Cat` refer to the same pair. `untried` lists every pair of known animals with no recorded result. The planner does not suggest an animal combined with itself.

You can also issue commands from a terminal:

```text
py impossible_animals.py next
py impossible_animals.py untried
py impossible_animals.py record Cat Dragon 5
py impossible_animals.py list
```

`untried` lists every pair of known animals with no recorded result. `next` suggests an unrecorded pair first, then uses recorded high-star pairs with occasional exploration. Pair order is normalized, and new records store only the parent animals and stars.

The helper learns from results entered with the `record` command: it stores attempts and updates average stars for pair recommendations. The versioned JSON format accepts new animal names and scores without code changes.

For the folder controller, record results with `{"action":"record","animal_a":"Cat","animal_b":"Dragon","stars":9}`.
