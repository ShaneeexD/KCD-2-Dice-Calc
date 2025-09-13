# Kingdom Come: Deliverance 2 Dice Calculator

A Python application that helps players optimize their dice selection in Kingdom Come: Deliverance 2.

## Features

- **Dice Information**: View detailed information about all dice in the game, including probability distributions and descriptions
- **Inventory Management**: Track which dice you have available for use
- **Dice Calculator**: Calculate the optimal combination of dice to maximize your chances of rolling specific numbers

## Requirements

- Python 3.8 or higher
- Required packages: numpy, pandas, matplotlib, pillow

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

### Calculator Tab

1. Select the target numbers you want to optimize for (e.g., if you want to maximize chances of rolling 1's and 6's, check those boxes)
2. Set the weights for each target to indicate their relative importance (higher = more important)
3. Choose how many dice to include in the combination (1-6)
4. Click "Calculate Best Combination" to get results

The results will show:
- The best combination of dice from your inventory
- Probability distribution for all numbers
- Weighted score based on your preferences

## Saving Your Data

Your inventory is automatically saved when you click "Save Inventory" and will be reloaded the next time you run the application.

## Calculation Method

The current algorithm uses a greedy approach to select dice that maximize the probability of rolling your target numbers based on their weights. Future updates may include more sophisticated algorithms for improved recommendations.
