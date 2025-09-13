"""
Kingdom Come: Deliverance 2 Dice Scoring System
Implements the scoring rules from the game for calculating probabilities and scores.
"""

import itertools
import random
from collections import Counter

# Optional acceleration
try:
    import numpy as np  # type: ignore
    from numba import njit, int64  # type: ignore
    _NUMBA_AVAILABLE = True
except Exception:  # pragma: no cover
    np = None  # type: ignore
    njit = None  # type: ignore
    int64 = None  # type: ignore
    _NUMBA_AVAILABLE = False

# Scoring rules as per SCORING.md
SCORING_RULES = {
    'single_1': 100,     # Single 1
    'single_5': 50,      # Single 5
    'partial_straight_1': 500,   # Partial straight (1, 2, 3, 4, 5)
    'partial_straight_2': 750,   # Partial straight (2, 3, 4, 5, 6)
    'full_straight': 1500,       # Full straight (1, 2, 3, 4, 5, 6)
    'three_1': 1000,  # Three 1s - changed from three_ones to be consistent
    'three_2': 200,      # Three 2s
    'three_3': 300,      # Three 3s
    'three_4': 400,      # Three 4s
    'three_5': 500,      # Three 5s
    'three_6': 600,      # Three 6s
    # Four or more of a kind handled in score_combination function
}

def get_all_scoring_combinations():
    """Get all possible scoring combinations and their descriptions."""
    return {
        'single_1': 'Single 1',
        'single_5': 'Single 5',
        'partial_straight_1': 'Partial straight (1, 2, 3, 4, 5)',
        'partial_straight_2': 'Partial straight (2, 3, 4, 5, 6)',
        'full_straight': 'Full straight (1, 2, 3, 4, 5, 6)',
        'three_ones': 'Three 1s',
        'three_2': 'Three 2s',
        'three_3': 'Three 3s',
        'three_4': 'Three 4s',
        'three_5': 'Three 5s',
        'three_6': 'Three 6s',
        'four_1': 'Four 1s',
        'four_2': 'Four 2s',
        'four_3': 'Four 3s',
        'four_4': 'Four 4s',
        'four_5': 'Four 5s',
        'four_6': 'Four 6s',
        'five_1': 'Five 1s',
        'five_2': 'Five 2s',
        'five_3': 'Five 3s',
        'five_4': 'Five 4s',
        'five_5': 'Five 5s',
        'five_6': 'Five 6s',
        'six_1': 'Six 1s',
        'six_2': 'Six 2s',
        'six_3': 'Six 3s',
        'six_4': 'Six 4s',
        'six_5': 'Six 5s',
        'six_6': 'Six 6s'
    }

def score_dice_roll(dice_values):
    """
    Score a dice roll based on KCD2 scoring rules.
    Takes into account multiple scoring combinations in a single roll.
    
    Args:
        dice_values: List of integers representing dice values (1-6)
        
    Returns:
        tuple: (total_score, combinations_list, description)
            where combinations_list is a list of (score, combo_name) tuples
            and description is a string describing all scoring elements
    """
    # Count occurrences of each value
    counter = Counter(dice_values)
    total_score = 0
    combinations = []
    remaining_dice = list(dice_values)  # Copy to track which dice have been used
    
    # Check for straights first (they have highest priority and use all dice)
    if set([1, 2, 3, 4, 5, 6]).issubset(set(dice_values)):
        score = SCORING_RULES['full_straight']
        total_score += score
        combinations.append((score, 'full_straight'))
        desc = 'Full straight (1, 2, 3, 4, 5, 6)'
        remaining_dice = []  # All dice used
        return total_score, combinations, desc
    
    if set([1, 2, 3, 4, 5]).issubset(set(dice_values)):
        score = SCORING_RULES['partial_straight_1']
        total_score += score
        combinations.append((score, 'partial_straight_1'))
        desc = 'Partial straight (1, 2, 3, 4, 5)'
        # Remove used dice
        for val in [1, 2, 3, 4, 5]:
            remaining_dice.remove(val)
    elif set([2, 3, 4, 5, 6]).issubset(set(dice_values)):
        score = SCORING_RULES['partial_straight_2']
        total_score += score
        combinations.append((score, 'partial_straight_2'))
        desc = 'Partial straight (2, 3, 4, 5, 6)'
        # Remove used dice
        for val in [2, 3, 4, 5, 6]:
            remaining_dice.remove(val)
    else:
        desc = ''
        # Create a copy of the counter to track remaining counts after processing
        remaining_counter = Counter(remaining_dice)
        
        # Check for multiples of the same number (X of a kind)
        # Process values from highest to lowest for optimal scoring
        for value in sorted(counter.keys(), reverse=True):
            count = remaining_counter[value]
            if count >= 3:
                # Calculate score for three or more of a kind
                if value == 1:
                    base_score = SCORING_RULES['three_1']
                    combo_key = 'three_1'
                    combo_desc = 'Three 1s'
                else:
                    base_score = SCORING_RULES[f'three_{value}']
                    combo_key = f'three_{value}'
                    combo_desc = f'Three {value}s'
                    
                # If more than three, double the score for each additional die
                if count > 3:
                    multiplier = 2 ** (count - 3)
                    score = base_score * multiplier
                    combo_key = f'{"four" if count == 4 else "five" if count == 5 else "six"}_{value}'
                    combo_desc = f'{"Four" if count == 4 else "Five" if count == 5 else "Six"} {value}s'
                else:
                    score = base_score
                
                # Add to total score and combinations list
                total_score += score
                combinations.append((score, combo_key))
                
                # Add to description
                if desc:
                    desc += ' + '
                desc += combo_desc
                
                # Remove these dice from consideration
                for _ in range(count):
                    remaining_dice.remove(value)
                remaining_counter = Counter(remaining_dice)
    
    # Check for remaining single 1s or 5s
    ones_count = remaining_dice.count(1)
    if ones_count > 0:
        score_ones = ones_count * SCORING_RULES['single_1']
        total_score += score_ones
        combinations.append((score_ones, 'single_1'))
        
        if desc:
            desc += ' + '
        desc += f"{ones_count} {'Single 1' if ones_count == 1 else 'Single 1s'}"
        
        # Remove these dice
        for _ in range(ones_count):
            remaining_dice.remove(1)
    
    fives_count = remaining_dice.count(5)
    if fives_count > 0:
        score_fives = fives_count * SCORING_RULES['single_5']
        total_score += score_fives
        combinations.append((score_fives, 'single_5'))
        
        if desc:
            desc += ' + '
        desc += f"{fives_count} {'Single 5' if fives_count == 1 else 'Single 5s'}"
        
        # Remove these dice
        for _ in range(fives_count):
            remaining_dice.remove(5)
    
    # If no scoring combinations were found
    if total_score == 0:
        return 0, [], 'No scoring combination'
    
    return total_score, combinations, desc

