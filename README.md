# Kingdom Come: Deliverance 2 Dice Calculator

A Python application that helps players optimize their dice selection and strategy in Kingdom Come: Deliverance 2.

## Features

- **Dice Information**: View detailed information about all dice in the game, including probability distributions and descriptions
- **Inventory Management**: Track which dice you have available for use
- **Target Calculator**: Calculate the optimal combination of dice to maximize your chances of rolling specific numbers
- **Strategy Calculator**: Find the best dice combination and strategy to maximize your expected score
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

### Strategy Calculator Tab

1. Select the number of dice to use (1-6)
2. Choose the number of simulations to run (more = more accurate but slower)
3. Toggle "Exhaustive Mode" to test all possible combinations (slower but more thorough)
4. Click "Calculate Optimal Strategy" to begin simulation

The results will show:
- Best dice combination for maximum expected score
- Expected score and bust rate
- Average number of rolls per turn
- Strategy comparison table

## Saving Your Data

Your inventory is automatically saved when you close the application or click "Save Inventory".

## Calculation Methods

### Target Calculator
Uses probability analysis to find dice combinations that maximize the chance of rolling specific target numbers based on their weights.

### Strategy Calculator
Runs thousands of simulated turns using different strategies to determine the optimal dice combination and playing strategy. The simulation considers:
- Expected score per turn
- Bust rate
- Average number of rolls
- Maximum observed score

## Performance Notes

- The Strategy Calculator can be resource-intensive with many dice combinations
- Progress is shown in real-time, including combinations tested per minute and estimated time remaining
- You can cancel a running calculation at any time
