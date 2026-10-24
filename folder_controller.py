"""Folder based command interface for the Impossible Animals memory helper.

Only command.json with one of the documented action values is executed.
Other files in the folder are treated as data and never as instructions.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from impossible_animals import Memory

BASE = Path(__file__).resolve().parent
COMMAND_FILE = BASE / "command.json"
RESULT_FILE = BASE / "result.json"
MEMORY_FILE = BASE / "impossible_animals_memory.json"
POLL_SECONDS = 0.2


def execute(command: Any, memory: Memory) -> dict[str, Any]:
    if not isinstance(command, dict) or not isinstance(command.get("action"), str):
        raise ValueError('Command must be an object with an "action" string')
    action = command["action"].strip().lower()
    if action == "add":
        name = command.get("animal")
        if not isinstance(name, str) or not name.strip():
            raise ValueError('"animal" must be a non-empty string')
        added = memory.add_animal(name)
        return {"message": "Animal added" if added else "Animal already known", "animal": name.strip()}
    if action == "record":
        a, b, stars = command.get("animal_a"), command.get("animal_b"), command.get("stars")
        if not isinstance(a, str) or not isinstance(b, str):
            raise ValueError('"animal_a" and "animal_b" must be strings')
        if isinstance(stars, bool) or not isinstance(stars, (int, float)):
            raise ValueError('"stars" must be a non-negative number')
        canonical = (memory.canonical_animal_name(a), memory.canonical_animal_name(b))
        memory.record(*canonical, float(stars))
        key = json.dumps(sorted(canonical), ensure_ascii=False, separators=(",", ":"))
        entry = memory.data["combinations"][key]
        return {"message": "Merge result recorded and learned", "animal_a": canonical[0], "animal_b": canonical[1],
                "stars": stars, "average_stars": entry.get("average_stars"),
                "attempts": entry.get("attempts")}
    if action == "edit_pair_score":
        a, b = command.get("animal_a"), command.get("animal_b")
        old_stars, new_stars = command.get("current_stars"), command.get("new_stars")
        if not isinstance(a, str) or not isinstance(b, str):
            raise ValueError('"animal_a" and "animal_b" must be strings')
        for name, value in (("current_stars", old_stars), ("new_stars", new_stars)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f'"{name}" must be a finite, non-negative number')
        a, b, updated_events = memory.set_pair_best_score(a, b, float(old_stars), float(new_stars))
        key = json.dumps(sorted((a, b)), ensure_ascii=False, separators=(",", ":"))
        entry = memory.data["combinations"][key]
        return {"message": "Pair score updated", "animal_a": a, "animal_b": b,
                "previous_stars": old_stars, "best_stars": entry.get("best_stars"),
                "updated_history_entries": updated_events}
    if action == "next":
        explore = command.get("explore", 0.25)
        if isinstance(explore, bool) or not isinstance(explore, (int, float)) or not 0 <= explore <= 1:
            raise ValueError('"explore" must be a number from 0 to 1')
        pair = memory.choose_pair(float(explore))
        return {"message": "Pair suggested" if pair else "Add at least two animals first",
                "pair": list(pair) if pair else None}
    if action == "untried":
        pairs = memory.untried_pairs()
        total_possible = len(memory.data["animals"]) * (len(memory.data["animals"]) - 1) // 2
        tried_count = total_possible - len(pairs)
        return {
            "message": f"Tried: {tried_count}; untried: {len(pairs)}; total: {total_possible}",
            "tried_count": tried_count,
            "untried_count": len(pairs),
            "total_pairs": total_possible,
            "pairs": [list(pair) for pair in pairs],
        }
    if action == "summary":
        animals = memory.data["animals"]
        known = {name.casefold() for name in animals}
        tried = set()
        for key in memory.tried_pair_keys():
            try:
                pair = json.loads(key)
            except (TypeError, json.JSONDecodeError):
                continue
            if (isinstance(pair, list) and len(pair) == 2
                    and pair[0].casefold() in known and pair[1].casefold() in known
                    and pair[0].casefold() != pair[1].casefold()):
                tried.add(key)
        best_by_pair: dict[str, float] = {}
        for raw_key, entry in memory.data["combinations"].items():
            try:
                pair = json.loads(raw_key)
                if not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(x, str) for x in pair):
                    continue
                pair = [memory.canonical_animal_name(x) for x in pair]
                if any(x.casefold() not in known for x in pair) or pair[0].casefold() == pair[1].casefold():
                    continue
                stars = float(entry.get("best_stars", entry.get("last_stars", 0)) or 0)
                if not math.isfinite(stars) or stars < 0:
                    continue
                key = json.dumps(sorted(pair), ensure_ascii=False, separators=(",", ":"))
                best_by_pair[key] = max(best_by_pair.get(key, stars), stars)
            except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
                continue
        for event in memory.data["history"]:
            if not isinstance(event, dict):
                continue
            a, b, stars = event.get("animal_a"), event.get("animal_b"), event.get("stars")
            if not isinstance(a, str) or not isinstance(b, str) or isinstance(stars, bool) or not isinstance(stars, (int, float)):
                continue
            pair = [memory.canonical_animal_name(a), memory.canonical_animal_name(b)]
            if any(x.casefold() not in known for x in pair) or pair[0].casefold() == pair[1].casefold():
                continue
            stars = float(stars)
            if not math.isfinite(stars) or stars < 0:
                continue
            key = json.dumps(sorted(pair), ensure_ascii=False, separators=(",", ":"))
            best_by_pair[key] = max(best_by_pair.get(key, stars), stars)
        star_counts: dict[float, int] = {}
        for stars in best_by_pair.values():
            star_counts[stars] = star_counts.get(stars, 0) + 1
        total_pairs = len(animals) * (len(animals) - 1) // 2
        return {
            "message": "Memory counts",
            "animal_count": len(animals),
            "tried_pair_count": len(tried),
            "untried_pair_count": total_pairs - len(tried),
            "total_possible_pairs": total_pairs,
            "star_distribution": [
                {"stars": stars, "pair_count": count}
                for stars, count in sorted(star_counts.items(), reverse=True)
            ],
        }
    if action == "list":
        display_fields = ("best_stars", "last_stars", "average_stars", "attempts", "observed_attempts")
        combinations = {
            key: {field: entry[field] for field in display_fields if field in entry}
            for key, entry in memory.data["combinations"].items()
            if isinstance(entry, dict)
        }
        return {"animals": memory.data["animals"], "combinations": combinations}
    if action == "history":
        limit = command.get("limit", 20)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError('"limit" must be an integer from 1 to 500')
        events = [
            {key: event[key] for key in ("animal_a", "animal_b", "stars") if key in event}
            for event in reversed(memory.data["history"][-limit:])
            if isinstance(event, dict)
        ]
        return {"message": "Recent fusion history", "history": events}
    if action == "top":
        minimum_stars = command.get("min_stars")
        maximum_stars = command.get("max_stars")
        limit = command.get("limit", 0)
        for field, value in (("min_stars", minimum_stars), ("max_stars", maximum_stars)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError(f'"{field}" must be a finite number')
        if minimum_stars is not None and maximum_stars is not None and minimum_stars > maximum_stars:
            raise ValueError('"min_stars" cannot be greater than "max_stars"')
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 5000:
            raise ValueError('"limit" must be a whole number from 0 to 5000')
        known = {name.casefold() for name in memory.data["animals"]}
        ranked: dict[str, dict[str, Any]] = {}
        for raw_key, entry in memory.data["combinations"].items():
            try:
                pair = json.loads(raw_key)
                if not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(x, str) for x in pair):
                    continue
                canonical_pair = [memory.canonical_animal_name(x) for x in pair]
                if any(x.casefold() not in known for x in canonical_pair):
                    continue
                key = json.dumps(sorted(canonical_pair), ensure_ascii=False, separators=(",", ":"))
                best = float(entry.get("best_stars", entry.get("last_stars", 0)) or 0)
                ranked[key] = {"best_stars": max(float(ranked.get(key, {}).get("best_stars", -1)), best)}
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        for event in memory.data["history"]:
            if not isinstance(event, dict):
                continue
            a, b, stars = event.get("animal_a"), event.get("animal_b"), event.get("stars")
            if not isinstance(a, str) or not isinstance(b, str) or not isinstance(stars, (int, float)):
                continue
            if a.casefold() not in known or b.casefold() not in known:
                continue
            key = json.dumps(sorted((memory.canonical_animal_name(a), memory.canonical_animal_name(b))), ensure_ascii=False, separators=(",", ":"))
            ranked[key] = {"best_stars": max(float(ranked.get(key, {}).get("best_stars", -1)), float(stars))}
        distribution: dict[float, int] = {}
        for entry in ranked.values():
            stars = entry["best_stars"]
            distribution[stars] = distribution.get(stars, 0) + 1
        filtered = [
            (key, entry) for key, entry in ranked.items()
            if (minimum_stars is None or entry["best_stars"] >= minimum_stars)
            and (maximum_stars is None or entry["best_stars"] <= maximum_stars)
        ]
        top_pairs = sorted(filtered, key=lambda item: (-item[1]["best_stars"], item[0]))[:limit]
        pairs = []
        for key, entry in top_pairs:
            animals = json.loads(key)
            pairs.append({
                "animal_a": animals[0],
                "animal_b": animals[1],
                "stars": entry["best_stars"],
            })
        return {
            "message": "Pair counts by best-star score",
            "distribution": [
                {"stars": stars, "pair_count": count}
                for stars, count in sorted(distribution.items(), reverse=True)
            ],
            "matched_pair_count": len(filtered),
            "pairs": pairs,
        }
    raise ValueError(f"Unknown action {action!r}; allowed: add, record, next, list, history, top, untried, summary")


def write_result(result: dict[str, Any]) -> None:
    payload = dict(result)
    temp = RESULT_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(RESULT_FILE)


def process_command() -> dict[str, Any]:
    if not COMMAND_FILE.exists():
        raise FileNotFoundError(f"Command file not found: {COMMAND_FILE}")
    command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
    memory = Memory(MEMORY_FILE)
    result = {"ok": True, **execute(command, memory)}
    write_result(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Impossible Animals command processor")
    parser.add_argument("--once", action="store_true", help="Process command.json once and exit")
    args = parser.parse_args()
    if args.once:
        try:
            result = process_command()
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
            write_result(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["ok"]:
            raise SystemExit(1)
        return

    print(f"Watching command file: {COMMAND_FILE}")
    print("Stop with Ctrl+C. Only documented JSON actions are accepted.")
    # Ignore a command that was already present before the watcher started.
    # The one-shot menu processor handles commands directly with --once.
    last_signature = None
    if COMMAND_FILE.exists():
        stat = COMMAND_FILE.stat()
        last_signature = (stat.st_mtime_ns, stat.st_size)
    while True:
        try:
            if COMMAND_FILE.exists():
                signature = (COMMAND_FILE.stat().st_mtime_ns, COMMAND_FILE.stat().st_size)
                if signature != last_signature:
                    try:
                        result = process_command()
                    except Exception as exc:
                        result = {"ok": False, "error": str(exc)}
                        write_result(result)
                    last_signature = signature
                    status = str(result.get("message", result.get("error", "done")))
                    encoding = sys.stdout.encoding or "utf-8"
                    status = status.encode(encoding, errors="replace").decode(encoding, errors="replace")
                    print("Command handled:", status)
            time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("Controller stopped.")
            return


if __name__ == "__main__":
    main()


