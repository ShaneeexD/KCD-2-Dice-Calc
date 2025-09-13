"""
Kingdom Come: Deliverance 2 Dice Game Simulator
Implements a direct simulator for evaluating dice combinations based on the game rules.
"""

import random
import itertools
import logging
import time
import os
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set, Optional, Callable

from dice_data import Die, get_die_by_name
# Optional high-performance dependencies
try:
    import numpy as np  # For fast sampling and arrays
except Exception:
    np = None

try:
    from scoring_system import score_dice_roll, _score_dice_roll_jit  # JIT-compiled scoring (if available)
except Exception:
    from scoring_system import score_dice_roll  # Fallback to Python scoring only
    _score_dice_roll_jit = None

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    handlers=[
                        logging.FileHandler("kcd2_dice_simulation.log"),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger('dice_simulator')

# Concurrency for cross-combination evaluation
from concurrent.futures import ProcessPoolExecutor, as_completed

def _eval_combo_worker(payload):
    """Process-safe worker to evaluate a single dice combination.
    Payload keys: name, dice_names, sims
    """
    try:
        name = payload["name"]
        dice_names = payload["dice_names"]
        sims = payload["sims"]
        # Reconstruct dice objects in the worker
        dice_objs = [get_die_by_name(n) for n in dice_names]
        # Reduce logging noise in worker
        logging.getLogger('dice_simulator').setLevel(logging.WARNING)
        sim = DiceSimulator([], sims)
        # Keep per-combo sims modest in workers to improve throughput
        sims = max(50, min(200, sims))
        res = sim.simulate_dice_combination(dice_objs, sims, None, diagnostics=False)
        res["name"] = name
        res["dice_combination"] = Counter(n for n in dice_names)
        ev = res.get("expected_value", 0.0)
        bust = res.get("bust_rate", 0.0)
        avg_rolls = max(1e-9, res.get("avg_rolls", 1.0))
        rate = ev / avg_rolls
        reliability = (1.0 - bust) * ev
        res["rank_score"] = 0.6 * ev + 0.3 * rate + 0.1 * reliability
        return res
    except Exception as e:
        return {"error": str(e), "name": payload.get("name", "Unknown")}

class DiceSimulator:
    """Simulates dice rolls in the KCD2 dice game."""
    
    def __init__(self, dice: List[Die], num_simulations: int = 10000):
        """Initialize the simulator with a dice set and simulation count."""
        self.dice = dice
        self.num_simulations = num_simulations

    def _format_combo_name(self, dice_list: List[Die]) -> str:
        """Return a normalized 'raw' composition string like '3x Weighted die, 2x Lucky Die, 1x Odd die'."""
        counts = Counter(d.name for d in dice_list)
        parts = [f"{count}x {name}" for name, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
        return ", ".join(parts)
    
    def _roll_dice(self, dice: List[Die]) -> List[int]:
        """
        Simulate rolling a set of dice based on their probabilities.
        Uses NumPy for sampling when available, otherwise falls back to random.choices.
        """
        result = []
        if np is not None:
            # Fast per-die sampling using NumPy
            sides = np.arange(1, 7, dtype=np.int64)
            for die in dice:
                w = np.array(die.weights, dtype=np.float64)
                p = w / w.sum()
                val = int(np.random.choice(sides, p=p))
                result.append(val)
            return result
        # Fallback: pure Python sampling
        for die in dice:
            sides = [1, 2, 3, 4, 5, 6]
            result.append(random.choices(sides, weights=die.weights)[0])
        return result
    
    def _identify_all_keep_options(self, roll: List[int]) -> List[Tuple[Set[int], int, str]]:
        """
        Identify ALL valid options for which dice to keep from a roll.
        This includes every valid combination of dice that scores points.
        
        Args:
            roll: List of dice values from a roll
            
        Returns:
            List of tuples (indices_to_keep, score, description)
        """
        options = []
        n = len(roll)
        
        def _is_pure_scoring_set(values: List[int]) -> bool:
            """Return True if every die in values contributes to the score.
            Prefer fast JIT scoring when available, else fall back to Python scorer.
            """
            if _score_dice_roll_jit is not None and np is not None:
                arr = np.array(values, dtype=np.int64)
                full_score = int(_score_dice_roll_jit(arr))
                if full_score <= 0:
                    return False
                n = arr.size
                for j in range(n):
                    if n == 1:
                        break
                    tmp = np.delete(arr, j)
                    tmp_score = int(_score_dice_roll_jit(tmp))
                    if tmp_score >= full_score:
                        return False
                return True
            # Fallback to descriptive Python scorer
            full_score, _, _ = score_dice_roll(values)
            if full_score <= 0:
                return False
            for j in range(len(values)):
                tmp = values[:j] + values[j+1:]
                tmp_score, _, _ = score_dice_roll(tmp)
                if tmp_score >= full_score:
                    return False
            return True

        # Generate all possible subsets of indices (excluding empty set)
        for keep_size in range(1, n + 1):
            for indices in itertools.combinations(range(n), keep_size):
                indices_set = set(indices)
                keep_values = [roll[i] for i in indices]
                # Fast raw scoring when JIT is available; otherwise use Python scorer
                if _score_dice_roll_jit is not None and np is not None:
                    score = int(_score_dice_roll_jit(np.array(keep_values, dtype=np.int64)))
                else:
                    score, _, _ = score_dice_roll(keep_values)
                # Only add if it's a valid scoring option
                if score > 0 and _is_pure_scoring_set(keep_values):
                    # Compute human-friendly description using Python scorer
                    _, _, desc = score_dice_roll(keep_values)
                    options.append((indices_set, score, desc))
        
        # Sort by score (descending)
        options.sort(key=lambda x: x[1], reverse=True)
        return options
        
    def _find_optimal_choices(self, roll: List[int], dice_left: int, current_total: int) -> List[Tuple[Set[int], int, float, str]]:
        """
        Find all valid keep options with their expected value for the next roll.
        
        Args:
            roll: The current roll values
            dice_left: Number of dice in total remaining (including this roll)
            current_total: Current accumulated score this turn (used for bank option)
            
        Returns:
            List of (indices_to_keep, immediate_score, expected_value, description) tuples
            where expected_value estimates the value of this choice considering future rolls
        """
        # First, get all valid scoring combinations
        all_options = self._identify_all_keep_options(roll)
        
        if not all_options:
            # No scoring options - bust!
            return []
            
        enhanced_options = []
        for indices, score, desc in all_options:
            # Calculate how many dice we'd have left after keeping these
            kept_dice = len(indices)
            remaining_dice = len(roll) - kept_dice
            
            # Base expected value is the immediate score
            expected_value = score
            
            # If we'd have dice left, we could roll again - estimate that value
            if remaining_dice > 0:
                # Very simple estimate: each remaining die is worth about 25 points on average
                # (this is a heuristic based on common dice game patterns)
                future_value = remaining_dice * 25
                # But there's bust risk - let's estimate based on remaining dice
                bust_risk = max(0.1, 0.1 * remaining_dice)  # More dice = higher bust risk
                expected_value += future_value * (1 - bust_risk)
                
            # If keeping these dice would clear all dice, we can roll all dice again!
            elif remaining_dice == 0 and dice_left > len(roll):
                # Big bonus for clearing all dice (get to reroll all dice)
                expected_value += 150  # Bonus for getting all dice back
            
            enhanced_options.append((indices, score, expected_value, desc))
            
        # Always include a 'Bank now' option that represents stopping this turn
        # Use an empty indices set to indicate banking
        enhanced_options.append((set(), 0, float(current_total), "Bank now"))

        # Sort by expected value
        enhanced_options.sort(key=lambda x: x[2], reverse=True)
        return enhanced_options
    
    def _evaluate_strategy(self, strategy_name: str, strategy_fn, initial_dice: List[Die]) -> Dict:
        """
        Evaluate a given strategy over multiple simulations.
        
        Args:
            strategy_name: Name of the strategy
            strategy_fn: Function that decides which dice to keep
            initial_dice: List of Die objects to start with
            
        Returns:
            Dict with statistics about the strategy performance
        """
        logger.info(f"Evaluating strategy: {strategy_name} with {len(initial_dice)} dice")
        strategy_start_time = time.time()
        
        total_score = 0
        bust_count = 0
        score_distribution = defaultdict(int)
        turn_lengths = []
        high_score = 0
        
        # Log progress at these intervals
        progress_intervals = [int(self.num_simulations * p) for p in [0.1, 0.25, 0.5, 0.75, 0.9]]
        
        for i in range(self.num_simulations):
            # Log progress at intervals
            if i in progress_intervals or i % 1000 == 0:
                progress_pct = (i / self.num_simulations) * 100
                logger.info(f"{strategy_name} strategy: {progress_pct:.1f}% complete ({i}/{self.num_simulations} simulations)")
            
            score, did_bust, num_rolls = self._simulate_turn(strategy_fn, initial_dice)
            
            total_score += score
            if did_bust:
                bust_count += 1
            
            # Track high score
            if score > high_score:
                high_score = score
                logger.info(f"New high score with {strategy_name}: {high_score} points")
            
            score_distribution[score] += 1
            turn_lengths.append(num_rolls)
        
        # Calculate statistics
        avg_score = total_score / self.num_simulations
        bust_rate = bust_count / self.num_simulations
        avg_turns = sum(turn_lengths) / self.num_simulations
        
        # Find most common scores
        common_scores = sorted(
            [(score, count / self.num_simulations * 100) 
             for score, count in score_distribution.items()],
            key=lambda x: x[1], reverse=True
        )[:5]
        
        return {
            "name": strategy_name,
            "avg_score": avg_score,
            "bust_rate": bust_rate,
            "avg_rolls": avg_turns,
            "common_scores": common_scores,
            "expected_value": avg_score * (1 - bust_rate)  # Adjusted for bust risk
        }
    
    def _simulate_turn_with_optimal_choices(self, dice: List[Die], debug: bool = False) -> Tuple[int, bool, int, List[str]]:
        """
        Simulate a single turn using optimal choices at each step.
        
        Args:
            dice: List of Die objects to start with
            debug: Whether to output detailed debug information
            
        Returns:
            Tuple of (final_score, did_bust, number_of_rolls, choice_descriptions)
        """
        current_dice = list(dice)
        total_score = 0
        roll_count = 0
        choice_descriptions = []  # Track choices made for logging
        total_dice = len(dice)  # Keep track of total dice available
        
        # Max turns to avoid infinite loops
        max_turns = 50
        
        while current_dice and roll_count < max_turns:
            roll_count += 1
            
            # Roll the current dice
            current_roll = self._roll_dice(current_dice)
            roll_str = ", ".join(str(v) for v in current_roll)
            
            if debug:
                dice_names = [die.name for die in current_dice]
                logger.info(f"DEBUG: Roll {roll_count} with {len(current_dice)} dice: {roll_str}")
                logger.info(f"DEBUG: Dice used: {Counter(dice_names)}")
            
            # Get all options with their expected values (including 'Bank now')
            options = self._find_optimal_choices(current_roll, total_dice, total_score)
            
            if debug and not options:
                # More detailed diagnostic when debug is on
                logger.error(f"DEBUG: No scoring options found for roll: {current_roll}")
                # Try debugging the scoring directly
                all_keep_options = self._identify_all_keep_options(current_roll)
                logger.error(f"DEBUG: _identify_all_keep_options found {len(all_keep_options)} options")
                
                # Test individual dice values that should definitely score
                for i, val in enumerate(current_roll):
                    if val == 1 or val == 5:
                        logger.error(f"DEBUG: Die {i} has value {val} which should score, checking...")
                        keep_values = [val]
                        score, combo_parts, desc = score_dice_roll(keep_values)
                        logger.error(f"DEBUG: Direct score_dice_roll({keep_values}) = {score}, {desc}")
            
            # If no valid options, bust!
            if not options:
                choice_descriptions.append(f"Roll {roll_count}: {roll_str} - BUST!")
                return 0, True, roll_count, choice_descriptions
            
            if debug:
                logger.info(f"DEBUG: Found {len(options)} scoring options")
                for i, opt in enumerate(options[:3]):  # Show top 3
                    kept_indices, score, ev, desc = opt
                    kept = [current_roll[i] for i in kept_indices]
                    logger.info(f"DEBUG: Option {i+1}: Keep {kept} for {score} points, EV: {ev:.1f} ({desc})")
            
            # Choose the option with the highest expected value
            best_option = options[0]  # Already sorted by expected value
            kept_indices, keep_score, _, description = best_option

            # If the best option is to bank now, end the turn
            if len(kept_indices) == 0 and description == "Bank now":
                choice_descriptions.append(f"Roll {roll_count}: {roll_str} - Decision: BANK NOW at {total_score} points")
                return total_score, False, roll_count, choice_descriptions
            
            # Log the choice
            kept_values = [current_roll[i] for i in kept_indices]
            kept_str = ", ".join(str(v) for v in kept_values)
            choice_descriptions.append(f"Roll {roll_count}: {roll_str} - Kept {kept_str} for {keep_score} points ({description})")
            
            # Add score from kept dice
            total_score += keep_score
            # Cap at the game win threshold (8000). If reached, stop rolling.
            if total_score >= 8000:
                total_score = 8000
                choice_descriptions.append(f"Reached 8000 points, ending turn.")
                break
            
            # Remove kept dice from the pool
            remaining_indices = [i for i in range(len(current_roll)) if i not in kept_indices]
            current_dice = [current_dice[i] for i in remaining_indices]
            
            if debug:
                logger.info(f"DEBUG: After keeping {kept_values}, {len(remaining_indices)} dice remain")
                logger.info(f"DEBUG: Current total score: {total_score}")
            
            # If we've used all dice, start again with a fresh set
            if not current_dice:
                choice_descriptions.append(f"Used all dice! Refreshing with full set. Current score: {total_score}")
                current_dice = list(dice)
                
                if debug:
                    logger.info(f"DEBUG: Used all dice - refreshing with full set. Current score: {total_score}")
        
        # If we hit max turns, report it
        if roll_count >= max_turns:
            logger.warning(f"Hit maximum turn limit ({max_turns}) - ending simulation")
            choice_descriptions.append(f"Hit maximum turn limit ({max_turns}) - ending simulation")
            
        # If we get here, we've completed all rolls successfully
        return total_score, False, roll_count, choice_descriptions
    
    def _test_scoring(self):
        """Test function to verify scoring works properly."""
        # Create some test rolls that should definitely score
        test_rolls = [
            [1, 1, 1, 2, 3, 4],  # Three 1s
            [2, 2, 2, 3, 4, 5],  # Three 2s
            [1, 2, 3, 4, 5, 6],  # Full straight
            [5, 5, 5, 5, 6, 6],  # Four 5s
            [1, 5, 2, 3, 4, 6],  # Single 1 and Single 5
        ]
        
        # Test each roll and log results
        logger.info("Testing scoring system with predefined rolls:")
        for roll in test_rolls:
            options = self._identify_all_keep_options(roll)
            logger.info(f"Roll: {roll} - Options: {len(options)} found")
            if options:
                for idx, (indices, score, desc) in enumerate(options[:3]):  # Show top 3 options
                    kept = [roll[i] for i in indices]
                    logger.info(f"  Option {idx+1}: Keep {kept} for {score} points ({desc})")
            else:
                logger.error(f"  ERROR: No scoring options found for {roll}!")
    
    def simulate_dice_combination(self, dice: List[Die], num_simulations: int = 1000, progress_fn: Optional[Callable[[int, int], None]] = None, diagnostics: bool = True) -> Dict:
        """
        Simulate multiple turns with a given dice combination using optimal choices.
        
        Args:
            dice: List of Die objects to simulate
            num_simulations: Number of simulations to run
            
        Returns:
            Dictionary with statistics about the dice combination performance
        """
        # Optional diagnostic: only when explicitly enabled (avoid in workers)
        # Prepare dice counts for return value
        dice_names = [die.name for die in dice]
        dice_counts = Counter(dice_names)
        if diagnostics:
            self._test_scoring()
            logger.info(f"Simulating {num_simulations} turns with {len(dice)} dice")
            logger.info(f"Dice set: {dict(dice_counts)}")
        
        start_time = time.time()
        
        # Run simulations
        total_score = 0
        bust_count = 0
        turn_lengths = []
        score_distribution = defaultdict(int)
        max_score = 0
        detailed_logs = []
        
        # Log progress at these intervals
        progress_intervals = [int(num_simulations * p) for p in [0.25, 0.5, 0.75]]
        
        for i in range(num_simulations):
            # Light progress logging
            if diagnostics and (i in progress_intervals or (i % 500 == 0)):
                progress_pct = (i / num_simulations) * 100
                elapsed = time.time() - start_time
                logger.info(f"Simulation {i}/{num_simulations} ({progress_pct:.1f}%). Elapsed: {elapsed:.1f}s")
            # UI progress callback (throttle to ~50 updates)
            if progress_fn and (i % max(1, num_simulations // 50) == 0 or i == num_simulations - 1):
                try:
                    progress_fn(i + 1, num_simulations)
                except Exception:
                    pass
            
            # Run a single turn simulation with diagnostic info for early turns
            debug = diagnostics and (i < 1)  # Minimal debug when diagnostics enabled
            score, did_bust, num_rolls, choices = self._simulate_turn_with_optimal_choices(dice, debug)
            
            # Update statistics
            total_score += score
            if did_bust:
                bust_count += 1
            turn_lengths.append(num_rolls)
            score_distribution[score] += 1
            
            if score > max_score:
                max_score = score
                logger.info(f"New max score: {max_score}")
                detailed_logs.append(f"Turn with score {score}:\n" + "\n".join(choices))
        
        # Calculate statistics
        avg_score = total_score / max(1, num_simulations)  # Avoid division by zero
        bust_rate = bust_count / max(1, num_simulations)   # Avoid division by zero
        avg_rolls = sum(turn_lengths) / max(1, len(turn_lengths))  # Avoid division by zero
        expected_value = avg_score * (1 - bust_rate)
        
        # Find most common scores
        common_scores = sorted(
            [(score, count / num_simulations * 100) 
             for score, count in score_distribution.items()],
            key=lambda x: x[1], reverse=True
        )[:5]
        
        elapsed_time = time.time() - start_time
        logger.info(f"Simulation completed in {elapsed_time:.2f}s")
        logger.info(f"Average score: {avg_score:.2f}, Bust rate: {bust_rate:.2%}, Expected value: {expected_value:.2f}")
        
        # Log detailed information for the top 3 scores
        for log in detailed_logs[:3]:
            logger.info(log)
        
        return {
            "avg_score": avg_score,
            "bust_rate": bust_rate,
            "avg_rolls": avg_rolls,
            "expected_value": expected_value,
            "common_scores": common_scores,
            "max_score": max_score,
            "dice_combination": dict(dice_counts)
        }
    
    def evaluate_strategies(self) -> List[Dict]:
        """
        Evaluate multiple strategies for playing the dice game.
        
        Returns:
            List of dictionaries with statistics for each strategy
        """
        strategies = [
            # Conservative: Keep all scoring dice
            ("Conservative", lambda roll, options: max(options, key=lambda x: x[1]) if options else (set(), 0, "")),
            
            # Balanced: Keep dice if they score at least 100 points
            ("Balanced", self._balanced_strategy),
            
            # Risky: Try to keep minimum scoring dice to maximize future potential
            ("Risky", self._risky_strategy),
            
            # Straight Hunter: Prioritize collecting dice for straights
            ("Straight Hunter", self._straight_hunter_strategy),
            
            # Three-of-a-Kind Hunter: Prioritize collecting dice for three-of-a-kind
            ("Three-of-a-Kind Hunter", self._three_of_a_kind_hunter_strategy),
        ]
        
        results = []
        for name, strategy_fn in strategies:
            result = self._evaluate_strategy(name, strategy_fn, self.dice)
            results.append(result)
        
        # Sort by expected value
        results.sort(key=lambda x: x["expected_value"], reverse=True)
        return results
    
    def _balanced_strategy(self, roll: List[int], options: List[Tuple[Set[int], int, str]]) -> Tuple[Set[int], int, str]:
        """Balanced strategy: keep dice if they score at least 100 points."""
        if not options:
            return set(), 0, ""
            
        # Consider future potential based on remaining dice
        best_option = None
        best_value = -1
        
        for option in options:
            indices, score, desc = option
            
            # If score is very good, just take it
            if score >= 300:
                return indices, score, desc
                
            # Calculate how many dice we're keeping
            num_kept = len(indices)
            num_remaining = len(roll) - num_kept
            
            # Calculate the "value" of this option based on score and remaining potential
            value = score + (num_remaining * 50)  # Each remaining die has potential value
            
            if value > best_value:
                best_value = value
                best_option = option
        
        return best_option
    
    def _risky_strategy(self, roll: List[int], options: List[Tuple[Set[int], int, str]]) -> Tuple[Set[int], int, str]:
        """Risky strategy: try to keep minimum scoring dice to maximize future potential."""
        if not options:
            return set(), 0, ""
            
        # Get all options that score at least 50 points
        viable_options = [opt for opt in options if opt[1] >= 50]
        if not viable_options:
            return options[0]  # Fallback to best option
            
        # Choose the option that keeps the fewest dice while still scoring
        return min(viable_options, key=lambda x: len(x[0]))
    
    def _straight_hunter_strategy(self, roll: List[int], options: List[Tuple[Set[int], int, str]]) -> Tuple[Set[int], int, str]:
        """Straight Hunter strategy: prioritize collecting dice for straights."""
        if not options:
            return set(), 0, ""
            
        # Check if any option has a straight or partial straight
        for indices, score, desc in options:
            if "straight" in desc.lower():
                return indices, score, desc
                
        # If we have 1,2,3,4 or 2,3,4,5 or 3,4,5,6 in our roll, keep those
        roll_set = set(roll)
        for straight_set in [{1,2,3,4}, {2,3,4,5}, {3,4,5,6}]:
            if straight_set.issubset(roll_set):
                indices = {i for i, val in enumerate(roll) if val in straight_set}
                kept_values = [roll[i] for i in indices]
                score, _, desc = score_dice_roll(kept_values)
                if score > 0:
                    return indices, score, desc
        
        # Fall back to balanced strategy if no straight potential
        return self._balanced_strategy(roll, options)
    
    def _three_of_a_kind_hunter_strategy(self, roll: List[int], options: List[Tuple[Set[int], int, str]]) -> Tuple[Set[int], int, str]:
        """Three-of-a-Kind Hunter strategy: prioritize collecting dice for three-of-a-kind."""
        if not options:
            return set(), 0, ""
            
        # Check if any option has three or more of a kind
        for indices, score, desc in options:
            if any(keyword in desc.lower() for keyword in ["three", "four", "five", "six"]):
                return indices, score, desc
                
        # Count occurrences of each value in the roll
        counter = Counter(roll)
        
        # If we have two of any value, keep those (potential for three of a kind)
        for val, count in counter.items():
            if count == 2:
                indices = {i for i, v in enumerate(roll) if v == val}
                # Only keep the pair if it's 1 or 5 (otherwise we'd bust)
                if val in [1, 5]:
                    kept_values = [roll[i] for i in indices]
                    score, _, desc = score_dice_roll(kept_values)
                    if score > 0:
                        return indices, score, desc
        
        # Fall back to balanced strategy if no three-of-a-kind potential
        return self._balanced_strategy(roll, options)
    
    def simulate_best_dice_selection(self, all_dice: List[Die], num_to_select: int = 6) -> List[Dict]:
        """
        Simulate different dice selections to find the optimal set using a smart sampling approach.
        
        Args:
            all_dice: List of all available Die objects
            num_to_select: Number of dice to select for the optimal set
            
        Returns:
            List of dictionaries with statistics for each dice selection
        """
        logger.info(f"Starting dice selection simulation with {len(all_dice)} available dice")
        logger.info(f"Looking for the optimal set of {num_to_select} dice")
        selection_start_time = time.time()
        
        # If we have fewer dice than requested, just use what we have
        if len(all_dice) <= num_to_select:
            logger.info(f"Only {len(all_dice)} dice available, using all of them")
            results = self.evaluate_strategies()
            return [{"dice": all_dice, "stats": results}]
        
        results = []
        
        # Group dice by name to identify unique dice types
        dice_by_name = {}
        for die in all_dice:
            if die.name not in dice_by_name:
                dice_by_name[die.name] = []
            dice_by_name[die.name].append(die)
        
        # Track the most common dice types in inventory
        dice_counts = {name: len(dice_list) for name, dice_list in dice_by_name.items()}
        top_dice_types = sorted(dice_counts.items(), key=lambda x: x[1], reverse=True)[:10]  # Top 10 most numerous
        
        # 1. Test homogeneous sets (all same dice)
        logger.info(f"Testing {len(dice_by_name)} different homogeneous dice sets")
        for idx, (die_name, dice_list) in enumerate(dice_by_name.items(), 1):
            if len(dice_list) >= num_to_select:
                logger.info(f"Testing homogeneous set {idx}: {num_to_select}x {die_name}")
                identical_dice = dice_list[:num_to_select]
                self.dice = identical_dice
                stats = self.evaluate_strategies()
                
                expected_value = stats[0]["expected_value"]
                logger.info(f"Set result: {expected_value:.2f} expected value with {stats[0]['name']} strategy")
                
                results.append({"dice": identical_dice, "stats": stats, 
                               "name": f"{num_to_select}x {die_name}",
                               "expected_value": expected_value})
        
        # 2. Test well-known good dice types
        good_dice_types = ["Weighted die", "Lucky Die", "Heavenly Kingdom die", "Odd die", 
                         "Favourable die", "Even die", "Devil's head die", "King's die", 
                         "St. Stephen's die", "Three die"]
        
        available_good_dice = []
        for die_type in good_dice_types:
            if die_type in dice_by_name:
                available_good_dice.extend(dice_by_name[die_type][:min(6, len(dice_by_name[die_type]))])
        
        if len(available_good_dice) >= num_to_select:
            logger.info(f"Testing curated good dice combination")
            self.dice = available_good_dice[:num_to_select]
            stats = self.evaluate_strategies()
            expected_value = stats[0]["expected_value"]
            logger.info(f"Good dice set result: {expected_value:.2f} expected value with {stats[0]['name']} strategy")
            
            results.append({"dice": self.dice, "stats": stats, 
                           "name": "Selected Good Dice",
                           "expected_value": expected_value})
        
        # 3. Test dice with best weights for ones and fives
        logger.info("Testing dice weighted for ones and fives")
        sorted_by_ones = sorted(all_dice, key=lambda d: d.probability_of(1), reverse=True)
        sorted_by_fives = sorted(all_dice, key=lambda d: d.probability_of(5), reverse=True)
        
        # Mix of best dice for ones and fives
        mixed_dice = sorted_by_ones[:num_to_select//2] + sorted_by_fives[:num_to_select//2]
        if len(mixed_dice) >= num_to_select:
            self.dice = mixed_dice[:num_to_select]
            stats = self.evaluate_strategies()
            expected_value = stats[0]["expected_value"]
            logger.info(f"Mixed 1s and 5s dice result: {expected_value:.2f} expected value")
            
            results.append({"dice": self.dice, "stats": stats, 
                           "name": "Best 1s and 5s Mix",
                           "expected_value": expected_value})
        
        # 4. Test dice focused on straights
        straight_dice = []
        # Find dice good at rolling consecutive numbers
        for die in all_dice:
            # Calculate how balanced the die is across all values
            balance_score = sum(abs(die.probability_of(i) - 100/6) for i in range(1, 7))
            if balance_score < 50:  # This die has relatively balanced probabilities
                straight_dice.append(die)
        
        if len(straight_dice) >= num_to_select:
            logger.info("Testing dice weighted for straights")
            self.dice = straight_dice[:num_to_select]
            stats = self.evaluate_strategies()
            expected_value = stats[0]["expected_value"]
            logger.info(f"Straight-focused dice result: {expected_value:.2f} expected value")
            
            results.append({"dice": self.dice, "stats": stats, 
                           "name": "Straight-focused Dice",
                           "expected_value": expected_value})
            
        # 5. Test random sampling of mixed combinations if we have many dice types
        if len(all_dice) > 10 and len(dice_by_name) > 3:
            logger.info("Testing random mixed combinations")
            num_samples = min(5, len(all_dice) // 2)  # At most 5 random samples to save time
            
            for i in range(num_samples):
                sampled_dice = random.sample(all_dice, min(len(all_dice), num_to_select))
                self.dice = sampled_dice[:num_to_select]
                stats = self.evaluate_strategies()
                expected_value = stats[0]["expected_value"]
                
                dice_composition = Counter([die.name for die in self.dice])
                composition_str = ", ".join(f"{count}x {name}" for name, count in dice_composition.items())
                
                logger.info(f"Random mix {i+1} result: {expected_value:.2f} expected value")
                
                results.append({"dice": self.dice, "stats": stats, 
                               "name": f"Random Mix {i+1}: {composition_str}",
                               "expected_value": expected_value})
        
        elapsed_time = time.time() - selection_start_time
        logger.info(f"Dice selection simulation completed in {elapsed_time:.2f} seconds")
        
def find_optimal_dice_combination(available_dice: List[Die], num_dice: int = 6, 
                             num_simulations: int = 1000,
                             progress_callback: Optional[Callable[[int], None]] = None,
                             exhaustive: bool = False,
                             status_callback: Optional[Callable[[int, int, float], None]] = None,
                             max_combos: int = 5000) -> Dict:
    """
    Find the optimal dice combination for maximizing expected score.
    Uses direct simulation of dice rolls with optimal player choices at each step.
    """
    logger.info(f"Starting optimal dice combination search with {len(available_dice)} available dice")
    logger.info(f"Will test combinations of {num_dice} dice using {num_simulations} simulations each")
    start_time = time.time()
    
    # Initialize simulator (we'll reuse this for all combinations)
    simulator = DiceSimulator([], num_simulations)
    
    # Update progress
    if progress_callback:
        progress_callback(5)  # Starting progress
    
    # If we have fewer dice than requested, just use what we have
    if len(available_dice) <= num_dice:
        logger.info(f"Only {len(available_dice)} dice available, using all of them")
        dice_to_use = available_dice
        results = [simulator.simulate_dice_combination(dice_to_use, num_simulations)]
        
        # Update progress
        if progress_callback:
            progress_callback(100)
            
        dice_names = [die.name for die in dice_to_use]
        return {
            "dice_combination": "All Available Dice",
            "dice_composition": Counter(dice_names),
            "dice_objects": dice_to_use,
            "expected_score": results[0]["expected_value"],
            "bust_rate": results[0]["bust_rate"],
            "avg_rolls": results[0]["avg_rolls"],
            "common_scores": results[0]["common_scores"],
            "max_score": results[0]["max_score"],
        }
    
    # Group dice by name for more efficient testing
    dice_by_name = {}
    for die in available_dice:
        if die.name not in dice_by_name:
            dice_by_name[die.name] = []
        dice_by_name[die.name].append(die)
    
    # Track combinations to test with their descriptions
    combinations_to_test = []
    
    # Decide whether to use exhaustive testing or smart sampling
    if exhaustive:
        # EXHAUSTIVE TESTING: Generate all possible combinations
        logger.info("Using EXHAUSTIVE combination testing mode")
        
        # Get all unique dice types available
        unique_dice_types = list(dice_by_name.keys())
        num_types = len(unique_dice_types)
        logger.info(f"Found {num_types} unique dice types")
        
        # Calculate total number of combinations
        import math
        from itertools import combinations_with_replacement
        
        total_combos = math.comb(num_types + num_dice - 1, num_dice)
        logger.info(f"Total possible combinations: {total_combos:,}")
        
        # Adjust simulations based on combination count
        adjusted_sims = max(10, min(num_simulations, 10000 // max(1, total_combos // 100)))
        logger.info(f"Adjusted simulations per combo: {adjusted_sims} (from {num_simulations})")
        num_simulations = adjusted_sims
        
        progress = 10
        if progress_callback:
            progress_callback(progress)
            
        # Generate all combinations with replacement
        # Each combo is a multiset of dice types
        for i, combo_types in enumerate(combinations_with_replacement(unique_dice_types, num_dice)):
            # Log progress periodically
            if i % 100 == 0 or i < 10:
                logger.info(f"Generating combination {i+1:,}/{total_combos:,}")
                if i > 0 and i % 1000 == 0:
                    # Report progress
                    prog = 10 + (20 * i / total_combos)
                    if progress_callback:
                        progress_callback(min(30, int(prog)))
                    if status_callback:
                        status_callback(i+1, total_combos, time.time() - start_time)
            
            # Count occurrences of each die type
            type_counts = Counter(combo_types)
            
            # Check if we have enough of each type
            valid = True
            dice_selection = []
            combo_name_parts = []
            
            for die_type, count in type_counts.items():
                available = len(dice_by_name[die_type])
                if available < count:
                    valid = False
                    break
                dice_selection.extend(dice_by_name[die_type][:count])
                if count > 0:
                    combo_name_parts.append(f"{count}x {die_type}")
            
            if valid:
                combo_name = ", ".join(combo_name_parts)
                combinations_to_test.append({
                    "dice": dice_selection,
                    "name": combo_name
                })
        
        # Cap the number of combinations to keep runtime bounded (only if max_combos > 0)
        if max_combos and max_combos > 0 and len(combinations_to_test) > max_combos:
            logger.info(f"Capping combinations from {len(combinations_to_test):,} to {max_combos:,} for performance")
            # Uniformly sample without replacement
            import random as _r
            combinations_to_test = _r.sample(combinations_to_test, max_combos)
        logger.info(f"Generated {len(combinations_to_test)} valid combinations to test")
    else:
        # SMART SAMPLING: Test specific promising combinations
        logger.info("Using SMART SAMPLING mode for dice combinations")
        
        # 1. Test homogeneous sets (all same dice)
        progress = 10
        if progress_callback:
            progress_callback(progress)
            
        logger.info(f"Preparing {len(dice_by_name)} homogeneous dice combinations")
        for die_name, dice_list in dice_by_name.items():
            if len(dice_list) >= num_dice:
                dice_sel = dice_list[:num_dice]
                combinations_to_test.append({
                    "dice": dice_sel,
                    "name": self._format_combo_name(dice_sel)
                })
        
        # 2. Test well-known good dice types
        progress = 15
        if progress_callback:
            progress_callback(progress)
            
        good_dice_types = ["Weighted die", "Lucky Die", "Heavenly Kingdom die", "Odd die", 
                         "Favourable die", "Even die", "Devil's head die", "King's die", 
                         "St. Stephen's die", "Three die"]
        
        available_good_dice = []
        for die_type in good_dice_types:
            if die_type in dice_by_name:
                available_good_dice.extend(dice_by_name[die_type][:min(6, len(dice_by_name[die_type]))])
        
        if len(available_good_dice) >= num_dice:
            dice_sel = available_good_dice[:num_dice]
            combinations_to_test.append({
                "dice": dice_sel,
                "name": self._format_combo_name(dice_sel)
            })
        
        # 3. Test dice with best weights for ones and fives
        progress = 20
        if progress_callback:
            progress_callback(progress)
            
        sorted_by_ones = sorted(available_dice, key=lambda d: d.probability_of(1), reverse=True)
        sorted_by_fives = sorted(available_dice, key=lambda d: d.probability_of(5), reverse=True)
        
        # Mix of best dice for ones and fives
        half = num_dice // 2
        mixed_dice = sorted_by_ones[:half] + sorted_by_fives[:num_dice - half]
        if len(mixed_dice) >= num_dice:
            dice_sel = mixed_dice[:num_dice]
            combinations_to_test.append({
                "dice": dice_sel,
                "name": self._format_combo_name(dice_sel)
            })
        
        # Add dice sets optimized for 1s only and 5s only
        dice_sel_ones = sorted_by_ones[:num_dice]
        combinations_to_test.append({
            "dice": dice_sel_ones,
            "name": self._format_combo_name(dice_sel_ones)
        })
        
        dice_sel_fives = sorted_by_fives[:num_dice]
        combinations_to_test.append({
            "dice": dice_sel_fives,
            "name": self._format_combo_name(dice_sel_fives)
        })
        
        # 4. Test dice focused on straights
        progress = 25
        if progress_callback:
            progress_callback(progress)
            
        straight_dice = []
        for die in available_dice:
            # Calculate how balanced the die is across all values
            balance_score = sum(abs(die.probability_of(i) - 100/6) for i in range(1, 7))
            if balance_score < 50:  # This die has relatively balanced probabilities
                straight_dice.append(die)
        
        if len(straight_dice) >= num_dice:
            dice_sel = straight_dice[:num_dice]
            combinations_to_test.append({
                "dice": dice_sel,
                "name": self._format_combo_name(dice_sel)
            })
        
        # 5. Add a few random mixes for variety
        progress = 30
        if progress_callback:
            progress_callback(progress)
            
        # Generate more random combinations if we have many dice types
        if len(available_dice) >= 10:
            num_random = min(10, len(available_dice) // 2)
            for i in range(num_random):
                random_sample = random.sample(available_dice, num_dice)
                combinations_to_test.append({
                    "dice": random_sample,
                    "name": self._format_combo_name(random_sample)
                })
    
    # Simulate each combination
    logger.info(f"Testing {len(combinations_to_test)} dice combinations")
    results = []
    total_combos = len(combinations_to_test)
    start_percent = max(30, int(progress))  # ensure we start at least at 30% after preparation
    end_percent = 90

    workers = max(1, (os.cpu_count() or 4) - 1)

    # Acceleration log + JIT warm-up
    logger.info(f"Acceleration: NumPy={'on' if np is not None else 'off'}, "
                f"NumbaJIT={'on' if _score_dice_roll_jit else 'off'}")
    if _score_dice_roll_jit is not None and np is not None:
        t0 = time.time()
        _ = _score_dice_roll_jit(np.array([1,2,3,4,5,6], dtype=np.int64))
        logger.info(f"JIT warm-up took {time.time() - t0:.2f}s")

    # Build payloads for processes to avoid pickling large objects
    payloads = [
        {
            "name": combo["name"],
            "dice_names": [d.name for d in combo["dice"]],
            "sims": max(1, num_simulations // 2),
        }
        for combo in combinations_to_test
    ]

    # Stream submissions to keep memory and scheduler pressure low
    max_in_flight = max(workers * 4, 8)
    submitted = 0
    completed = 0
    in_flight = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        # Prime the pool
        while submitted < len(payloads) and len(in_flight) < max_in_flight:
            f = executor.submit(_eval_combo_worker, payloads[submitted])
            in_flight[f] = submitted
            submitted += 1
        # Process as they complete and keep submitting
        while in_flight:
            for fut in as_completed(list(in_flight.keys())):
                in_flight.pop(fut, None)
                completed += 1
                try:
                    res = fut.result()
                except Exception as e:
                    logger.warning(f"Worker raised exception: {e}")
                    res = {"error": str(e)}
                if isinstance(res, dict) and "error" in res:
                    logger.warning(f"Worker error for {res.get('name','Unknown')}: {res['error']}")
                else:
                    results.append(res)
                # Update progress
                if progress_callback and total_combos > 0:
                    frac = completed / total_combos
                    percent = start_percent + int(frac * (end_percent - start_percent))
                    progress_callback(min(end_percent, max(start_percent, percent)))
                if status_callback:
                    status_callback(completed, total_combos, time.time() - start_time)
                # Keep the pipeline full
                while submitted < len(payloads) and len(in_flight) < max_in_flight:
                    f = executor.submit(_eval_combo_worker, payloads[submitted])
                    in_flight[f] = submitted
                    submitted += 1
    
    # Sort by composite rank (EV + EV/roll + reliability)
    results.sort(key=lambda x: x.get("rank_score", 0.0), reverse=True)
    
    # Return the best result
    if results:
        best = results[0]
        logger.info(f"Best dice combination found: {best['name']}")
        logger.info(f"Expected score: {best['expected_value']:.2f}")
        logger.info(f"Bust rate: {best['bust_rate']:.2%}")
        
        # Final result with all combinations
        result = {
            "dice_combination": best["name"],
            "dice_composition": best["dice_combination"],
            "dice_objects": next(c["dice"] for c in combinations_to_test if c["name"] == best["name"]),
            "expected_score": best["expected_value"],
            "bust_rate": best["bust_rate"],
            "avg_rolls": best["avg_rolls"],
            "common_scores": best["common_scores"],
            "max_score": best["max_score"],
            "all_combinations": results
        }
    else:
        logger.warning("No valid dice combinations found")
        result = {"error": "No valid dice combinations found"}
    
    # Final progress update
    if progress_callback:
        progress_callback(100)  # Complete
    
    elapsed_time = time.time() - start_time
    logger.info(f"Optimal dice search completed in {elapsed_time:.2f} seconds")
    
    return result
