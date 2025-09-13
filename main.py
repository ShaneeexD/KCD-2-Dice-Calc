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
import threading

from dice_data import load_dice_data, get_die_by_name, get_all_dice_names, Die
from turn_simulator import find_optimal_dice_combination, DiceSimulator

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
        self.strategy_tab = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.info_tab, text="Dice Information")
        self.tab_control.add(self.inventory_tab, text="Inventory")
        self.tab_control.add(self.calculator_tab, text="Target Calculator")
        self.tab_control.add(self.strategy_tab, text="Strategy Calculator")
        
        self.tab_control.pack(expand=1, fill="both")
        
        # Initialize inventory data
        self.inventory = self.load_inventory()
        
        # Set up each tab
        self.setup_info_tab()
        self.setup_inventory_tab()
        self.setup_calculator_tab()
        self.setup_strategy_tab()
    
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
        
        # Add text area for results (Target Calculator)
        self.target_results_text = tk.Text(results_frame, height=10, wrap="word")
        self.target_results_text.pack(fill="both", expand=True, pady=(0, 10))
        
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
        self.target_results_text.delete(1.0, tk.END)
        
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
            self.target_results_text.insert(tk.END, "Calculating optimal dice for each position...\n\n")
            
            # Find best dice for each position
            best_combo, probabilities = self.find_best_dice_for_positions(
                usable_dice, target_numbers)
            
            # Display results
            self.target_results_text.insert(tk.END, "Best Dice Combination:\n")
            
            total_probability = 1.0
            for position, (die, target_num, probability) in best_combo.items():
                self.target_results_text.insert(tk.END, 
                    f"Die position {position}: {die.name} - {probability:.2f}% chance of rolling a {target_num}\n")
                total_probability *= (probability / 100.0)
            
            # Overall probability (multiply individual probabilities)
            overall_percent = total_probability * 100.0
            self.target_results_text.insert(tk.END, 
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
        
            
    # Keeping these for backward compatibility
    def find_best_dice_combination(self, available_dice, dice_count, targets, weights):
        pass
        
    def calculate_combination_probabilities(self, dice_combo):
        pass
        
    def update_results_chart(self, probabilities):
        pass
    
    def setup_strategy_tab(self):
        """Set up the Strategy Calculator tab for advanced turn simulation."""
        frame = ttk.Frame(self.strategy_tab, padding=PADDING)
        frame.pack(fill="both", expand=True)
        
        # Top frame for inputs
        input_frame = ttk.LabelFrame(frame, text="Strategy Parameters", padding=PADDING)
        input_frame.pack(fill="x", pady=(0, 10))
        
        # Instructions
        ttk.Label(input_frame, text="Simulate full turns with different strategies based on KCD2 dice game rules", 
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        # Test Mode checkbox
        self.strategy_test_mode_var = tk.BooleanVar(value=False)
        strategy_test_mode_cb = ttk.Checkbutton(
            input_frame,
            text="Test Mode (Assume 6 of each die)",
            variable=self.strategy_test_mode_var
        )
        strategy_test_mode_cb.grid(row=0, column=2, sticky="e", padx=10)
        
        # Settings section
        settings_frame = ttk.Frame(input_frame)
        settings_frame.grid(row=1, column=0, columnspan=3, sticky="w", padx=10, pady=5)
        
        # Number of dice to use
        ttk.Label(settings_frame, text="Number of Dice:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.strategy_dice_count_var = tk.StringVar(value="6")
        ttk.Spinbox(
            settings_frame, 
            from_=1, 
            to=6, 
            width=5, 
            textvariable=self.strategy_dice_count_var
        ).grid(row=0, column=1, padx=10)
        
        # Number of simulations
        ttk.Label(settings_frame, text="Simulations:").grid(row=0, column=2, sticky="w", padx=(20, 5))
        self.simulation_count_var = tk.StringVar(value="1000")
        ttk.Spinbox(
            settings_frame, 
            from_=500, 
            to=5000, 
            increment=500,
            width=8, 
            textvariable=self.simulation_count_var
        ).grid(row=0, column=3, padx=10)
        
        # Exhaustive mode checkbox
        self.exhaustive_mode_var = tk.BooleanVar(value=True)
        exhaustive_cb = ttk.Checkbutton(
            settings_frame,
            text="Exhaustive Mode (Test All Combinations)",
            variable=self.exhaustive_mode_var
        )
        exhaustive_cb.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(settings_frame, variable=self.progress_var, 
                                           mode="determinate", length=200)
        self.progress_bar.grid(row=0, column=4, padx=(20, 5))
        
        # Status label for rate/ETA
        self.status_label_var = tk.StringVar(value="")
        self.status_label = ttk.Label(settings_frame, textvariable=self.status_label_var)
        self.status_label.grid(row=0, column=5, padx=(10, 5), sticky="w")
        
        # Calculate button
        self.calculate_button = ttk.Button(
            input_frame, 
            text="Calculate Optimal Strategy", 
            command=self.calculate_optimal_strategy
        )
        self.calculate_button.grid(row=2, column=0, columnspan=3, pady=10)
        
        # Results section
        results_frame = ttk.LabelFrame(frame, text="Optimal Dice & Strategy", padding=PADDING)
        results_frame.pack(fill="x", pady=10)
        
        # Best dice combination and strategy (Strategy Calculator)
        self.strategy_results_text = tk.Text(results_frame, height=6, wrap="word")
        self.strategy_results_text.pack(fill="x", pady=5)
        
        # Display a waiting message
        self.strategy_results_text.insert(tk.END, "Click 'Calculate Optimal Strategy' to find the best dice and strategy for your inventory.\n")
        self.strategy_results_text.insert(tk.END, "This will simulate thousands of turns with different strategies to find the optimal approach.\n")
        
        # Strategies comparison frame
        strategies_frame = ttk.LabelFrame(frame, text="Strategy Comparison", padding=PADDING)
        strategies_frame.pack(fill="both", expand=True)
        
        # Create a treeview for strategy comparison
        columns = ("strategy", "expected_score", "bust_rate", "avg_rolls", "rank_score")
        self.strategy_tree = ttk.Treeview(strategies_frame, columns=columns, show="headings")
        
        # Define column headings
        self.strategy_tree.heading("strategy", text="Strategy")
        self.strategy_tree.heading("expected_score", text="Expected Score")
        self.strategy_tree.heading("bust_rate", text="Bust Rate")
        self.strategy_tree.heading("avg_rolls", text="Avg. Rolls")
        self.strategy_tree.heading("rank_score", text="Rank Score")
        
        # Define column widths
        self.strategy_tree.column("strategy", width=150)
        self.strategy_tree.column("expected_score", width=110, anchor="center")
        self.strategy_tree.column("bust_rate", width=90, anchor="center")
        self.strategy_tree.column("avg_rolls", width=90, anchor="center")
        self.strategy_tree.column("rank_score", width=100, anchor="center")
        
        # Add scrollbars
        scrollbar_y = ttk.Scrollbar(strategies_frame, orient="vertical", command=self.strategy_tree.yview)
        self.strategy_tree.configure(yscrollcommand=scrollbar_y.set)
        
        # Pack the treeview and scrollbar
        self.strategy_tree.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")
        
        # Bind selection event
        self.strategy_tree.bind("<<TreeviewSelect>>", self.on_strategy_selected)
        
        # Details frame
        self.strategy_details_frame = ttk.LabelFrame(frame, text="Strategy Details", padding=PADDING)
        self.strategy_details_frame.pack(fill="both", expand=False, pady=10)
        
        # Chart frame for common scores
        self.strategy_chart_frame = ttk.Frame(self.strategy_details_frame)
        self.strategy_chart_frame.pack(fill="both", expand=True)
    
    def calculate_optimal_strategy(self):
        """Calculate the optimal dice selection and strategy using turn simulation."""
        # Disable the calculate button during calculation
        self.calculate_button.config(state="disabled")
        self.progress_var.set(0)
        
        # Clear existing results
        self.strategy_results_text.delete(1.0, tk.END)
        for item in self.strategy_tree.get_children():
            self.strategy_tree.delete(item)
        
        # Clear chart
        for widget in self.strategy_chart_frame.winfo_children():
            widget.destroy()
        
        # Get input parameters
        try:
            dice_count = int(self.strategy_dice_count_var.get())
            if dice_count < 1 or dice_count > 6:
                raise ValueError("Dice count must be between 1 and 6")
            
            num_simulations = int(self.simulation_count_var.get())
            if num_simulations < 1000:
                num_simulations = 1000  # Minimum for reasonable results
            
            # Check if test mode is enabled
            if self.strategy_test_mode_var.get():
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
                    self.calculate_button.config(state="normal")
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
            
            # Show "calculating" message
            self.strategy_results_text.insert(tk.END, "Calculating optimal strategy...\n")
            self.strategy_results_text.insert(tk.END, "This may take a few moments depending on the number of simulations.\n")
            self.strategy_results_text.see(tk.END)
            self.root.update_idletasks()
            
            # Run the simulation in a separate thread to avoid freezing the UI
            threading.Thread(
                target=self._run_simulation,
                args=(usable_dice, dice_count, num_simulations),
                daemon=True
            ).start()
            
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            self.calculate_button.config(state="normal")
    
    def _update_progress(self, percentage):
        """Update progress in the UI."""
        # Update progress bar
        self.progress_var.set(percentage)
        
        # Update progress text
        self.strategy_results_text.delete(1.0, tk.END)
        self.strategy_results_text.insert(tk.END, f"Calculating optimal strategy... {percentage}% complete\n")
        self.strategy_results_text.insert(tk.END, "This may take a few moments depending on the number of simulations.\n")
        if percentage >= 10:
            self.strategy_results_text.insert(tk.END, "\nAnalyzing dice combinations and strategies...\n")
        self.strategy_results_text.see(tk.END)
        self.root.update_idletasks()

    def _update_status(self, combos_done: int, combos_total: int, elapsed_sec: float):
        """Update rate (combinations/min) and ETA in the status label."""
        if elapsed_sec <= 0:
            return
        rate_per_min = (combos_done / elapsed_sec) * 60.0
        if combos_total > 0 and rate_per_min > 0:
            remaining = max(0, combos_total - combos_done)
            eta_min = remaining / rate_per_min
            self.status_label_var.set(
                f"Combos: {combos_done}/{combos_total} | Rate: {rate_per_min:.1f}/min | ETA: {eta_min:.1f} min"
            )
        else:
            self.status_label_var.set(
                f"Combos: {combos_done} | Rate: {rate_per_min:.1f}/min"
            )
    
    def _run_simulation(self, usable_dice, dice_count, num_simulations):
        """Run the simulation in a background thread and update the UI when done."""
        try:
            # Create a callback function for progress updates
            def progress_callback(percentage):
                # Schedule UI update on the main thread
                self.root.after(0, lambda p=percentage: self._update_progress(p))
            
            # Status callback for rate/ETA updates
            def status_callback(combos_done: int, combos_total: int, elapsed_sec: float):
                self.root.after(0, lambda d=combos_done, t=combos_total, e=elapsed_sec: self._update_status(d, t, e))
            
            # Get exhaustive mode setting
            exhaustive_mode = self.exhaustive_mode_var.get()
            
            # Run the direct simulation with progress reporting
            result = find_optimal_dice_combination(
                usable_dice, 
                dice_count, 
                num_simulations,
                progress_callback,
                exhaustive_mode,
                status_callback,
                max_combos=0  # 0 disables capping; test all combinations
            )
            
            # Update the UI on the main thread
            self.root.after(0, self._update_simulation_results, result)
            
        except Exception as e:
            # Show error on the main thread
            self.root.after(0, lambda: messagebox.showerror("Simulation Error", str(e)))
            self.root.after(0, lambda: self.calculate_button.config(state="normal"))
    
    def _update_simulation_results(self, result):
        """Update the UI with simulation results."""
        # Clear and update results text
        self.strategy_results_text.delete(1.0, tk.END)
        
        if "error" in result:
            self.strategy_results_text.insert(tk.END, f"Error: {result['error']}\n")
            self.calculate_button.config(state="normal")
            return
        
        # Display best dice combination
        self.strategy_results_text.insert(tk.END, f"Best Dice Combination: {result['dice_combination']}\n\n")
        self.strategy_results_text.insert(tk.END, f"Expected Score: {result['expected_score']:.2f}\n")
        self.strategy_results_text.insert(tk.END, f"Bust Rate: {result['bust_rate']*100:.1f}%\n")
        self.strategy_results_text.insert(tk.END, f"Average Rolls per Turn: {result['avg_rolls']:.2f}\n")
        self.strategy_results_text.insert(tk.END, f"Max Score Observed: {result['max_score']}\n")
        
        # Clear the tree
        for item in self.strategy_tree.get_children():
            self.strategy_tree.delete(item)
        
        # Add dice combinations to the tree
        for i, combo in enumerate(result.get('all_combinations', [])):
            self.strategy_tree.insert(
                "", "end", 
                values=(
                    combo.get("name", "Unknown"),
                    f"{combo.get('expected_value', 0):.2f}",
                    f"{combo.get('bust_rate', 0)*100:.1f}%",
                    f"{combo.get('avg_rolls', 0):.2f}",
                    f"{combo.get('rank_score', 0):.2f}"
                ),
                tags=(str(i),)
            )
        
        # Select the first item
        if self.strategy_tree.get_children():
            first_item = self.strategy_tree.get_children()[0]
            self.strategy_tree.selection_set(first_item)
            self.strategy_tree.focus(first_item)
            self.on_strategy_selected(None)  # Update details for first item
        
        # Re-enable the calculate button
        self.calculate_button.config(state="normal")
        
        # Update progress bar to complete
        self.progress_var.set(100)
        # Clear status label when done
        self.status_label_var.set("")
    
    def on_strategy_selected(self, event):
        """Handle selection of a dice combination from the treeview."""
        # Clear chart
        for widget in self.strategy_chart_frame.winfo_children():
            widget.destroy()
        
        selection = self.strategy_tree.selection()
        if not selection:
            return
        
        # Get selected item
        item = selection[0]
        tag = self.strategy_tree.item(item, "tags")[0]
        combo_idx = int(tag)
        
        # Get selected combination name
        combo_name = self.strategy_tree.item(item, "values")[0]
        
        try:
            # Get the latest simulation result from memory
            # We can try to rebuild this or just use existing chart data
            
            # Create chart for common scores
            fig, ax = plt.subplots(figsize=(4, 3))
            
            # Display a dice composition chart (even if we don't have probabilities)
            # Parse the dice composition from the combination name
            dice_composition = {}
            if "x" in combo_name and not combo_name.startswith("Random"):
                parts = combo_name.split("x", 1)
                if len(parts) == 2:
                    count = parts[0].strip()
                    name = parts[1].strip()
                    try:
                        dice_composition[name] = int(count)
                    except ValueError:
                        pass
            
            # If we have dice composition, show a pie chart of dice types
            if dice_composition:
                labels = list(dice_composition.keys())
                values = list(dice_composition.values())
                ax.pie(values, labels=labels, autopct='%1.1f%%')
                ax.set_title(f'Dice Composition for {combo_name}')
            else:
                # Otherwise show the name and a placeholder
                ax.text(0.5, 0.5, f"Selected: {combo_name}", 
                        ha='center', va='center', fontsize=12)
                ax.axis('off')
            
            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, master=self.strategy_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        
        except Exception as e:
            print(f"Error displaying combination details: {e}")
    
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