# ---------------------------------------------------------------------------
# Optional Numba-accelerated scoring (numeric score only)
# ---------------------------------------------------------------------------

if _NUMBA_AVAILABLE:
    @njit(cache=True)
    def _score_dice_roll_numba(arr):  # type: ignore
        # arr is int64[:] with values in 1..6
        n = arr.size
        counts = np.zeros(7, dtype=np.int64)
        for i in range(n):
            v = arr[i]
            if v < 1 or v > 6:
                continue
            counts[v] += 1

        total = 0

        # Full straight uses all dice (1..6 present) and only meaningful for 6 dice
        full = 1
        for v in range(1, 7):
            if counts[v] == 0:
                full = 0
                break
        if full == 1 and n == 6:
            return 1500

        # Partial straights (consume those dice)
        # 1-5 => 500, 2-6 => 750
        p1 = 1
        for v in range(1, 6):
            if counts[v] == 0:
                p1 = 0
                break
        if p1 == 1:
            total += 500
            for v in range(1, 6):
                counts[v] -= 1
        else:
            p2 = 1
            for v in range(2, 7):
                if counts[v] == 0:
                    p2 = 0
                    break
            if p2 == 1:
                total += 750
                for v in range(2, 7):
                    counts[v] -= 1

        # Three or more of a kind, process high to low
        for v in range(6, 0, -1):
            c = counts[v]
            if c >= 3:
                if v == 1:
                    base = 1000
                else:
                    base = v * 100
                if c > 3:
                    # multiplier = 2 ** (c - 3)
                    shift = c - 3
                    mult = 1
                    for _ in range(shift):
                        mult = mult * 2
                    score = base * mult
                else:
                    score = base
                total += score
                counts[v] = 0

        # Singles: 1s and 5s
        if counts[1] > 0:
            total += counts[1] * 100
            counts[1] = 0
        if counts[5] > 0:
            total += counts[5] * 50
            counts[5] = 0

        return total

    def _score_dice_roll_jit(arr):
        """Public accelerated scorer used by the simulator hot loops.
        Accepts a numpy int64 array and returns the numeric score (int).
        If arr is not an ndarray, attempts to convert.
        """
        if not isinstance(arr, np.ndarray):
            arr = np.asarray(arr, dtype=np.int64)
        else:
            if arr.dtype != np.int64:
                arr = arr.astype(np.int64)
        return int(_score_dice_roll_numba(arr))
else:
    # Fallback when numba/numpy is not available
    _score_dice_roll_jit = None  # type: ignore

def calculate_dice_roll_probability(dice, target_values):
    """
    Calculate the probability of rolling specific values with a set of dice.
    
    Args:
        dice: List of Die objects to roll
        target_values: List of target values (1-6) for each die position
        
    Returns:
        float: Probability as a percentage
    """
    if len(dice) != len(target_values):
        raise ValueError("Number of dice must match number of target values")
    
    # Calculate probability as product of individual probabilities
    probability = 1.0
    for i, die in enumerate(dice):
        target = target_values[i]
        # Get probability of rolling the target number with this die
        prob = die.probability_of(target) / 100.0  # Convert from percentage to decimal
        probability *= prob
    
    # Return as percentage
    return probability * 100.0

