"""
Kingdom Come: Deliverance 2 Dice Calculator
A calculator and information app for KCD 2 dice that allows users to:
- View each die and their description
- See weight and weight percentage information for dice
- Calculate the best combination of dice for desired outcomes
"""

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from dice_data import load_dice_data, get_die_by_name, get_all_dice_names, Die
from scoring_system import find_optimal_scoring_strategy, get_all_scoring_combinations

# Ensure dice data is loaded
ALL_DICE = load_dice_data()

# Constants
PADDING = 10
DICE_INVENTORY_FILE = "dice_inventory.json"

class DiceCalculatorApp:
    def __init__(self, root):
        """Initialize the main application window."""
        self.root = root
        self.root.title("KCD2 Dice Calculator")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Set up the main tab control
        self.tab_control = ttk.Notebook(self.root)
        
        # Create tabs
        self.info_tab = ttk.Frame(self.tab_control)
        self.inventory_tab = ttk.Frame(self.tab_control)
        self.calculator_tab = ttk.Frame(self.tab_control)
        self.scoring_tab = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.info_tab, text="Dice Information")
        self.tab_control.add(self.inventory_tab, text="Inventory")
        self.tab_control.add(self.calculator_tab, text="Target Calculator")
        self.tab_control.add(self.scoring_tab, text="Scoring Calculator")
        
        self.tab_control.pack(expand=1, fill="both")
        
        # Initialize inventory data
        self.inventory = self.load_inventory()
        
        # Set up each tab
        self.setup_info_tab()
        self.setup_inventory_tab()
        self.setup_calculator_tab()
        self.setup_scoring_tab()
    
    def setup_info_tab(self):
        """Set up the Dice Information tab."""
        frame = ttk.Frame(self.info_tab, padding=PADDING)
        frame.pack(fill="both", expand=True)
        
        # Left panel for dice list
        list_frame = ttk.LabelFrame(frame, text="Dice List", padding=PADDING)
        list_frame.pack(side="left", fill="both", expand=False)
        
        # Create a listbox with all dice names
        dice_names = sorted(get_all_dice_names())
        self.dice_listbox = tk.Listbox(list_frame, width=30, height=30)
        for name in dice_names:
            self.dice_listbox.insert(tk.END, name)
        
        self.dice_listbox.pack(fill="both", expand=True)
        self.dice_listbox.bind('<<ListboxSelect>>', self.on_die_selected)
        
        # Right panel for dice details
        self.detail_frame = ttk.LabelFrame(frame, text="Dice Details", padding=PADDING)
        self.detail_frame.pack(side="right", fill="both", expand=True)
        
        # Die information
        self.die_name_label = ttk.Label(self.detail_frame, text="", font=("Arial", 14, "bold"))
        self.die_name_label.pack(anchor="w", pady=(0, 10))
        
        self.die_desc_label = ttk.Label(self.detail_frame, text="", wraplength=400)
        self.die_desc_label.pack(anchor="w", pady=(0, 10))
        
        self.die_id_label = ttk.Label(self.detail_frame, text="")
        self.die_id_label.pack(anchor="w", pady=(0, 10))
        
        self.die_weight_label = ttk.Label(self.detail_frame, text="")
        self.die_weight_label.pack(anchor="w", pady=(0, 10))
        
        # Frame for probability distribution
        self.prob_frame = ttk.LabelFrame(self.detail_frame, text="Probability Distribution", padding=PADDING)
        self.prob_frame.pack(fill="both", expand=True)
        
        # Table for probabilities
        self.prob_table = ttk.Treeview(self.prob_frame, columns=("Side", "Weight", "Probability"))
        self.prob_table.heading("Side", text="Side")
        self.prob_table.heading("Weight", text="Weight")
        self.prob_table.heading("Probability", text="Probability %")
        self.prob_table["show"] = "headings"
        self.prob_table.pack(fill="both", expand=True, pady=10)
        
        # Frame for the chart
        self.chart_frame = ttk.Frame(self.detail_frame)
        self.chart_frame.pack(fill="both", expand=True)
        
        # Select the first die by default
        if dice_names:
            self.dice_listbox.selection_set(0)
            self.on_die_selected(None)
    
    def setup_inventory_tab(self):
        """Set up the Inventory tab."""
        frame = ttk.Frame(self.inventory_tab, padding=PADDING)
        frame.pack(fill="both", expand=True)
        
        # Instructions
        ttk.Label(frame, text="Set the quantity of each die you have in your inventory:", 
                 font=("Arial", 12)).pack(anchor="w", pady=(0, 10))
        
        # Create a scrollable frame for the inventory items
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create header row
        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Label(header_frame, text="Die Name", width=30, font=("Arial", 10, "bold")).grid(row=0, column=0, padx=5)
        ttk.Label(header_frame, text="Quantity", width=10, font=("Arial", 10, "bold")).grid(row=0, column=1, padx=5)
        
        # Create inventory entries
        self.quantity_vars = {}
        dice_names = sorted(get_all_dice_names())
        
        for idx, name in enumerate(dice_names):
            row_frame = ttk.Frame(scrollable_frame)
            row_frame.pack(fill="x", pady=2)
            
            ttk.Label(row_frame, text=name, width=30).grid(row=0, column=0, padx=5)
            
            self.quantity_vars[name] = tk.StringVar(value=str(self.inventory.get(name, 0)))
            quantity_entry = ttk.Spinbox(
                row_frame, 
                from_=0, 
                to=10, 
                width=5, 
                textvariable=self.quantity_vars[name]
            )
            quantity_entry.grid(row=0, column=1, padx=5)
        
        # Button to save inventory
        ttk.Button(
            frame, 
            text="Save Inventory", 
            command=self.save_inventory
        ).pack(pady=10)
    
    def setup_calculator_tab(self):
        """Set up the Calculator tab."""
        frame = ttk.Frame(self.calculator_tab, padding=PADDING)
        frame.pack(fill="both", expand=True)
        
        # Top frame for inputs
        input_frame = ttk.LabelFrame(frame, text="Calculation Parameters", padding=PADDING)
        input_frame.pack(fill="x", pady=(0, 10))
        
        # Instructions
        ttk.Label(input_frame, text="Select the target number for each die position:", 
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        # Test Mode checkbox
        self.test_mode_var = tk.BooleanVar(value=False)
        test_mode_cb = ttk.Checkbutton(
            input_frame,
            text="Test Mode (Assume 6 of each die)",
            variable=self.test_mode_var
        )
        test_mode_cb.grid(row=0, column=2, sticky="e", padx=10)
        
        # Create die position selectors
        self.target_vars = {}
        
        # Create a frame for each die position
        positions_frame = ttk.Frame(input_frame)
        positions_frame.grid(row=1, column=0, columnspan=3, sticky="w", pady=5)
        
        # Create a combobox for each die position to select target number
        for i in range(1, 7):
            pos_frame = ttk.Frame(positions_frame)
            pos_frame.pack(side="left", padx=15)
            
            ttk.Label(pos_frame, text=f"Die {i}", font=("Arial", 10, "bold")).pack(anchor="center")
            
            self.target_vars[i] = tk.StringVar(value=str(i))
            die_combo = ttk.Combobox(pos_frame, values=["1", "2", "3", "4", "5", "6"], 
                                    width=5, textvariable=self.target_vars[i], state="readonly")
            die_combo.pack(pady=5)
            die_combo.set(str(i))  # Default to the die position as target
        
        # Calculate button
        ttk.Button(
            input_frame, 
            text="Calculate Best Combination", 
            command=self.calculate_best_combination
        ).grid(row=2, column=0, columnspan=3, pady=10)
        
        # Bottom frame for results
        results_frame = ttk.LabelFrame(frame, text="Results", padding=PADDING)
        results_frame.pack(fill="both", expand=True)
        
        # Add text area for results
        self.results_text = tk.Text(results_frame, height=10, wrap="word")
        self.results_text.pack(fill="both", expand=True, pady=(0, 10))
        
        # Frame for the probability chart
        self.result_chart_frame = ttk.Frame(results_frame)
        self.result_chart_frame.pack(fill="both", expand=True)
    
    def on_die_selected(self, event):
        """Handle selection of a die from the listbox."""
        selection = self.dice_listbox.curselection()
        if not selection:
            return
            
        die_name = self.dice_listbox.get(selection[0])
        die = get_die_by_name(die_name)
        
        if not die:
            return
            
        # Update die information
        self.die_name_label.config(text=die.name)
        self.die_desc_label.config(text=die.description)
        self.die_id_label.config(text=f"ID: {die.item_id}")
        self.die_weight_label.config(text=f"Total Weight: {die.total_weight}")
        
        # Clear existing table rows
        for item in self.prob_table.get_children():
            self.prob_table.delete(item)
            
        # Populate the table
        for i in range(6):
            self.prob_table.insert(
                "", 
                "end", 
                values=(
                    f"{i+1}", 
                    f"{die.weights[i]}", 
                    f"{die.probabilities[i]}%"
                )
            )
        
        # Update the chart
        self.update_probability_chart(die)
    
    def update_probability_chart(self, die):
        """Update the probability chart for the selected die."""
        # Clear previous chart
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(5, 3))
        sides = list(range(1, 7))
        probabilities = die.probabilities
        
        # Create bar chart
        bars = ax.bar(sides, probabilities, color='skyblue')
        
        # Add labels and title
        ax.set_xlabel('Die Side')
        ax.set_ylabel('Probability (%)')
        ax.set_title(f'{die.name} Probability Distribution')
        ax.set_xticks(sides)
        
        # Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height}%',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom')
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def calculate_best_combination(self):
        """Calculate the best combination of dice based on user inputs."""
        # Clear previous results
        self.results_text.delete(1.0, tk.END)
        
        try:
            # Get target numbers for each die position
            target_numbers = {}
            for i in range(1, 7):
                if i in self.target_vars and self.target_vars[i].get():
                    target_numbers[i] = int(self.target_vars[i].get())
            
            # Check if test mode is enabled
            if self.test_mode_var.get():
                # Use all dice with quantity 6
                usable_dice = []
                for name in get_all_dice_names():
                    die = get_die_by_name(name)
                    usable_dice.extend([die] * 6)  # 6 of each die in test mode
            else:
                # Use inventory
                available_dice = {name: int(self.quantity_vars[name].get()) for name in self.quantity_vars
                                if int(self.quantity_vars[name].get()) > 0}
                
                if not available_dice:
                    messagebox.showwarning("Empty Inventory", "You don't have any dice in your inventory. "
                                                            "Please add some in the Inventory tab.")
                    return
                
                # Get the list of dice we can use (respecting quantity)
                usable_dice = []
                for name, quantity in available_dice.items():
                    die = get_die_by_name(name)
                    usable_dice.extend([die] * quantity)
            
            # Run the calculation
            self.results_text.insert(tk.END, "Calculating optimal dice for each position...\n\n")
            
            # Find best dice for each position
            best_combo, probabilities = self.find_best_dice_for_positions(
                usable_dice, target_numbers)
            
            # Display results
            self.results_text.insert(tk.END, "Best Dice Combination:\n")
            
            total_probability = 1.0
            for position, (die, target_num, probability) in best_combo.items():
                self.results_text.insert(tk.END, 
                    f"Die position {position}: {die.name} - {probability:.2f}% chance of rolling a {target_num}\n")
                total_probability *= (probability / 100.0)
            
            # Overall probability (multiply individual probabilities)
            overall_percent = total_probability * 100.0
            self.results_text.insert(tk.END, 
                f"\nOverall probability of getting all target numbers: {overall_percent:.4f}%\n")
            
            # Update chart with results
            self.update_results_chart_for_positions(best_combo)
            
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
    
    def find_best_dice_for_positions(self, available_dice, target_numbers):
        """
        Find the best dice for each position based on target numbers.
        
        Args:
            available_dice: List of Die objects available to use
            target_numbers: Dictionary mapping die positions to target numbers
            
        Returns:
            tuple: (best_dice_by_position, overall_probabilities)
        """
        # Dictionary to track which dice have been assigned
        used_dice_indices = set()
        best_dice_by_position = {}
        
        # Calculate the best die for each position
        for position in sorted(target_numbers.keys()):
            target = target_numbers[position]
            best_die = None
            best_prob = -1
            best_idx = -1
            
            # Find the die with highest probability for this target
            for idx, die in enumerate(available_dice):
                if idx in used_dice_indices:
                    continue  # Skip dice that are already assigned
                    
                prob = die.probability_of(target)
                if prob > best_prob:
                    best_prob = prob
                    best_die = die
                    best_idx = idx
            
            if best_die is None:
                # No more dice available
                best_dice_by_position[position] = (None, target, 0)
            else:
                # Assign this die to this position
                best_dice_by_position[position] = (best_die, target, best_prob)
                used_dice_indices.add(best_idx)
        
        # Overall probabilities is just a placeholder now
        overall_probabilities = [0] * 6
        
        return best_dice_by_position, overall_probabilities
    
    def update_results_chart_for_positions(self, best_combo):
        """Update the chart displaying the probabilities for each die position."""
        # Clear previous chart
        for widget in self.result_chart_frame.winfo_children():
            widget.destroy()
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(5, 3))
        
        # Prepare data for the chart
        positions = list(best_combo.keys())
        probabilities = [best_combo[pos][2] for pos in positions]
        target_numbers = [best_combo[pos][1] for pos in positions]
        
        # Create position labels
        position_labels = [f"Die {pos}\n(Target: {target_numbers[i]})" for i, pos in enumerate(positions)]
        
        # Create bar chart
        bars = ax.bar(position_labels, probabilities, color='lightblue')
        
        # Add labels and title
        ax.set_ylabel('Probability (%)')
        ax.set_title('Probability of Target Numbers by Die Position')
        
        # Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.2f}%',
                      xy=(bar.get_x() + bar.get_width() / 2, height),
                      xytext=(0, 3),
                      textcoords="offset points",
                      ha='center', va='bottom')
        
        # Adjust y-axis to include a little padding at the top
        ax.set_ylim(0, max(probabilities) * 1.15)
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.result_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
    def setup_scoring_tab(self):
        """Set up the Scoring Calculator tab."""
        frame = ttk.Frame(self.scoring_tab, padding=PADDING)
        frame.pack(fill="both", expand=True)
        
        # Top frame for inputs
        input_frame = ttk.LabelFrame(frame, text="Scoring Parameters", padding=PADDING)
        input_frame.pack(fill="x", pady=(0, 10))
        
        # Instructions
        ttk.Label(input_frame, text="Find the best dice combination for achieving high scores", 
                 font=("Arial", 11)).grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        # Test Mode checkbox
        self.scoring_test_mode_var = tk.BooleanVar(value=False)
        scoring_test_mode_cb = ttk.Checkbutton(
            input_frame,
            text="Test Mode (Assume 6 of each die)",
            variable=self.scoring_test_mode_var
        )
        scoring_test_mode_cb.grid(row=0, column=1, sticky="e", padx=10)
        
        # Number of dice to use
        dice_count_frame = ttk.Frame(input_frame)
        dice_count_frame.grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        ttk.Label(dice_count_frame, text="Number of Dice:").pack(side="left", padx=(0, 5))
        
        self.scoring_dice_count_var = tk.StringVar(value="6")
        ttk.Spinbox(
            dice_count_frame, 
            from_=1, 
            to=6, 
            width=5, 
            textvariable=self.scoring_dice_count_var
        ).pack(side="left")
        
        # Calculate button
        ttk.Button(
            input_frame, 
            text="Find Best Scoring Combinations", 
            command=self.calculate_best_scoring_combinations
        ).grid(row=1, column=1, padx=10)
        
        # Bottom frame for results
        results_frame = ttk.LabelFrame(frame, text="Scoring Combinations", padding=PADDING)
        results_frame.pack(fill="both", expand=True)
        
        # Create a treeview for the results
        columns = ("rank", "score", "probability", "expected", "combo")
        self.scoring_results_tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        
        # Define column headings
        self.scoring_results_tree.heading("rank", text="#")
        self.scoring_results_tree.heading("score", text="Score")
        self.scoring_results_tree.heading("probability", text="Probability")
        self.scoring_results_tree.heading("expected", text="Expected Value")
        self.scoring_results_tree.heading("combo", text="Combination")
        
        # Define column widths
        self.scoring_results_tree.column("rank", width=40, anchor="center")
        self.scoring_results_tree.column("score", width=80, anchor="center")
        self.scoring_results_tree.column("probability", width=80, anchor="center")
        self.scoring_results_tree.column("expected", width=100, anchor="center")
        self.scoring_results_tree.column("combo", width=400)
        
        # Add scrollbars
        scrollbar_y = ttk.Scrollbar(results_frame, orient="vertical", command=self.scoring_results_tree.yview)
        self.scoring_results_tree.configure(yscrollcommand=scrollbar_y.set)
        
        # Pack the treeview and scrollbar
        self.scoring_results_tree.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")
        
        # Frame for details
        self.scoring_details_frame = ttk.LabelFrame(frame, text="Combination Details", padding=PADDING)
        self.scoring_details_frame.pack(fill="both", expand=False, pady=10)
        
        # Text widget for detailed information
        self.scoring_details_text = tk.Text(self.scoring_details_frame, height=10, wrap="word")
        self.scoring_details_text.pack(fill="both", expand=True)
        
        # Bind treeview selection event
        self.scoring_results_tree.bind("<<TreeviewSelect>>", self.on_scoring_combo_selected)
    
    def calculate_best_scoring_combinations(self):
        """Calculate the best scoring combinations based on inventory."""
        try:
            # Get number of dice to use
            dice_count = int(self.scoring_dice_count_var.get())
            if dice_count < 1 or dice_count > 6:
                raise ValueError("Dice count must be between 1 and 6")
            
            # Check if test mode is enabled
            if self.scoring_test_mode_var.get():
                # Use all dice with quantity 6
                usable_dice = []
                for name in get_all_dice_names():
                    die = get_die_by_name(name)
                    usable_dice.extend([die] * 6)  # 6 of each die in test mode
            else:
                # Use inventory
                available_dice = {name: int(self.quantity_vars[name].get()) for name in self.quantity_vars
                                if int(self.quantity_vars[name].get()) > 0}
                
                if not available_dice:
                    messagebox.showwarning("Empty Inventory", "You don't have any dice in your inventory. "
                                                          "Please add some in the Inventory tab.")
                    return
                
                # Get the list of dice we can use (respecting quantity)
                usable_dice = []
                for name, quantity in available_dice.items():
                    die = get_die_by_name(name)
                    usable_dice.extend([die] * quantity)
            
            # If we have fewer dice than requested, adjust
            if len(usable_dice) < dice_count:
                messagebox.showinfo("Insufficient Dice", f"You only have {len(usable_dice)} dice available. "
                                                    f"Calculation will use all available dice.")
                dice_count = len(usable_dice)
            
            # Find optimal scoring strategies
            results = find_optimal_scoring_strategy(usable_dice, dice_count)
            
            # Clear existing results
            for item in self.scoring_results_tree.get_children():
                self.scoring_results_tree.delete(item)
            
            # Display results in the treeview
            for i, (score, probability, dice_combo, scoring_type, description, expected_value) in enumerate(results[:20], 1):
                # Format the data
                score_str = f"{score:,}"
                prob_str = f"{probability:.2f}%"
                expected_str = f"{expected_value:.2f}"
                
                # Insert into treeview
                self.scoring_results_tree.insert(
                    "", "end", 
                    values=(i, score_str, prob_str, expected_str, description),
                    tags=(scoring_type,)
                )
            
            # Select the first item
            if self.scoring_results_tree.get_children():
                first_item = self.scoring_results_tree.get_children()[0]
                self.scoring_results_tree.selection_set(first_item)
                self.scoring_results_tree.focus(first_item)
                self.on_scoring_combo_selected(None)  # Update details for first item
            
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
    
    def on_scoring_combo_selected(self, event):
        """Handle selection of a scoring combination from the treeview."""
        # Clear previous details
        self.scoring_details_text.delete(1.0, tk.END)
        
        selection = self.scoring_results_tree.selection()
        if not selection:
            return
        
        # Get selected item
        item = selection[0]
        values = self.scoring_results_tree.item(item, "values")
        scoring_type = self.scoring_results_tree.item(item, "tags")[0]
        
        # Get index in results list
        index = int(values[0]) - 1  # Rank is 1-based, index is 0-based
        
        try:
            # Get number of dice to use
            dice_count = int(self.scoring_dice_count_var.get())
            
            # Check if test mode is enabled
            if self.scoring_test_mode_var.get():
                # Use all dice with quantity 6
                usable_dice = []
                for name in get_all_dice_names():
                    die = get_die_by_name(name)
                    usable_dice.extend([die] * 6)  # 6 of each die in test mode
            else:
                # Get dice from inventory again
                available_dice = {name: int(self.quantity_vars[name].get()) for name in self.quantity_vars
                                if int(self.quantity_vars[name].get()) > 0}
                
                usable_dice = []
                for name, quantity in available_dice.items():
                    die = get_die_by_name(name)
                    usable_dice.extend([die] * quantity)
            
            # If we have fewer dice than requested, adjust
            if len(usable_dice) < dice_count:
                dice_count = len(usable_dice)
            
            # Recalculate to get dice combinations
            results = find_optimal_scoring_strategy(usable_dice, dice_count)
            
            if index < len(results):
                score, probability, dice_combo, scoring_type, description, expected_value = results[index]
                
                # Display detailed information
                self.scoring_details_text.insert(tk.END, f"Scoring Combination: {description}\n\n")
                self.scoring_details_text.insert(tk.END, f"Score: {score:,}\n")
                self.scoring_details_text.insert(tk.END, f"Probability: {probability:.4f}%\n")
                self.scoring_details_text.insert(tk.END, f"Expected Value: {expected_value:.2f}\n\n")
                
                self.scoring_details_text.insert(tk.END, "Recommended Dice:\n")
                for i, die in enumerate(dice_combo, 1):
                    self.scoring_details_text.insert(tk.END, f"Die {i}: {die.name} - "
                                                    f"(Weight distribution: {die.weights})\n")
        
        except (ValueError, IndexError):
            self.scoring_details_text.insert(tk.END, "Error retrieving combination details.")
            
    # Keeping these for backward compatibility
    def find_best_dice_combination(self, available_dice, dice_count, targets, weights):
        pass
        
    def calculate_combination_probabilities(self, dice_combo):
        pass
        
    def update_results_chart(self, probabilities):
        pass
    
    def load_inventory(self):
        """Load inventory data from file."""
        if os.path.exists(DICE_INVENTORY_FILE):
            try:
                with open(DICE_INVENTORY_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default inventory - all dice with quantity 0
        return {name: 0 for name in get_all_dice_names()}
    
    def save_inventory(self):
        """Save inventory data to file."""
        inventory = {}
        for name, var in self.quantity_vars.items():
            try:
                inventory[name] = int(var.get())
            except ValueError:
                inventory[name] = 0
        
        with open(DICE_INVENTORY_FILE, 'w') as f:
            json.dump(inventory, f)
        
        self.inventory = inventory
        messagebox.showinfo("Success", "Inventory saved successfully!")


def main():
    root = tk.Tk()
    app = DiceCalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
