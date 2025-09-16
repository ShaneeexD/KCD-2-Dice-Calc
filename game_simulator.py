"""
KCD2 Dice Full Game Simulator (Player vs AI)

This module simulates full games to a point cap using the same per-turn logic
as the Single Combo Simulator. Badges are intentionally not modeled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Callable
import random
import time
from collections import defaultdict

from dice_data import Die, get_die_by_name
from turn_simulator import DiceSimulator

# Difficulty profiles (no badges). See AI_BEHAVIOR.md for details.
AI_PROFILES: Dict[str, Dict[str, int | bool]] = {
    # Accurate
    "priest": {
        "bank_min_value": 500,
        "bank_min_applies_first_n_rolls": 2,
        "bank_if_dice_below": 0,
        "no_bank_on_clear": True,
        "reset_count_on_refresh": True,
    }
}


@dataclass
class GameResult:
    player_score: int
    ai_score: int
    turns: int
    first_player: str  # "player" or "ai"
    winner: str        # "player" or "ai"
    game_log: Optional[List[Dict]] = None  # detailed per-turn log when collected


class GameSimulator:
    """Simulate full games to a point cap using DiceSimulator per-turn logic."""

    def __init__(
        self,
        player_dice: List[Die],
        ai_dice: List[Die],
        win_target: int = 8000,
        ai_profile: str = "priest",
        alternate_first: bool = True,
        player_settings: Optional[Dict[str, int | bool]] = None,
    ) -> None:
        self.player_dice = list(player_dice)
        self.ai_dice = list(ai_dice)
        self.win_target = int(win_target)
        self.ai_profile_name = ai_profile
        self.alternate_first = alternate_first
        self.player_settings: Optional[Dict[str, int | bool]] = player_settings

    def _configure_sim(self, sim: DiceSimulator, profile: Dict[str, int | bool]) -> None:
        sim.bank_min_value = int(profile.get("bank_min_value", 0)) if profile.get("bank_min_value") else None
        sim.bank_min_applies_first_n_rolls = (
            int(profile.get("bank_min_applies_first_n_rolls", 0)) if profile.get("bank_min_applies_first_n_rolls") else None
        )
        sim.no_bank_on_clear = bool(profile.get("no_bank_on_clear", False))
        sim.reset_count_on_refresh = bool(profile.get("reset_count_on_refresh", False))
        sim.bank_if_dice_below = int(profile.get("bank_if_dice_below", 0))
        sim.win_target = int(self.win_target)

    def _play_single_turn(self, dice: List[Die], profile: Dict[str, int | bool] | None, capture_log: bool = False):
        sim = DiceSimulator(dice, num_simulations=0)
        if profile is not None:
            self._configure_sim(sim, profile)
        else:
            # Player: apply provided Single Combo settings if available
            if self.player_settings:
                self._configure_sim(sim, self.player_settings)
            else:
                # Fallback baseline: only win target
                sim.win_target = int(self.win_target)
        score, did_bust, rolls, turn_log = sim._simulate_turn_with_optimal_choices(dice, debug=False)
        if capture_log:
            return {
                "score": 0 if did_bust else score,
                "did_bust": bool(did_bust),
                "rolls": int(rolls),
                "log": turn_log,
            }
        else:
            return 0 if did_bust else score

    def play_game(self, first: str = "player", collect_log: bool = False) -> GameResult:
        player_total = 0
        ai_total = 0
        turns = 0
        ai_profile = AI_PROFILES.get(self.ai_profile_name, AI_PROFILES["priest"])
        game_log: List[Dict] = [] if collect_log else None

        current = first
        while player_total < self.win_target and ai_total < self.win_target:
            turns += 1
            if current == "player":
                if collect_log:
                    res = self._play_single_turn(self.player_dice, profile=None, capture_log=True)
                    gained = int(res["score"])  # already 0 on bust
                    player_total += gained
                    if game_log is not None:
                        game_log.append({
                            "turn": turns,
                            "actor": "player",
                            "gained": gained,
                            "did_bust": res["did_bust"],
                            "rolls": res["rolls"],
                            "choices": res["log"],
                            "totals": {"player": player_total, "ai": ai_total},
                        })
                else:
                    gained = self._play_single_turn(self.player_dice, profile=None)
                    player_total += gained
                current = "ai"
            else:
                if collect_log:
                    res = self._play_single_turn(self.ai_dice, profile=ai_profile, capture_log=True)
                    gained = int(res["score"])  # already 0 on bust
                    ai_total += gained
                    if game_log is not None:
                        game_log.append({
                            "turn": turns,
                            "actor": "ai",
                            "gained": gained,
                            "did_bust": res["did_bust"],
                            "rolls": res["rolls"],
                            "choices": res["log"],
                            "totals": {"player": player_total, "ai": ai_total},
                        })
                else:
                    gained = self._play_single_turn(self.ai_dice, profile=ai_profile)
                    ai_total += gained
                current = "player"

        winner = "player" if player_total >= self.win_target else "ai"
        return GameResult(
            player_score=min(player_total, self.win_target),
            ai_score=min(ai_total, self.win_target),
            turns=turns,
            first_player=first,
            winner=winner,
            game_log=game_log,
        )

    def simulate_games(self, n_games: int = 1000, progress_fn: Optional[Callable[[int, int], None]] = None) -> Dict:
        start = time.time()
        n_games = max(1, int(n_games))

        player_wins = 0
        ai_wins = 0
        total_turns = 0
        margins = []
        game_lengths = defaultdict(int)
        example_win: Optional[GameResult] = None
        example_loss: Optional[GameResult] = None

        if progress_fn:
            try:
                progress_fn(0, n_games)
            except Exception:
                pass

        for i in range(n_games):
            if self.alternate_first:
                first = "player" if (i % 2 == 0) else "ai"
            else:
                first = random.choice(["player", "ai"])  # slight randomization

            need_example = (example_win is None) or (example_loss is None)
            result = self.play_game(first=first, collect_log=need_example)
            total_turns += result.turns
            game_lengths[result.turns] += 1

            margin = result.player_score - result.ai_score
            margins.append(margin)

            if result.winner == "player":
                player_wins += 1
                if example_win is None and result.game_log:
                    example_win = result
            else:
                ai_wins += 1
                if example_loss is None and result.game_log:
                    example_loss = result

            if progress_fn and (i % max(1, n_games // 50) == 0 or i == n_games - 1):
                try:
                    progress_fn(i + 1, n_games)
                except Exception:
                    pass

        elapsed = time.time() - start
        player_win_rate = player_wins / n_games
        ai_win_rate = ai_wins / n_games
        avg_turns = total_turns / n_games
        avg_margin = sum(margins) / n_games

        # Convert game_lengths to distribution (percentage)
        length_dist = {k: (v / n_games * 100.0) for k, v in sorted(game_lengths.items())}

        def _format_example(gr: Optional[GameResult]) -> Optional[str]:
            if not gr or not gr.game_log:
                return None
            lines = [
                f"First player: {gr.first_player}",
                f"Winner: {gr.winner}",
                f"Final Score - Player: {gr.player_score}, AI: {gr.ai_score}",
                f"Total turns: {gr.turns}",
                "",
            ]
            for entry in gr.game_log:
                actor = entry.get("actor")
                gained = entry.get("gained")
                did_bust = entry.get("did_bust")
                rolls = entry.get("rolls")
                totals = entry.get("totals", {})
                lines.append(f"Turn {entry.get('turn')}: {actor.upper()} gained {gained} ({'BUST' if did_bust else 'ok'}), rolls={rolls}, totals: P={totals.get('player')}, AI={totals.get('ai')}")
                choices = entry.get("choices", [])
                for c in choices:
                    lines.append(f"  - {c}")
            return "\n".join(lines)

        return {
            "games": n_games,
            "win_target": self.win_target,
            "ai_profile": self.ai_profile_name,
            "player_win_rate": player_win_rate,
            "ai_win_rate": ai_win_rate,
            "avg_turns": avg_turns,
            "avg_margin": avg_margin,
            "length_distribution": length_dist,
            "elapsed_sec": elapsed,
            "example_player_win": _format_example(example_win),
            "example_player_loss": _format_example(example_loss),
        }
