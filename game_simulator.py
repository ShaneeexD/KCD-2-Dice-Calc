"""
KCD2 Dice Full Game Simulator (Player vs AI)

This module simulates full games to a point cap using the same per-turn logic
as the Single Combo Simulator. Badges are intentionally not modeled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
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


class GameSimulator:
    """Simulate full games to a point cap using DiceSimulator per-turn logic."""

    def __init__(
        self,
        player_dice: List[Die],
        ai_dice: List[Die],
        win_target: int = 8000,
        ai_profile: str = "priest",
        alternate_first: bool = True,
    ) -> None:
        self.player_dice = list(player_dice)
        self.ai_dice = list(ai_dice)
        self.win_target = int(win_target)
        self.ai_profile_name = ai_profile
        self.alternate_first = alternate_first

    def _configure_sim(self, sim: DiceSimulator, profile: Dict[str, int | bool]) -> None:
        sim.bank_min_value = int(profile.get("bank_min_value", 0)) if profile.get("bank_min_value") else None
        sim.bank_min_applies_first_n_rolls = (
            int(profile.get("bank_min_applies_first_n_rolls", 0)) if profile.get("bank_min_applies_first_n_rolls") else None
        )
        sim.no_bank_on_clear = bool(profile.get("no_bank_on_clear", False))
        sim.reset_count_on_refresh = bool(profile.get("reset_count_on_refresh", False))
        sim.bank_if_dice_below = int(profile.get("bank_if_dice_below", 0))
        sim.win_target = int(self.win_target)

    def _play_single_turn(self, dice: List[Die], profile: Dict[str, int | bool] | None) -> int:
        sim = DiceSimulator(dice, num_simulations=0)
        if profile is not None:
            self._configure_sim(sim, profile)
        else:
            # Player defaults: use the same baseline as Single Combo (no extra constraints)
            sim.win_target = int(self.win_target)
        score, did_bust, _rolls, _log = sim._simulate_turn_with_optimal_choices(dice, debug=False)
        return 0 if did_bust else score

    def play_game(self, first: str = "player") -> GameResult:
        player_total = 0
        ai_total = 0
        turns = 0
        ai_profile = AI_PROFILES.get(self.ai_profile_name, AI_PROFILES["priest"])

        current = first
        while player_total < self.win_target and ai_total < self.win_target:
            turns += 1
            if current == "player":
                gained = self._play_single_turn(self.player_dice, profile=None)
                player_total += gained
                current = "ai"
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
        )

    def simulate_games(self, n_games: int = 1000) -> Dict:
        start = time.time()
        n_games = max(1, int(n_games))

        player_wins = 0
        ai_wins = 0
        total_turns = 0
        margins = []
        game_lengths = defaultdict(int)

        for i in range(n_games):
            if self.alternate_first:
                first = "player" if (i % 2 == 0) else "ai"
            else:
                first = random.choice(["player", "ai"])  # slight randomization

            result = self.play_game(first=first)
            total_turns += result.turns
            game_lengths[result.turns] += 1

            margin = result.player_score - result.ai_score
            margins.append(margin)

            if result.winner == "player":
                player_wins += 1
            else:
                ai_wins += 1

        elapsed = time.time() - start
        player_win_rate = player_wins / n_games
        ai_win_rate = ai_wins / n_games
        avg_turns = total_turns / n_games
        avg_margin = sum(margins) / n_games

        # Convert game_lengths to distribution (percentage)
        length_dist = {k: (v / n_games * 100.0) for k, v in sorted(game_lengths.items())}

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
        }
