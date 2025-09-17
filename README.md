# Kingdom Come: Deliverance 2 Dice Calculator

A Python application that helps players optimize their dice selection and strategy in Kingdom Come: Deliverance 2.

## Features

- **Dice Information**: View detailed information about all dice in the game, including probability distributions and descriptions
- **Inventory Management**: Track which dice you have available for use
- **Target Calculator**: Calculate the optimal combination of dice to maximize your chances of rolling specific numbers
- **Single Combo Simulator**: Test a specific dice combination with advanced banking rules and decision breakdowns
- **Game Simulator (Player vs AI)**: Simulate full games to a point cap against an AI profile (no badges) and get win rates and more
- **Play Book**: Real-time assistant for actual gameplay with turn-by-turn guidance optimized for win probability
- **Strategy Calculator** (WIP): Find the best dice combination and strategy to maximize your expected score
- **Progress Tracking**: Real-time progress updates during calculations

## Requirements

- Python 3.8 or higher
- Required packages: numpy, matplotlib, pillow, ttkthemes

## Installation

1. Make sure you have Python installed on your system.
2. Install the required packages:

```
pip install -r requirements.txt
```

## Usage

Run the application with the following command:

```
python main.py
```

### Dice Information Tab

Browse through the list of all dice in the game. Selecting a die will display:
- Die description
- Weight distribution
- Probability percentages for each side
- Visual chart of probability distribution

### Inventory Tab

Set the quantity of each die that you have available in your collection. This information is used by the calculator to determine which dice you can include in combinations.

### Target Calculator Tab

1. Select the target numbers you want to optimize for (e.g., if you want to maximize chances of rolling 1's and 6's, check those boxes)
2. Set the weights for each target to indicate their relative importance (higher = more important)
3. Choose how many dice to include in the combination (1-6)
4. Click "Calculate Best Combination" to get results

The results will show:
- The best combination of dice from your inventory
- Probability distribution for all numbers
- Weighted score based on your preferences

### Single Combo Simulator Tab

Test a specific 6-dice combination with advanced options:
1. Select dice for each of the 6 positions
2. Configure simulation settings:
   - Number of simulations to run
   - Minimum Bank Value: Set a threshold score required to bank in early rolls
   - Apply to first N rolls: How many early rolls the minimum bank rule applies to
   - Show decision breakdown: Display detailed turn logs showing decisions made
   - Don't bank if all dice used: Continue after clearing all dice instead of banking

Results include:
- Average score per turn
- Expected score (adjusted for bust rate)
- Bust rate percentage
- Average rolls per turn
- Common scores with their frequencies
- Top scores by value with their frequencies
- Maximum score observed
- Decision breakdown (when enabled)

### Game Simulator Tab (Player vs AI)

Simulate complete games against an AI opponent using the same turn logic as the Single Combo Simulator.

1. Select 6 dice for the Player
2. Select 6 dice for the AI
3. Choose an AI Profile (difficulty) – see `AI_BEHAVIOR.md` for details; badges are not modeled
4. Set the number of games and win target (point cap)
5. Run the simulation

Results include:
- Player and AI win percentages
- Average turns per game
- Average margin (Player - AI)
- Distribution of game lengths (by number of turns)
- Elapsed time
- Example game logs showing turn-by-turn decisions

### Play Book Tab

The Play Book is a real-time assistant for actual gameplay that provides turn-by-turn guidance:

1. Select your 6 dice for the turn (or load from Game Simulator)
2. Set your game parameters:
   - Game point limit (default: 8000)
   - Your current Overall score
   - AI's current score (for win probability calculations)
3. Enter your roll values for each die (labeled with die names and D# tags)
4. Click "Suggest Best Keep" to get ranked options

The Play Book offers:
- Win probability optimization: Ranks options by chance to win the game from your exact state
- EV optimization: Alternative ranking by risk-adjusted expected value
- Fast mode: Quick heuristic suggestions when you need speed over precision
- Risk penalty adjustment: Control risk aversion in EV mode
- One-click application of suggestions
- Banking recommendations when reaching the game limit
- Turn and overall score tracking

Controls:
- Load Player Dice from Game Simulator: Copy dice from Game Simulator tab
- Reset Turn: Clear current turn (keeps Overall score)
- Full Reset: Reset Overall score and current turn
- Bank Now: End turn and add points to Overall score
- Apply #1-5: Apply specific suggestions from the ranked list

### Strategy Calculator Tab (Work in Progress)

This tab is currently under development. When completed, it will:
1. Find the optimal dice combination from your inventory
2. Compare different playing strategies
3. Provide detailed statistics on expected performance

## Saving Your Data

Your inventory is automatically saved when you close the application or click "Save Inventory".

## Calculation Methods

### Target Calculator
Uses probability analysis to find dice combinations that maximize the chance of rolling specific target numbers based on their weights.

### Single Combo Simulator
Simulates thousands of turns with a specific dice combination, using optimal decision-making at each step. Includes:
- Banking threshold rules for early rolls
- Options to continue after clearing all dice
- Detailed breakdowns of decisions made during turns

### Play Book
Uses Monte Carlo simulation to estimate win probability from any game state:
- Simulates the rest of the current turn from your exact dice state
- Continues with alternating turns (player/AI) until someone reaches the game limit
- Ranks options by probability of winning the game, not just by expected points
- Accounts for your banking rules, game point limit, and current scores

### Strategy Calculator (WIP)
Will run simulations across different dice combinations to determine the optimal setup and playing strategy.

## Performance Notes

- The Strategy Calculator can be resource-intensive with many dice combinations
- Progress is shown in real-time, including combinations tested per minute and estimated time remaining
- You can cancel a running calculation at any time
