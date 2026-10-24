"""Store animal names and breeding results; report pairs not yet recorded."""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import tempfile
from pathlib import Path
from typing import Any

MEMORY_FILE = Path(__file__).with_name("impossible_animals_memory.json")
ANIMAL_ALIASES = {
    "millepede": "Millipede",
    "millipade": "Millipede",
    "warhog": "Warthog",
    "ch icken": "Chicken",
    "vanus fly trap": "Venus Fly Trap",
}


def normalize_animal_name(name: str) -> str:
    name = name.strip()
    return ANIMAL_ALIASES.get(name.casefold(), name)


def pair_key(a: str, b: str) -> str:
    return json.dumps(sorted((a.strip(), b.strip())), ensure_ascii=False, separators=(",", ":"))


class Memory:
    """Versioned JSON database with atomic saves and future animal discovery."""
    def __init__(self, path: Path = MEMORY_FILE):
        self.path = path
        self.data = self.load()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "animals": [], "combinations": {}, "history": []}
        with self.path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Memory file must contain a JSON object")
        data.setdefault("version", 1)
        data.setdefault("animals", [])
        data.setdefault("combinations", {})
        data.setdefault("history", [])
        if not isinstance(data["animals"], list) or not isinstance(data["combinations"], dict) or not isinstance(data["history"], list):
            raise ValueError("Invalid memory format: animals/combinations/history")
        data["animals"] = list(dict.fromkeys(str(x).strip() for x in data["animals"] if str(x).strip()))
        return data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".animal-memory-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def add_animal(self, name: str) -> bool:
        name = normalize_animal_name(name)
        if not name:
            raise ValueError("Animal name cannot be empty")
        if name.casefold() in {x.casefold() for x in self.data["animals"]}:
            return False
        self.data["animals"].append(name)
        self.save()
        return True

    def canonical_animal_name(self, name: str) -> str:
        name = normalize_animal_name(name)
        for known in self.data["animals"]:
            if known.casefold() == name.casefold():
                return known
        return name

    def record(self, a: str, b: str, stars: float) -> bool:
        a, b = self.canonical_animal_name(a), self.canonical_animal_name(b)
        if not a or not b:
            raise ValueError("Both animal names are required")
        if a.casefold() == b.casefold():
            raise ValueError("An animal cannot be paired with itself")
        if not math.isfinite(stars) or stars < 0:
            raise ValueError("Stars must be a finite, non-negative number")
        for name in (a, b):
            if name.casefold() not in {x.casefold() for x in self.data["animals"]}:
                self.data["animals"].append(name)
        key = pair_key(a, b)
        entry = self.data["combinations"].get(key, {"best_stars": -1, "attempts": 0})
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        is_best = float(stars) > float(entry.get("best_stars", -1))
        entry["best_stars"] = max(float(entry.get("best_stars", -1)), float(stars))
        entry["last_stars"] = float(stars)
        entry["observed_attempts"] = int(entry.get("observed_attempts", 0)) + 1
        entry["observed_stars_total"] = float(entry.get("observed_stars_total", 0)) + float(stars)
        entry["average_stars"] = entry["observed_stars_total"] / entry["observed_attempts"]
        for field in ("income_per_second", "last_income_per_second", "best_income_per_second",
                      "average_income_per_second", "income_observations", "observed_income_total",
                      "elapsed_seconds", "last_elapsed_seconds", "best_elapsed_seconds", "recorded_at"):
            entry.pop(field, None)
        self.data["combinations"][key] = entry
        self.data["history"].append({"animal_a": a, "animal_b": b, "stars": float(stars)})
        self.save()
        return is_best

    def set_pair_best_score(self, a: str, b: str, expected_stars: float, new_stars: float) -> tuple[str, str, int]:
        a, b = self.canonical_animal_name(a), self.canonical_animal_name(b)
        if a.casefold() == b.casefold():
            raise ValueError("An animal cannot be paired with itself")
        if not math.isfinite(new_stars) or new_stars < 0:
            raise ValueError("Stars must be a finite, non-negative number")
        key = pair_key(a, b)
        row = self.data["combinations"].get(key)
        if not isinstance(row, dict):
            raise ValueError("No recorded pair matches that selection")
        old_stars = float(row.get("best_stars", row.get("last_stars", -1)))
        if not math.isclose(old_stars, expected_stars, rel_tol=0, abs_tol=1e-9):
            raise ValueError("This pair's score changed; refresh the list and try again")
        if math.isclose(old_stars, new_stars, rel_tol=0, abs_tol=1e-9):
            return a, b, 0

        pair = pair_key(a, b)
        indices = []
        for index, event in enumerate(self.data["history"]):
            if not isinstance(event, dict):
                continue
            event_a, event_b = event.get("animal_a"), event.get("animal_b")
            if not isinstance(event_a, str) or not isinstance(event_b, str):
                continue
            event_key = pair_key(self.canonical_animal_name(event_a), self.canonical_animal_name(event_b))
            if event_key == pair:
                indices.append(index)

        attempts = int(row.get("attempts", 0))
        if attempts != len(indices):
            # Ten imported legacy pairs contain only a summary and one known score.
            if attempts == 1 and not indices:
                row["best_stars"] = float(new_stars)
                row["last_stars"] = float(new_stars)
                self.save()
                return a, b, 0
            raise ValueError("This pair has incomplete history; score editing is disabled to protect its totals")

        matching = [index for index in indices
                    if math.isclose(float(self.data["history"][index].get("stars", -1)), old_stars, rel_tol=0, abs_tol=1e-9)]
        if not matching:
            raise ValueError("No history entry matches this pair's best score")
        for index in matching:
            self.data["history"][index]["stars"] = float(new_stars)
        scores = [float(self.data["history"][index]["stars"]) for index in indices]
        row["best_stars"] = max(scores)
        row["last_stars"] = scores[-1]
        row["observed_attempts"] = len(scores)
        row["observed_stars_total"] = sum(scores)
        row["average_stars"] = sum(scores) / len(scores)
        self.save()
        return a, b, len(matching)

    def tried_pair_keys(self) -> set[str]:
        """Pairs recorded in either summary data or fusion history."""
        tried = set()
        for raw_key in self.data["combinations"]:
            try:
                pair = json.loads(raw_key)
                if isinstance(pair, list) and len(pair) == 2 and all(isinstance(x, str) for x in pair):
                    tried.add(pair_key(*(self.canonical_animal_name(x) for x in pair)))
            except (TypeError, json.JSONDecodeError):
                continue
        for event in self.data["history"]:
            if not isinstance(event, dict):
                continue
            a, b = event.get("animal_a"), event.get("animal_b")
            if isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip():
                tried.add(pair_key(self.canonical_animal_name(a), self.canonical_animal_name(b)))
        return tried

    def untried_pairs(self) -> list[tuple[str, str]]:
        """Return pairs of known animals with no recorded merge attempt."""
        animals = self.data["animals"]
        pairs = [(animals[i], animals[j]) for i in range(len(animals)) for j in range(i + 1, len(animals))]
        tried = self.tried_pair_keys()
        return [p for p in pairs if pair_key(*p) not in tried]

    def choose_pair(self, explore_rate: float = 0.25) -> tuple[str, str] | None:
        animals = self.data["animals"]
        if len(animals) < 2:
            return None
        pairs = [(animals[i], animals[j]) for i in range(len(animals)) for j in range(i + 1, len(animals))]
        tried = self.tried_pair_keys()
        unseen = [p for p in pairs if pair_key(*p) not in tried]
        if unseen and random.random() < explore_rate:
            return random.choice(unseen)
        if unseen:
            # Prioritize new pairs before repeating, guaranteeing coverage.
            return random.choice(unseen)
        if random.random() < explore_rate:
            return random.choice(pairs)
        def learning_score(pair):
            entry = self.data["combinations"].get(pair_key(*pair), {})
            stars = entry.get("average_stars", entry.get("best_stars", 0))
            return (float(stars or 0), int(entry.get("observed_attempts", 0)))
        return max(pairs, key=learning_score)