def evaluate_all_possible_scores(dice_combo, num_dice=6, max_simulations=10000):
    """
    Monte Carlo simulation to evaluate all possible scoring outcomes with a set of dice.
    
    Args:
        dice_combo: List of Die objects
        num_dice: Number of dice to use
        max_simulations: Maximum number of simulations to run
        
    Returns:
        dict: Mapping from score to (probability, description, sample_roll)
    """
    # If we don't have enough dice, use what we have
    if len(dice_combo) < num_dice:
        num_dice = len(dice_combo)
    
    # Use a subset of dice if needed
    dice_to_use = dice_combo[:num_dice]
    
    # Run simulations by randomly rolling each die
    score_counter = Counter()
    score_descriptions = {}
    score_sample_rolls = {}
    
    num_simulations = min(max_simulations, 6 ** num_dice)  # Limit simulations for performance
    
    for _ in range(num_simulations):
        # Roll each die
        roll = []
        for die in dice_to_use:
            # Simulate a roll by randomly selecting based on probabilities
            sides = list(range(1, 7))
            weights = die.weights
            roll.append(random.choices(sides, weights=weights)[0])
        
        # Score the roll
        score, _, desc = score_dice_roll(roll)
        
        # Update counters
        score_counter[score] += 1
        
        # Save description and sample roll for this score if not already stored
        if score not in score_descriptions:
            score_descriptions[score] = desc
            score_sample_rolls[score] = roll
    
    # Calculate probabilities
    result = {}
    for score, count in score_counter.items():
        probability = (count / num_simulations) * 100.0
        result[score] = (probability, score_descriptions[score], score_sample_rolls[score])
    
    return result

def find_optimal_dice_for_score(available_dice, num_dice=6, max_combinations=1000):
    """
    Find the optimal dice combinations for maximizing expected score.
    Uses a more sophisticated approach that considers all possible scoring combinations.
    
    Args:
        available_dice: List of Die objects available
        num_dice: Number of dice to use
        max_combinations: Maximum number of dice combinations to evaluate
        
    Returns:
        list: List of (expected_score, dice_combination, top_scores) tuples,
              sorted by expected score (descending)
    """
    # If we don't have enough dice, use what we have
    if len(available_dice) < num_dice:
        num_dice = len(available_dice)
    
    # Generate all possible combinations of dice (up to max_combinations)
    all_dice_combinations = []
    
    if len(available_dice) <= 10:  # Only do combinations for reasonable numbers of dice
        # Get all combinations of dice
        all_combinations = list(itertools.combinations(range(len(available_dice)), num_dice))
        
        # Limit the number of combinations to evaluate
        if len(all_combinations) > max_combinations:
            all_combinations = random.sample(all_combinations, max_combinations)
        
        # Convert indices to dice objects
        for combo_indices in all_combinations:
            combo = [available_dice[idx] for idx in combo_indices]
            all_dice_combinations.append(combo)
    else:
        # For large numbers of available dice, just sample random combinations
        for _ in range(min(max_combinations, 100)):
            combo = random.sample(available_dice, num_dice)
            all_dice_combinations.append(combo)
    
    # Always include the first num_dice dice as a baseline
    if len(available_dice) >= num_dice and available_dice[:num_dice] not in all_dice_combinations:
        all_dice_combinations.append(available_dice[:num_dice])
    
    # Evaluate each combination
    results = []
    
    for dice_combo in all_dice_combinations:
        # Evaluate all possible scores with this combination
        score_results = evaluate_all_possible_scores(dice_combo, num_dice)
        
        # Calculate expected score
        expected_score = sum(score * (prob/100.0) for score, (prob, _, _) in score_results.items())
        
        # Get top 3 most likely scores
        top_scores = sorted([(score, prob, desc) 
                           for score, (prob, desc, _) in score_results.items()], 
                           key=lambda x: x[1], reverse=True)[:3]
        
        results.append((expected_score, list(dice_combo), top_scores))
    
    # Sort by expected score (descending)
    results.sort(key=lambda x: x[0], reverse=True)
    return results

def find_optimal_scoring_strategy(available_dice, dice_count):
    """
    Find the optimal scoring strategy given available dice.
    Uses the improved algorithm that accounts for all scoring combinations.
    
    Args:
        available_dice: List of Die objects available
        dice_count: Number of dice to use
    
    Returns:
        list: List of tuples with scoring strategy details, sorted by expected value
    """
    # Import random at the function level to avoid global import issues
    import random
    
    # Find optimal dice combinations
    optimal_combos = find_optimal_dice_for_score(available_dice, dice_count)
    
    # Convert to the expected format for the UI
    results = []
    
    for expected_score, dice_combo, top_scores in optimal_combos:
        # Use the top score as the main one for display
        if top_scores:
            main_score, main_prob, main_desc = top_scores[0]
        else:
            main_score, main_prob, main_desc = 0, 0, "No scoring combination"
        
        # Create a description that includes info about multiple possible outcomes
        description = main_desc
        if len(top_scores) > 1:
            description += f" (and other combinations)"
        
        results.append((
            main_score,
            main_prob,
            dice_combo,
            "multiple_scoring",  # New type for multiple scoring combos
            description,
            expected_score
        ))
    
    return results