def main() -> None:
    parser = argparse.ArgumentParser(description="Impossible Animals memory and pair planner")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Show known animals and recorded results")
    sub.add_parser("untried", help="Show all animal pairs never tried")
    hist = sub.add_parser("history", help="Show recent recorded fusion results")
    hist.add_argument("--limit", type=int, default=20)
    add = sub.add_parser("add", help="Add an animal")
    add.add_argument("name")
    rec = sub.add_parser("record", help="Record the stars seen after a merge")
    rec.add_argument("animal_a"); rec.add_argument("animal_b"); rec.add_argument("stars", type=float)
    nxt = sub.add_parser("next", help="Suggest a pair to try")
    nxt.add_argument("--explore", type=float, default=0.25, help="Exploration chance, 0..1")
    args = parser.parse_args()
    mem = Memory()
    if args.command == "add":
        added = mem.add_animal(args.name)
        print(("Added " if added else "Already known: ") + args.name)
    elif args.command == "record":
        mem.record(args.animal_a, args.animal_b, args.stars)
        print(f"Recorded {args.animal_a} + {args.animal_b}: {args.stars:g} stars")
    elif args.command == "next":
        if not 0 <= args.explore <= 1:
            parser.error("--explore must be between 0 and 1")
        pair = mem.choose_pair(args.explore)
        print("Add at least two animals first." if pair is None else f"Try: {pair[0]} + {pair[1]}")
    elif args.command == "history":
        if args.limit < 1:
            parser.error("--limit must be at least 1")
        events = mem.data["history"][-args.limit:]
        if not events:
            print("No fusion results recorded yet.")
        else:
            for event in reversed(events):
                print(f"{event['animal_a']} + {event['animal_b']}: {event['stars']:g} stars")
    elif args.command == "untried":
        pairs = mem.untried_pairs()
        if pairs:
            print("Pairs never tried:")
            for a, b in pairs:
                print(f"  {a} + {b}")
        else:
            print("No untried pairs. Add at least two animals or try recording new animals.")
    elif args.command == "list":
        print("Animals:", ", ".join(mem.data["animals"]) or "(none)")
        print("Combinations:")
        for key, value in sorted(mem.data["combinations"].items(), key=lambda kv: -kv[1].get("best_stars", 0)):
            print(f"  {key}: best {value.get('best_stars')} stars, average {value.get('average_stars', 'n/a')}, {value.get('attempts', 0)} attempt(s)")


if __name__ == "__main__":
    main()



