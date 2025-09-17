"""
Kingdom Come: Deliverance 2 Dice Calculator
A calculator and information app for KCD 2 dice that allows users to:
- View each die and their description
- See weight and weight percentage information for dice
- Calculate the best combination of dice for desired outcomes
"""

import os
from datetime import datetime
import csv
import json
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
from collections import Counter
from typing import List, Dict, Optional, Set
import random

from dice_data import load_dice_data, get_die_by_name, get_all_dice_names, Die
from turn_simulator import find_optimal_dice_combination, DiceSimulator
from game_simulator import GameSimulator, AI_PROFILES

# Ensure dice data is loaded
ALL_DICE = load_dice_data()

# Constants
PADDING = 10
DICE_INVENTORY_FILE = "dice_inventory.json"


# Simple tooltip helper for Tkinter widgets
class _ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self._enter)
        self.widget.bind("<Leave>", self._leave)

    def _enter(self, _event=None):
        self._schedule()

    def _leave(self, _event=None):
        self._unschedule()
        self._hide()

    def _schedule(self):
        self._unschedule()
        self.id = self.widget.after(500, self._show)

    def _unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def _show(self):
        if self.tipwindow or not self.text:
            return
        # Position tooltip near the widget
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"), wraplength=320)
        label.pack(ipadx=5, ipady=3)

    def _hide(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


def add_tooltip(widget, text: str):
    """Attach a tooltip to a Tk widget."""
    _ToolTip(widget, text)

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
        self.single_combo_tab = ttk.Frame(self.tab_control)
        self.game_sim_tab = ttk.Frame(self.tab_control)
        self.playbook_tab = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.info_tab, text="Dice Information")
        self.tab_control.add(self.inventory_tab, text="Inventory")
        self.tab_control.add(self.calculator_tab, text="Target Calculator")
        self.tab_control.add(self.strategy_tab, text="Strategy Calculator (WIP)")
        self.tab_control.add(self.single_combo_tab, text="Single Combo Simulator")
        self.tab_control.add(self.game_sim_tab, text="Game Simulator (WIP)")
        self.tab_control.add(self.playbook_tab, text="Play Book")
        
        self.tab_control.pack(expand=1, fill="both")
        
        # Some methods may have been defined at module scope; bind them if needed
        try:
            _ = self.load_inventory
        except AttributeError:
            if 'load_inventory' in globals():
                # Bind module function as instance method
                self.load_inventory = globals()['load_inventory'].__get__(self, DiceCalculatorApp)
        try:
            _ = self.save_inventory
        except AttributeError:
            if 'save_inventory' in globals():
                self.save_inventory = globals()['save_inventory'].__get__(self, DiceCalculatorApp)

        # Initialize inventory data
        if hasattr(self, 'load_inventory'):
            self.inventory = self.load_inventory()
        else:
            self.inventory = {name: 0 for name in get_all_dice_names()}
        
        # Set up each tab
        self.setup_info_tab()
        self.setup_inventory_tab()
        self.setup_calculator_tab()
        self.setup_strategy_tab()
        self.setup_single_combo_tab()
        self.setup_game_sim_tab()
        self.setup_playbook_tab()
        # Shared state between tabs
        self.last_best_combo_names = None  # type: list[str] | None
    
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

    def setup_single_combo_tab(self):
        """Set up the Single Combo Simulator tab."""
        frame = ttk.Frame(self.single_combo_tab, padding=PADDING)
        frame.pack(fill="both", expand=True)

        # Top: consolidated settings area
        control_frame = ttk.LabelFrame(frame, text="Simulation & Banking Settings", padding=PADDING)
        control_frame.pack(fill="x", pady=(0, 10))
        row1 = ttk.Frame(control_frame)
        row1.pack(fill="x", pady=2)
        row2 = ttk.Frame(control_frame)
        row2.pack(fill="x", pady=2)
        row3 = ttk.Frame(control_frame)
        row3.pack(fill="x", pady=2)

        # Initialize control booleans used by checkbuttons
        # These were previously created in the old layout; we recreate them here explicitly
        if not hasattr(self, 'single_reset_on_refresh_var'):
            self.single_reset_on_refresh_var = tk.BooleanVar(value=True)
        if not hasattr(self, 'single_no_bank_on_clear_var'):
            self.single_no_bank_on_clear_var = tk.BooleanVar(value=True)
        if not hasattr(self, 'single_show_debug_var'):
            self.single_show_debug_var = tk.BooleanVar(value=True)

        # Row 1: Simulations, Win Target
        ttk.Label(row1, text="Simulations:").grid(row=0, column=0, sticky="e")
        self.single_sim_count_var = tk.StringVar(value="5000")
        self.single_sim_entry = ttk.Spinbox(row1, from_=100, to=1000000, increment=100,
                                            width=10, textvariable=self.single_sim_count_var)
        self.single_sim_entry.grid(row=0, column=1, sticky="w", padx=(5, 15))
        add_tooltip(self.single_sim_entry, "Number of Monte Carlo simulations to run for this combo. Higher = more accurate but slower.")

        ttk.Label(row1, text="Win Target:").grid(row=0, column=2, sticky="e")
        self.single_win_target_var = tk.StringVar(value="8000")
        self.single_win_target_entry = ttk.Spinbox(row1, from_=500, to=20000, increment=250,
                                                   width=10, textvariable=self.single_win_target_var)
        self.single_win_target_entry.grid(row=0, column=3, sticky="w", padx=(5, 15))
        add_tooltip(self.single_win_target_entry, "Game mode target score to win the game. The sim will stop the turn once this total is reached.")

        # Row 2: Banking rules (minimum bank)
        ttk.Label(row2, text="Minimum Bank Value:").grid(row=0, column=0, sticky="e")
        self.single_min_bank_var = tk.StringVar(value="500")
        self.single_min_bank_entry = ttk.Spinbox(row2, from_=0, to=10000, increment=50,
                                                 width=10, textvariable=self.single_min_bank_var)
        self.single_min_bank_entry.grid(row=0, column=1, sticky="w", padx=(5, 15))
        add_tooltip(self.single_min_bank_entry, "Minimum total required to be allowed to bank during the early rolls below.")

        ttk.Label(row2, text="Apply to first N rolls:").grid(row=0, column=2, sticky="e")
        self.single_min_bank_rolls_var = tk.StringVar(value="2")
        self.single_min_bank_rolls_entry = ttk.Spinbox(row2, from_=0, to=10, increment=1,
                                                       width=6, textvariable=self.single_min_bank_rolls_var)
        self.single_min_bank_rolls_entry.grid(row=0, column=3, sticky="w", padx=(5, 15))
        add_tooltip(self.single_min_bank_rolls_entry, "How many rolls the minimum bank rule applies to at the start of a turn (and after refresh if enabled).")

        apply_after_refresh_cb = ttk.Checkbutton(
            row2,
            text="Apply after refresh",
            variable=self.single_reset_on_refresh_var
        )
        apply_after_refresh_cb.grid(row=0, column=4, sticky="w", padx=(5, 15))
        add_tooltip(apply_after_refresh_cb, "When all dice are used and the set refreshes, restart the early-roll counter so the minimum bank rule applies again.")

        # Row 3: Behavior & diagnostics
        no_bank_on_clear_cb = ttk.Checkbutton(
            row3,
            text="Don't bank if all dice used",
            variable=self.single_no_bank_on_clear_var
        )
        no_bank_on_clear_cb.grid(row=0, column=0, sticky="w")
        add_tooltip(no_bank_on_clear_cb, "If a keep uses all dice, do not allow immediate banking; instead, refresh all dice and continue the turn.")

        ttk.Label(row3, text="Bank when X or fewer dice remain:").grid(row=0, column=1, sticky="e", padx=(15, 0))
        self.single_bank_if_dice_below_var = tk.StringVar(value="0")
        self.single_bank_if_dice_below_entry = ttk.Spinbox(row3, from_=0, to=5, increment=1,
                                                           width=6, textvariable=self.single_bank_if_dice_below_var)
        self.single_bank_if_dice_below_entry.grid(row=0, column=2, sticky="w", padx=(5, 15))
        add_tooltip(self.single_bank_if_dice_below_entry, "If a keep would leave X or fewer dice, bank immediately on that same roll. Set 0 to disable.")

        show_debug_cb = ttk.Checkbutton(
            row3,
            text="Show decision breakdown",
            variable=self.single_show_debug_var
        )
        show_debug_cb.grid(row=0, column=3, sticky="w", padx=(10, 0))
        add_tooltip(show_debug_cb, "Include a compact log of decisions taken during simulated turns.")

        # Inventory enforcement
        self.single_respect_inventory_var = tk.BooleanVar(value=False)
        respect_inventory_cb = ttk.Checkbutton(
            row3,
            text="Respect Inventory Quantities",
            variable=self.single_respect_inventory_var
        )
        respect_inventory_cb.grid(row=0, column=4, sticky="w", padx=(15, 0))
        add_tooltip(respect_inventory_cb, "If enabled, you can only select dice up to the quantities in your Inventory tab. If disabled, you can select any dice.")

        # Dice pickers section
        input_frame = ttk.LabelFrame(frame, text="Select Dice for Each Position (1-6)", padding=PADDING)
        input_frame.pack(fill="x", pady=(0, 10))

        # Dice selectors (1..6)
        ttk.Label(input_frame, text="Pick dice for each slot:").grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 5))
        names = sorted(get_all_dice_names())
        self.single_combo_vars = []
        self.single_combo_boxes = []
        row_base = 2
        for i in range(6):
            ttk.Label(input_frame, text=f"Die {i+1}:").grid(row=row_base + i, column=0, sticky="e", padx=(0, 10))
            var = tk.StringVar(value=names[0] if names else "")
            box = ttk.Combobox(input_frame, values=names, width=30, textvariable=var, state="readonly")
            box.grid(row=row_base + i, column=1, columnspan=2, sticky="w")
            self.single_combo_vars.append(var)
            self.single_combo_boxes.append(box)

        # Run button
        self.single_run_button = ttk.Button(frame, text="Run Single Combo Simulation", command=self.run_single_combo)
        self.single_run_button.pack(pady=10)

        # Send to Game Simulator (always enabled; validates selection on click)
        self.single_send_to_game_button = ttk.Button(frame, text="Send to Game Simulator",
                                                     command=self.send_to_game_from_single)
        self.single_send_to_game_button.pack(pady=(0, 10))
        add_tooltip(self.single_send_to_game_button, "Open the Game Simulator with these six dice as Player dice.")

        # Results
        results_frame = ttk.LabelFrame(frame, text="Single Combo Results", padding=PADDING)
        results_frame.pack(fill="both", expand=True)

        self.single_results_text = tk.Text(results_frame, height=10, wrap="word")
        self.single_results_text.pack(fill="both", expand=True)

        # Compact debug output box for decision breakdown
        debug_frame = ttk.LabelFrame(frame, text="Decision Breakdown (sample)", padding=PADDING)
        debug_frame.pack(fill="both", expand=False, pady=(5, 0))
        self.single_debug_text = tk.Text(debug_frame, height=8, wrap="word")
        self.single_debug_text.pack(fill="x", expand=False)

        # Progress for single combo
        self.single_progress_var = tk.DoubleVar(value=0)
        self.single_progress_bar = ttk.Progressbar(results_frame, variable=self.single_progress_var, mode="determinate")
        self.single_progress_bar.pack(fill="x", pady=(5, 0))

    def run_single_combo(self):
        """Validate inputs and start single combo simulation in a thread."""
        try:
            sim_count = int(self.single_sim_count_var.get())
            if sim_count < 100:
                sim_count = 100
                self.single_sim_count_var.set(str(sim_count))

            selected_names = [v.get() for v in self.single_combo_vars]
            if any(not n for n in selected_names):
                messagebox.showerror("Input Error", "Please select a die for all 6 positions.")
                return

            # Respect inventory quantities if requested
            if self.single_respect_inventory_var.get():
                counts = Counter(selected_names)
                for name, need in counts.items():
                    have = int(self.quantity_vars.get(name, tk.StringVar(value="0")).get()) if hasattr(self, 'quantity_vars') else 0
                    if need > have:
                        messagebox.showerror("Inventory Limit", f"Selected {need}x '{name}' but inventory has {have}.")
                        return

            # Build dice list
            dice_list = []
            for name in selected_names:
                die = get_die_by_name(name)
                if not die:
                    messagebox.showerror("Input Error", f"Unknown die: {name}")
                    return
                dice_list.append(die)

            # Disable run button and reset progress
            self.single_run_button.config(state="disabled")
            self.single_progress_var.set(0)
            self.single_results_text.delete(1.0, tk.END)
            self.single_results_text.insert(tk.END, "Running single combo simulation...\n")

            def worker():
                try:
                    simulator = DiceSimulator([], sim_count)
                    # Apply optional banking rule
                    try:
                        min_bank = int(self.single_min_bank_var.get())
                    except Exception:
                        min_bank = 0
                    try:
                        first_n = int(self.single_min_bank_rolls_var.get())
                    except Exception:
                        first_n = 0
                    if min_bank > 0 and first_n > 0:
                        simulator.bank_min_value = min_bank
                        simulator.bank_min_applies_first_n_rolls = first_n
                    # Apply no-bank-on-clear rule
                    simulator.no_bank_on_clear = bool(self.single_no_bank_on_clear_var.get())
                    # Apply reset-count-on-refresh rule
                    simulator.reset_count_on_refresh = bool(self.single_reset_on_refresh_var.get())
                    # Apply win target
                    try:
                        simulator.win_target = int(self.single_win_target_var.get())
                    except Exception:
                        simulator.win_target = 8000
                    # Apply bank-if-dice-below rule
                    try:
                        bank_if_below = int(self.single_bank_if_dice_below_var.get())
                        simulator.bank_if_dice_below = max(0, min(5, bank_if_below))  # Clamp between 0-5
                    except ValueError:
                        simulator.bank_if_dice_below = 0
                    # Use the same simulation function as strategy uses
                    stats = simulator.simulate_dice_combination(
                        dice_list,
                        sim_count,
                        None,
                        diagnostics=bool(self.single_show_debug_var.get())
                    )
                    self.root.after(0, lambda: self._update_single_combo_results(selected_names, stats))
                except Exception as e:
                    err_msg = str(e)
                    self.root.after(0, lambda msg=err_msg: [
                        messagebox.showerror("Simulation Error", msg),
                        self.single_run_button.config(state="normal")
                    ])

            threading.Thread(target=worker, daemon=True).start()
        except ValueError:
            messagebox.showerror("Input Error", "Please enter a valid number of simulations.")

    def _update_single_combo_results(self, selected_names, stats):
        """Render results from a single combo simulation."""
        self.single_results_text.delete(1.0, tk.END)
        self.single_results_text.insert(tk.END, f"Combination: {', '.join(selected_names)}\n")
        # Settings summary for reproducibility
        try:
            sim_count = int(self.single_sim_count_var.get())
        except Exception:
            sim_count = 0
        try:
            min_bank = int(self.single_min_bank_var.get())
        except Exception:
            min_bank = 0
        try:
            first_n = int(self.single_min_bank_rolls_var.get())
        except Exception:
            first_n = 0
        try:
            bank_if_below = int(self.single_bank_if_dice_below_var.get())
        except Exception:
            bank_if_below = 0
        try:
            win_target = int(self.single_win_target_var.get())
        except Exception:
            win_target = 8000
            
        if 'avg_score' in stats:
            self.single_results_text.insert(tk.END, f"Average Score Per Turn: {stats.get('avg_score', 0):.2f}\n")
        self.single_results_text.insert(tk.END, f"Expected Score: {stats.get('expected_value', 0):.2f}\n")
        self.single_results_text.insert(tk.END, f"Bust Rate: {stats.get('bust_rate', 0)*100:.2f}%\n")
        self.single_results_text.insert(tk.END, f"Average Rolls per Turn: {stats.get('avg_rolls', 0):.2f}\n")
        # Common scores (handle dict or list-of-pairs)
        common_raw = stats.get('common_scores', {})
        pairs = []
        if isinstance(common_raw, dict):
            pairs = list(common_raw.items())
        elif isinstance(common_raw, list):
            # Expect list of (score, prob) pairs
            pairs = [(p[0], p[1]) for p in common_raw if isinstance(p, (list, tuple)) and len(p) >= 2]
        if pairs:
            self.single_results_text.insert(tk.END, "\nCommon Scores (approx):\n")
            for score, prob in sorted(pairs, key=lambda x: x[1], reverse=True)[:5]:
                self.single_results_text.insert(tk.END, f"  {score}: {prob:.2f}%\n")
        # Top Scores by value
        top_pairs = stats.get('top_scores')
        if isinstance(top_pairs, list) and top_pairs:
            self.single_results_text.insert(tk.END, "\nTop Scores (by value):\n")
            for score, prob in top_pairs[:5]:
                self.single_results_text.insert(tk.END, f"  {score}: {prob:.2f}%\n")
        max_score = stats.get('max_score')
        if max_score is not None:
            self.single_results_text.insert(tk.END, f"\nMax Score Observed: {max_score}\n")

        self.single_results_text.insert(tk.END, "\n")

        self.single_results_text.insert(tk.END, "Settings Used:\n")
        self.single_results_text.insert(tk.END, f"  Simulations: {sim_count}\n")
        self.single_results_text.insert(tk.END, f"  Minimum Bank Value: {min_bank}\n")
        self.single_results_text.insert(tk.END, f"  Apply to first N rolls: {first_n}\n")
        self.single_results_text.insert(tk.END, f"  Win Target: {win_target}\n")
        self.single_results_text.insert(tk.END, f"  Apply after refresh: {'Yes' if self.single_reset_on_refresh_var.get() else 'No'}\n")
        self.single_results_text.insert(tk.END, f"  Don't bank if all dice used: {'Yes' if self.single_no_bank_on_clear_var.get() else 'No'}\n")
        self.single_results_text.insert(tk.END, f"  Bank when X or fewer dice remain: {bank_if_below}\n")

        self.single_progress_var.set(100)
        self.single_run_button.config(state="normal")

        # Update decision breakdown box (when diagnostics was enabled)
        self.single_debug_text.delete(1.0, tk.END)
        logs = stats.get('detailed_logs') if isinstance(stats, dict) else None
        if logs:
            # Show up to ~10 logs
            self.single_debug_text.insert(tk.END, "\n\n".join(logs))
        else:
            if self.single_show_debug_var.get():
                self.single_debug_text.insert(tk.END, "No decision breakdown available for this run.")

    def setup_game_sim_tab(self):
        """Set up the Game Simulator tab (Player vs AI full games to a point cap)."""
        frame = ttk.Frame(self.game_sim_tab, padding=PADDING)
        frame.pack(fill="both", expand=True)

        # Controls
        control = ttk.LabelFrame(frame, text="Simulation Settings", padding=PADDING)
        control.pack(fill="x", pady=(0, 10))

        # Row 1: AI profile, games, win target
        row1 = ttk.Frame(control)
        row1.pack(fill="x", pady=2)

        ttk.Label(row1, text="AI Profile:").grid(row=0, column=0, sticky="e")
        self.ai_profile_var = tk.StringVar(value=sorted(AI_PROFILES.keys())[0])
        self.ai_profile_box = ttk.Combobox(row1, values=sorted(AI_PROFILES.keys()), width=20,
                                           textvariable=self.ai_profile_var, state="disabled")
        self.ai_profile_box.grid(row=0, column=1, sticky="w", padx=(5, 15))
        add_tooltip(self.ai_profile_box, "Select the AI difficulty profile (no badges). See AI_BEHAVIOR.md for details.")

        ttk.Label(row1, text="Games:").grid(row=0, column=2, sticky="e")
        self.games_count_var = tk.StringVar(value="2000")
        self.games_count_entry = ttk.Spinbox(row1, from_=100, to=200000, increment=100,
                                             width=10, textvariable=self.games_count_var)
        self.games_count_entry.grid(row=0, column=3, sticky="w", padx=(5, 15))
        add_tooltip(self.games_count_entry, "Number of games to simulate. Higher = more accurate but slower.")

        ttk.Label(row1, text="Win Target:").grid(row=0, column=4, sticky="e")
        self.game_win_target_var = tk.StringVar(value="8000")
        self.game_win_target_entry = ttk.Spinbox(row1, from_=500, to=20000, increment=250,
                                                 width=10, textvariable=self.game_win_target_var)
        self.game_win_target_entry.grid(row=0, column=5, sticky="w", padx=(5, 15))
        add_tooltip(self.game_win_target_entry, "Game point cap to win.")

        # Player dice selection
        player_box = ttk.LabelFrame(frame, text="Player Dice (6)", padding=PADDING)
        player_box.pack(fill="x", pady=(0, 10))

        dice_names = sorted(get_all_dice_names())
        self.all_dice_names = dice_names
        self.player_combo_vars = []
        for i in range(6):
            ttk.Label(player_box, text=f"Die {i+1}:").grid(row=i, column=0, sticky="e", padx=(0, 10))
            var = tk.StringVar(value=dice_names[0] if dice_names else "")
            box = ttk.Combobox(player_box, values=dice_names, width=30, textvariable=var, state="readonly")
            box.grid(row=i, column=1, sticky="w")
            self.player_combo_vars.append(var)

        # AI dice selection
        ai_box = ttk.LabelFrame(frame, text="AI Dice (6)", padding=PADDING)
        ai_box.pack(fill="x", pady=(0, 10))
        self.ai_combo_vars = []
        for i in range(6):
            ttk.Label(ai_box, text=f"Die {i+1}:").grid(row=i, column=0, sticky="e", padx=(0, 10))
            var = tk.StringVar(value=dice_names[0] if dice_names else "")
            box = ttk.Combobox(ai_box, values=dice_names, width=30, textvariable=var, state="readonly")
            box.grid(row=i, column=1, sticky="w")
            self.ai_combo_vars.append(var)

        # Randomize AI dice button
        ttk.Button(ai_box, text="Randomize AI Dice", command=self.randomize_ai_dice).grid(
            row=6, column=0, columnspan=2, pady=(6, 0)
        )

        # Run button
        self.run_game_sim_btn = ttk.Button(frame, text="Run Game Simulation", command=self.run_game_simulation)
        self.run_game_sim_btn.pack(pady=10)

        # Send current Player dice to Play Book
        self.send_to_playbook_btn = ttk.Button(frame, text="Send to Play Book", command=self.send_to_playbook_from_game)
        self.send_to_playbook_btn.pack(pady=(0, 10))

        # Results area
        results_frame = ttk.LabelFrame(frame, text="Game Simulation Results", padding=PADDING)
        results_frame.pack(fill="both", expand=True)
        # Progress UI
        prog_row = ttk.Frame(results_frame)
        prog_row.pack(fill="x", pady=(0, 6))
        ttk.Label(prog_row, text="Progress:").pack(side="left")
        self.game_progress_var = tk.DoubleVar(value=0)
        self.game_progress_bar = ttk.Progressbar(prog_row, variable=self.game_progress_var, maximum=100)
        self.game_progress_bar.pack(side="left", fill="x", expand=True, padx=(6, 6))
        self.game_status_var = tk.StringVar(value="Idle")
        ttk.Label(prog_row, textvariable=self.game_status_var).pack(side="left")

        self.game_results_text = tk.Text(results_frame, height=18, wrap="word")
        self.game_results_text.pack(fill="both", expand=True)

    def setup_playbook_tab(self):
        """Set up the Play Book tab to assist with real-game rolls step-by-step."""
        frame = ttk.Frame(self.playbook_tab, padding=PADDING)
        frame.pack(fill="both", expand=True)

        # Controls row
        ctrl = ttk.Frame(frame)
        ctrl.pack(fill="x", pady=(0, 8))
        ttk.Button(ctrl, text="Load Player Dice from Game Simulator", command=self.load_playbook_from_game).pack(side="left")
        ttk.Button(ctrl, text="Reset Turn", command=self.playbook_reset_turn).pack(side="left", padx=(8, 0))
        ttk.Button(ctrl, text="Full Reset", command=self.playbook_full_reset).pack(side="left", padx=(8, 0))
        ttk.Label(ctrl, text="Game point limit:").pack(side="left", padx=(16, 4))
        self.playbook_game_limit_var = tk.StringVar(value="8000")
        self.playbook_game_limit_entry = ttk.Spinbox(ctrl, from_=500, to=20000, increment=250, width=8,
                                                     textvariable=self.playbook_game_limit_var)
        self.playbook_game_limit_entry.pack(side="left")

        # Player dice selection for Play Book
        dice_box = ttk.LabelFrame(frame, text="Player Dice (6) for this turn", padding=PADDING)
        dice_box.pack(fill="x", pady=(0, 8))
        names = sorted(get_all_dice_names())
        self.playbook_player_combo_vars: List[tk.StringVar] = []
        for i in range(6):
            ttk.Label(dice_box, text=f"Die {i+1}:").grid(row=i, column=0, sticky="e", padx=(0, 10))
            var = tk.StringVar(value=names[0] if names else "")
            box = ttk.Combobox(dice_box, values=names, width=30, textvariable=var, state="readonly")
            box.grid(row=i, column=1, sticky="w")
            self.playbook_player_combo_vars.append(var)

        # Current turn status
        status = ttk.LabelFrame(frame, text="Current Turn Status", padding=PADDING)
        status.pack(fill="x", pady=(0, 8))
        self.playbook_total_var = tk.StringVar(value="0")
        self.playbook_roll_var = tk.StringVar(value="1")
        self.playbook_dice_left_var = tk.StringVar(value="6")
        self.playbook_overall_score_var = tk.StringVar(value="0")
        ttk.Label(status, text="Total so far:").grid(row=0, column=0, sticky="e")
        ttk.Label(status, textvariable=self.playbook_total_var).grid(row=0, column=1, sticky="w", padx=(6, 20))
        ttk.Label(status, text="Roll #:").grid(row=0, column=2, sticky="e")
        ttk.Label(status, textvariable=self.playbook_roll_var).grid(row=0, column=3, sticky="w", padx=(6, 20))
        ttk.Label(status, text="Dice to roll:").grid(row=0, column=4, sticky="e")
        ttk.Label(status, textvariable=self.playbook_dice_left_var).grid(row=0, column=5, sticky="w", padx=(6, 20))
        ttk.Label(status, text="Overall score:").grid(row=0, column=6, sticky="e")
        ttk.Label(status, textvariable=self.playbook_overall_score_var).grid(row=0, column=7, sticky="w", padx=(6, 0))
        # Row 1: AI score input for win% optimizer
        ttk.Label(status, text="AI score:").grid(row=1, column=0, sticky="e", pady=(6, 0))
        self.playbook_ai_score_var = tk.StringVar(value="0")
        ttk.Spinbox(status, from_=0, to=20000, increment=100, width=8, textvariable=self.playbook_ai_score_var).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(6, 0))

        # Enter roll values
        roll_frame = ttk.LabelFrame(frame, text="Enter your current roll values (1-6)", padding=PADDING)
        roll_frame.pack(fill="x", pady=(0, 8))
        self.playbook_roll_frame = ttk.Frame(roll_frame)
        self.playbook_roll_frame.pack(fill="x")
        self.playbook_roll_vars: List[tk.StringVar] = []

        # Actions
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="Suggest Best Keep", command=self.playbook_suggest_best).pack(side="left")
        ttk.Button(actions, text="Apply Top Suggestion", command=self.playbook_apply_top).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Bank Now", command=self.playbook_bank_now).pack(side="left", padx=(8, 16))

        # Risk aversion control: penalty (points) per 100% bust probability
        ttk.Label(actions, text="Risk penalty:").pack(side="left")
        self.playbook_risk_penalty_var = tk.StringVar(value="400")
        self.playbook_risk_penalty = ttk.Spinbox(actions, from_=0, to=2000, increment=50, width=7,
                                                 textvariable=self.playbook_risk_penalty_var)
        self.playbook_risk_penalty.pack(side="left", padx=(4, 16))
        add_tooltip(self.playbook_risk_penalty, "Subtract this many points from EV for 100% bust risk (scaled by bust%). Higher = more risk-averse.")

        # Optimize by mode: Win% or EV
        ttk.Label(actions, text="Optimize:").pack(side="left")
        self.playbook_opt_mode_var = tk.StringVar(value="Win%")
        self.playbook_opt_mode = ttk.Combobox(actions, values=["Win%", "EV"], width=6, state="readonly",
                                              textvariable=self.playbook_opt_mode_var)
        self.playbook_opt_mode.pack(side="left", padx=(4, 16))

        # Fast vs Slow (accurate) toggle: Fast skips Monte Carlo and precise EV
        self.playbook_fast_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(actions, text="Fast (heuristic)", variable=self.playbook_fast_mode_var).pack(side="left", padx=(0, 16))

        # Buttons to apply any of the top 5 suggestions directly
        self.playbook_apply_btns = []
        for i in range(1, 6):
            btn = ttk.Button(actions, text=f"Apply #{i}", command=lambda idx=i: self.playbook_apply_index(idx-1))
            btn.pack(side="left", padx=(4, 0))
            self.playbook_apply_btns.append(btn)

        # Suggestions / log
        log_frame = ttk.LabelFrame(frame, text="Suggestions & Log", padding=PADDING)
        log_frame.pack(fill="both", expand=True)
        self.playbook_text = tk.Text(log_frame, height=16, wrap="word")
        self.playbook_text.pack(fill="both", expand=True)

        # Initialize state
        self.playbook_all_dice: List[Die] = []
        self.playbook_current_dice: List[Die] = []
        self.playbook_total_dice: int = 6
        self.playbook_current_total: int = 0
        self.playbook_roll_index: int = 1
        self.playbook_last_suggestion: Optional[tuple] = None
        self.playbook_last_options: Optional[List[Dict]] = None
        self.playbook_last_roll: Optional[List[int]] = None
        self._playbook_refresh_dice_from_selectors()
        self._playbook_render_roll_inputs()

    def _playbook_refresh_dice_from_selectors(self):
        names = [v.get() for v in self.playbook_player_combo_vars]
        dice = []
        for n in names:
            d = get_die_by_name(n)
            if d:
                dice.append(d)
        self.playbook_all_dice = dice
        if not self.playbook_current_dice:
            self.playbook_current_dice = list(dice)
        self.playbook_total_dice = max(1, len(dice)) if dice else 6
        self.playbook_dice_left_var.set(str(len(self.playbook_current_dice) if self.playbook_current_dice else self.playbook_total_dice))

    def _playbook_render_roll_inputs(self):
        # Clear existing inputs
        for child in list(self.playbook_roll_frame.winfo_children()):
            child.destroy()
        self.playbook_roll_vars.clear()
        n = len(self.playbook_current_dice) if self.playbook_current_dice else self.playbook_total_dice
        n = max(1, min(6, n))
        for i in range(n):
            # Label each input with the die's name if available, else generic
            die_name = None
            try:
                die_name = getattr(self.playbook_current_dice[i], 'name', None)
            except Exception:
                die_name = None
            label_text = die_name if die_name else f"Die {i+1}"
            ttk.Label(self.playbook_roll_frame, text=label_text).grid(row=0, column=i*2, sticky="e")
            # Default to 1 to avoid empty values causing parse errors
            var = tk.StringVar(value="1")
            spin = ttk.Spinbox(self.playbook_roll_frame, from_=1, to=6, width=4, textvariable=var)
            spin.grid(row=0, column=i*2+1, sticky="w", padx=(4, 10))
            self.playbook_roll_vars.append(var)

    def _playbook_player_settings(self) -> Dict[str, int | bool]:
        # Mirror Single Combo settings
        def _to_int(v, default=0):
            try:
                return int(v)
            except Exception:
                return default
        return {
            "bank_min_value": _to_int(self.single_min_bank_var.get(), 0) or None,
            "bank_min_applies_first_n_rolls": _to_int(self.single_min_bank_rolls_var.get(), 0) or None,
            "no_bank_on_clear": bool(self.single_no_bank_on_clear_var.get()),
            "reset_count_on_refresh": bool(self.single_reset_on_refresh_var.get()),
            "bank_if_dice_below": max(0, min(5, _to_int(self.single_bank_if_dice_below_var.get(), 0))),
            "win_target": _to_int(self.single_win_target_var.get(), 8000),
        }

    def playbook_reset_turn(self):
        self._playbook_refresh_dice_from_selectors()
        self.playbook_current_dice = list(self.playbook_all_dice)
        self.playbook_current_total = 0
        self.playbook_roll_index = 1
        self.playbook_total_var.set("0")
        self.playbook_roll_var.set("1")
        self.playbook_dice_left_var.set(str(len(self.playbook_current_dice)))
        self.playbook_text.delete(1.0, tk.END)
        self.playbook_text.insert(tk.END, "Play Book reset. Enter your first roll and click 'Suggest Best Keep'.\n")
        self._playbook_render_roll_inputs()

    def playbook_full_reset(self):
        """Reset overall score and the current turn state in the Play Book."""
        # Reset overall score
        self.playbook_overall_score_var.set("0")
        # Clear log and reset turn state
        try:
            self.playbook_text.delete(1.0, tk.END)
        except Exception:
            pass
        self.playbook_reset_turn()
        self.playbook_text.insert(tk.END, "Overall score reset to 0.\n")

    def playbook_suggest_best(self):
        # Parse roll values
        try:
            roll = [int(v.get()) for v in self.playbook_roll_vars]
        except Exception:
            messagebox.showerror("Input Error", "Please enter valid roll values (1-6) for all dice.")
            return
        if any(v < 1 or v > 6 for v in roll):
            messagebox.showerror("Input Error", "Roll values must be between 1 and 6.")
            return
        if not self.playbook_all_dice:
            self._playbook_refresh_dice_from_selectors()
        # Configure simulator
        settings = self._playbook_player_settings()
        sim = DiceSimulator(self.playbook_all_dice, num_simulations=0)
        sim.bank_min_value = settings.get("bank_min_value")
        sim.bank_min_applies_first_n_rolls = settings.get("bank_min_applies_first_n_rolls")
        sim.no_bank_on_clear = bool(settings.get("no_bank_on_clear", False))
        sim.reset_count_on_refresh = bool(settings.get("reset_count_on_refresh", False))
        sim.bank_if_dice_below = int(settings.get("bank_if_dice_below", 0))
        sim.win_target = int(settings.get("win_target", 8000))
        # Compute candidate options (heuristic-ranked), then refine EV with state-based Monte Carlo
        options = sim._find_optimal_choices(
            roll,
            self.playbook_total_dice,
            self.playbook_current_total,
            roll_index=self.playbook_roll_index + 1,
        )
        self.playbook_text.insert(tk.END, f"\nRoll #{self.playbook_roll_index}: {', '.join(map(str, roll))}\n")
        if not options:
            self.playbook_text.insert(tk.END, "No scoring options: BUST!\n")
            self.playbook_last_suggestion = None
            return

        # Evaluate a curated set of options with precise EV / Win%.
        # Take top-by-heuristic plus top-by-immediate-score to ensure strong-scoring sets are included.
        evaluated = []  # list of dicts with detailed info
        n_curr = len(self.playbook_current_dice) if self.playbook_current_dice else self.playbook_total_dice
        # Build compact dice labels for this roll (D1..Dn) and a short name map
        labels = [f"D{i+1}" for i in range(n_curr)]
        def _abbr(name: str, limit: int = 10) -> str:
            return name if len(name) <= limit else (name[:limit] + "…")
        name_map = []
        for i in range(min(n_curr, len(self.playbook_current_dice))):
            nm = getattr(self.playbook_current_dice[i], 'name', f'Die{i+1}')
            name_map.append(f"{labels[i]}={_abbr(nm)}")
        # Curate candidates: top 10 by heuristic ordering + top 10 by immediate score
        cand: list = []
        seen_keys = set()
        # Helper to add unique options based on kept indices and desc
        def _add_candidate(opt):
            kept_idx, sc, evh, desc = opt
            key = (tuple(sorted(list(kept_idx))), desc)
            if key not in seen_keys:
                seen_keys.add(key)
                cand.append(opt)
        for opt in options[:10]:
            _add_candidate(opt)
        opts_by_score = sorted(list(options), key=lambda x: x[1], reverse=True)[:10]
        for opt in opts_by_score:
            _add_candidate(opt)
        # Cap total candidates to avoid heavy compute
        if len(cand) > 25:
            cand = cand[:25]
        # Parse current overall and game limit for win-target banking
        try:
            overall_score = int(self.playbook_overall_score_var.get() or 0)
        except Exception:
            overall_score = 0
        try:
            game_limit = int(self.playbook_game_limit_var.get() or 8000)
        except Exception:
            game_limit = 8000

        # Fast mode skips GameSimulator usage
        fast_mode = bool(getattr(self, 'playbook_fast_mode_var', tk.BooleanVar(value=False)).get())
        if not fast_mode:
            # Prepare GameSimulator for win% estimates
            try:
                ai_names = [v.get() for v in getattr(self, 'ai_combo_vars', [])]
            except Exception:
                ai_names = []
            ai_dice = []
            if ai_names and all(ai_names):
                for name in ai_names:
                    d = get_die_by_name(name)
                    if d:
                        ai_dice.append(d)
            if not ai_dice:
                # Fallback to Ordinary dice if AI combo not set
                ord_die = get_die_by_name("Ordinary die")
                ai_dice = [ord_die] * 6 if ord_die else list(self.playbook_all_dice)
            try:
                game_limit = int(self.playbook_game_limit_var.get() or 8000)
            except Exception:
                game_limit = 8000
            # Build a game simulator with current settings
            gs = GameSimulator(
                player_dice=list(self.playbook_all_dice),
                ai_dice=ai_dice,
                win_target=game_limit,
                ai_profile=self.ai_profile_var.get() if hasattr(self, 'ai_profile_var') else 'priest',
                player_settings={
                    key: settings.get(key)
                    for key in [
                        "bank_min_value",
                        "bank_min_applies_first_n_rolls",
                        "no_bank_on_clear",
                        "reset_count_on_refresh",
                        "bank_if_dice_below",
                    ]
                },
            )

        for opt in cand:
            kept_idx, score, ev_heur, desc = opt
            bank_choice = (desc == "Bank after keep") or desc.startswith("Bank after keep (forced")
            # Default precise EV: bank -> just keep_score; continue -> keep_score + future EV
            precise_ev = float(score)
            bust_rate = 0.0
            future_added = 0.0

            # If banking now (after this keep) would reach or exceed the game limit, force a bank suggestion
            projected_total_if_bank = overall_score + self.playbook_current_total + int(score)
            if projected_total_if_bank >= game_limit:
                bank_choice = True
                desc = "Bank after keep (win target)"

            if not bank_choice:
                # Build remaining dice after keeping kept_idx (indices align with current_dice ordering)
                remaining_indices = [i for i in range(n_curr) if i not in kept_idx]
                remaining_indices = [i for i in remaining_indices if i < len(self.playbook_current_dice)]
                remaining_dice = [self.playbook_current_dice[i] for i in remaining_indices]
                if not fast_mode:
                    try:
                        res = sim.simulate_from_state(
                            remaining_dice,
                            start_total=self.playbook_current_total + int(score),
                            start_roll_index=self.playbook_roll_index + 1,
                            full_set_size=self.playbook_total_dice,
                            num_simulations=300,
                        )
                        future_added = float(res.get("avg_added", 0.0))
                        bust_rate = float(res.get("bust_rate", 0.0))
                        precise_ev = float(score) + future_added
                    except Exception:
                        # Fallback: use heuristic EV if simulate_from_state fails for any reason
                        precise_ev = float(score) + max(0.0, float(ev_heur) - float(score))
                else:
                    # Fast heuristic path: use heuristic EV as-is
                    precise_ev = float(ev_heur)

            kept_vals = [roll[j] for j in kept_idx]
            # Win probability estimation (skip in fast mode)
            if not fast_mode:
                try:
                    ai_total = int(self.playbook_ai_score_var.get() or 0)
                except Exception:
                    ai_total = 0
                if bank_choice:
                    # If banking reaches limit, certain win
                    if projected_total_if_bank >= game_limit:
                        win_prob = 1.0
                    else:
                        win_prob = gs.estimate_win_probability(
                            player_total=overall_score + self.playbook_current_total + int(score),
                            ai_total=ai_total,
                            next_actor="ai",
                            start_remaining_dice=None,
                            start_turn_total=0,
                            start_roll_index=1,
                            trials=200,
                        )
                else:
                    # Continue from current state
                    win_prob = gs.estimate_win_probability(
                        player_total=overall_score,
                        ai_total=ai_total,
                        next_actor="player",
                        start_remaining_dice=remaining_dice,
                        start_turn_total=self.playbook_current_total + int(score),
                        start_roll_index=self.playbook_roll_index + 1,
                        trials=200,
                    )
            else:
                win_prob = 0.0

            evaluated.append({
                "kept_idx": kept_idx,
                "score": int(score),
                "desc": desc,
                "kept_vals": kept_vals,
                "ev_precise": precise_ev,
                "bust_rate": bust_rate,
                "future_added": future_added,
                "win_prob": float(win_prob),
                # store updated desc in opt clone for apply path
                "opt": (kept_idx, score, ev_heur, desc),
            })

        # Risk-aware ranking: EV - risk_penalty * bust_rate
        try:
            risk_penalty = float(self.playbook_risk_penalty_var.get())
        except Exception:
            risk_penalty = 0.0
        for info in evaluated:
            # EV-based rank
            ev_rank = float(info["ev_precise"]) - risk_penalty * float(info["bust_rate"])  # bust_rate is 0..1
            info["ev_rank"] = ev_rank
            # Win% based rank
            info["wp_rank"] = float(info.get("win_prob", 0.0))
            # Win-target banking should always be preferred over continuing
            desc_txt = str(info.get("desc", ""))
            info["win_flag"] = 1 if "win target" in desc_txt else 0
        # Sort by selected mode
        mode = (self.playbook_opt_mode_var.get() or "Win%").strip()
        if fast_mode:
            mode = "EV"
        if mode == "Win%":
            evaluated.sort(key=lambda x: (x["win_flag"], x["wp_rank"]), reverse=True)
        else:
            evaluated.sort(key=lambda x: (x["win_flag"], x["ev_rank"]), reverse=True)
        best = evaluated[0]
        self.playbook_last_suggestion = (best["opt"], roll)
        self.playbook_last_options = evaluated
        self.playbook_last_roll = list(roll)

        # Render suggestions
        if name_map:
            self.playbook_text.insert(tk.END, "Dice map: " + ", ".join(name_map) + "\n")
        self.playbook_text.insert(tk.END, "Top suggestions (risk-adjusted):\n")
        for i, info in enumerate(evaluated[:5], start=1):
            kept_idx = info["kept_idx"]
            # kept_idx may be a set; sort indices to safely index labels/roll
            idx_list = sorted(list(kept_idx))
            kept_display = [f"{roll[j]}({labels[j]})" for j in idx_list]
            score = info["score"]
            desc = info["desc"]
            evp = info["ev_precise"]
            add_future = info["future_added"]
            bust = info["bust_rate"] * 100.0
            winp = info.get("win_prob", 0.0) * 100.0
            rank_score = info.get("ev_rank", evp)
            if (
                desc == "Bank after keep"
                or desc.startswith("Bank after keep (forced")
                or desc.startswith("Bank after keep (win target")
            ):
                if mode == "Win%":
                    self.playbook_text.insert(tk.END, f"  {i}. Keep {kept_display} for {score} pts -> BANK, win {winp:.1f}%\n")
                else:
                    self.playbook_text.insert(tk.END, f"  {i}. Keep {kept_display} for {score} pts -> BANK, EV {evp:.1f}, win {winp:.1f}%, score {rank_score:.1f}\n")
            else:
                if mode == "Win%":
                    self.playbook_text.insert(tk.END, f"  {i}. Keep {kept_display} for {score} pts -> CONT, win {winp:.1f}%, bust {bust:.1f}%\n")
                else:
                    self.playbook_text.insert(tk.END, f"  {i}. Keep {kept_display} for {score} pts -> CONT, future +{add_future:.1f}, EV {evp:.1f}, win {winp:.1f}%, bust {bust:.1f}%, score {rank_score:.1f}\n")
        self.playbook_text.see(tk.END)

    def playbook_apply_top(self):
        if not self.playbook_last_suggestion:
            messagebox.showwarning("No Suggestion", "Click 'Suggest Best Keep' first.")
            return
        (best_opt, roll) = self.playbook_last_suggestion
        kept_idx, score, _ev, desc = best_opt
        kept_vals = [roll[j] for j in kept_idx]
        self.playbook_current_total += int(score)
        self.playbook_text.insert(tk.END, f"Applied: kept {kept_vals} (+{score}). Total = {self.playbook_current_total}. {desc}\n")
        # Determine banking
        bank = (desc == "Bank after keep") or desc.startswith("Bank after keep (forced") or desc.startswith("Bank after keep (win target")
        # Update current dice by removing kept indices from current roll mapping
        n = len(self.playbook_current_dice) if self.playbook_current_dice else self.playbook_total_dice
        remaining_indices = [i for i in range(n) if i not in kept_idx]
        # If n might mismatch, clamp
        remaining_indices = [i for i in remaining_indices if i < len(self.playbook_current_dice)]
        self.playbook_current_dice = [self.playbook_current_dice[i] for i in remaining_indices]
        # Handle bank
        if bank:
            self.playbook_text.insert(tk.END, f"Decision: BANK NOW at {self.playbook_current_total} points. Turn ends.\n")
            self.playbook_total_var.set(str(self.playbook_current_total))
            # Add to overall score
            try:
                overall = int(self.playbook_overall_score_var.get() or 0)
            except Exception:
                overall = 0
            overall += int(self.playbook_current_total)
            self.playbook_overall_score_var.set(str(overall))
            # Notify if reaching limit
            try:
                limit = int(self.playbook_game_limit_var.get() or 8000)
            except Exception:
                limit = 8000
            if overall >= limit:
                self.playbook_text.insert(tk.END, f"Reached or exceeded game limit ({limit}).\n")
            # Typically start a new turn after bank; keep state but reset for next turn
            self.playbook_current_total = 0
            self.playbook_roll_index = 1
            self.playbook_current_dice = list(self.playbook_all_dice)
            self.playbook_dice_left_var.set(str(len(self.playbook_current_dice)))
            self._playbook_render_roll_inputs()
            self.playbook_text.insert(tk.END, "-- New turn started. Enter next roll. --\n")
            self.playbook_text.see(tk.END)
            return
        # If all dice used, refresh and maybe reset roll counter
        if not self.playbook_current_dice:
            self.playbook_text.insert(tk.END, f"Used all dice -> refresh full set. Current total: {self.playbook_current_total}.\n")
            self.playbook_current_dice = list(self.playbook_all_dice)
            if bool(self.single_reset_on_refresh_var.get()):
                self.playbook_roll_index = 0  # will increment to 1 below
        # Advance to next roll
        self.playbook_roll_index += 1
        self.playbook_total_var.set(str(self.playbook_current_total))
        self.playbook_roll_var.set(str(self.playbook_roll_index))
        self.playbook_dice_left_var.set(str(len(self.playbook_current_dice)))
        self._playbook_render_roll_inputs()
        self.playbook_text.insert(tk.END, "Enter next roll values and suggest again.\n")
        self.playbook_text.see(tk.END)

    def playbook_apply_index(self, index: int):
        """Apply a specific option from the last evaluated list (0-based index)."""
        opts = self.playbook_last_options
        if not opts or index < 0 or index >= len(opts):
            messagebox.showwarning("No Suggestion", "No evaluated options available. Click 'Suggest Best Keep' first.")
            return
        info = opts[index]
        # Use the last evaluated roll if available
        roll = self.playbook_last_roll
        if roll is None:
            try:
                roll = [int(v.get()) for v in self.playbook_roll_vars]
            except Exception:
                roll = []
        self.playbook_last_suggestion = (info["opt"], roll)
        # Reuse the same apply path
        self.playbook_apply_top()

    def playbook_bank_now(self):
        self.playbook_text.insert(tk.END, f"Manual decision: BANK NOW at {self.playbook_current_total} points. Turn ends.\n")
        self.playbook_total_var.set(str(self.playbook_current_total))
        # Add to overall
        try:
            overall = int(self.playbook_overall_score_var.get() or 0)
        except Exception:
            overall = 0
        overall += int(self.playbook_current_total)
        self.playbook_overall_score_var.set(str(overall))
        try:
            limit = int(self.playbook_game_limit_var.get() or 8000)
        except Exception:
            limit = 8000
        if overall >= limit:
            self.playbook_text.insert(tk.END, f"Reached or exceeded game limit ({limit}).\n")
        # Reset for next turn
        self.playbook_current_total = 0
        self.playbook_roll_index = 1
        self.playbook_current_dice = list(self.playbook_all_dice)
        self.playbook_dice_left_var.set(str(len(self.playbook_current_dice)))
        self._playbook_render_roll_inputs()
        self.playbook_text.insert(tk.END, "-- New turn started. Enter next roll. --\n")
        self.playbook_text.see(tk.END)

    def send_to_playbook_from_game(self):
        names = [v.get() for v in getattr(self, 'player_combo_vars', [])]
        if any(not n for n in names):
            messagebox.showerror("Input Error", "Please select all 6 Player dice in Game Simulator first.")
            return
        self._playbook_set_dice_names(names)
        try:
            self.tab_control.select(self.playbook_tab)
        except Exception:
            pass

    def load_playbook_from_game(self):
        self.send_to_playbook_from_game()

    def _playbook_set_dice_names(self, names: List[str]):
        all_names = set(get_all_dice_names())
        for i, name in enumerate(names):
            if name in all_names and i < len(self.playbook_player_combo_vars):
                self.playbook_player_combo_vars[i].set(name)
        # Refresh state
        self.playbook_reset_turn()

    def randomize_ai_dice(self):
        """Randomly assign AI dice from the full dice list (duplicates allowed)."""
        names = getattr(self, 'all_dice_names', None) or sorted(get_all_dice_names())
        if not names:
            messagebox.showerror("Randomize Error", "No dice available to randomize.")
            return
        for var in getattr(self, 'ai_combo_vars', []):
            var.set(random.choice(names))

    def run_game_simulation(self):
        """Start the game simulation in a background thread."""
        try:
            n_games = int(self.games_count_var.get())
            n_games = max(100, n_games)
        except Exception:
            n_games = 1000
            self.games_count_var.set(str(n_games))

        try:
            win_target = int(self.game_win_target_var.get())
        except Exception:
            win_target = 8000
            self.game_win_target_var.set(str(win_target))

        # Build dice lists
        player_names = [v.get() for v in self.player_combo_vars]
        ai_names = [v.get() for v in self.ai_combo_vars]

        if any(not n for n in player_names) or any(not n for n in ai_names):
            messagebox.showerror("Input Error", "Please select a die for all 6 positions for both Player and AI.")
            return

        player_dice = []
        ai_dice = []
        for name in player_names:
            d = get_die_by_name(name)
            if not d:
                messagebox.showerror("Input Error", f"Unknown player die: {name}")
                return
            player_dice.append(d)
        for name in ai_names:
            d = get_die_by_name(name)
            if not d:
                messagebox.showerror("Input Error", f"Unknown AI die: {name}")
                return
            ai_dice.append(d)

        profile = self.ai_profile_var.get()
        if profile not in AI_PROFILES:
            profile = "priest"
            try:
                self.ai_profile_var.set("priest")
            except Exception:
                pass

        # Disable button and clear results
        self.run_game_sim_btn.config(state="disabled")
        self.game_results_text.delete(1.0, tk.END)
        self.game_results_text.insert(tk.END, "Running game simulations...\n")
        self.game_progress_var.set(0)
        self.game_status_var.set("0%")

        def worker():
            try:
                # Build player settings from Single Combo tab
                player_settings = {
                    "bank_min_value": int(self.single_min_bank_var.get() or 0) or None,
                    "bank_min_applies_first_n_rolls": int(self.single_min_bank_rolls_var.get() or 0) or None,
                    "no_bank_on_clear": bool(self.single_no_bank_on_clear_var.get()),
                    "reset_count_on_refresh": bool(self.single_reset_on_refresh_var.get()),
                    "bank_if_dice_below": max(0, min(5, int(self.single_bank_if_dice_below_var.get() or 0))),
                }

                sim = GameSimulator(
                    player_dice,
                    ai_dice,
                    win_target=win_target,
                    ai_profile=profile,
                    player_settings=player_settings,
                )

                def progress(done: int, total: int):
                    pct = 0 if total <= 0 else (done / total) * 100.0
                    self.root.after(0, lambda p=pct, d=done, t=total: [
                        self.game_progress_var.set(p),
                        self.game_status_var.set(f"{d}/{t} ({p:.1f}%)")
                    ])

                stats = sim.simulate_games(n_games=n_games, progress_fn=progress)
                self.root.after(0, lambda: self._update_game_sim_results(player_names, ai_names, stats))
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda msg=err_msg: [
                    messagebox.showerror("Simulation Error", msg),
                    self.run_game_sim_btn.config(state="normal")
                ])

        threading.Thread(target=worker, daemon=True).start()

    def _update_game_sim_results(self, player_names: List[str], ai_names: List[str], stats: Dict):
        """Render results from the full game simulation."""
        self.game_results_text.delete(1.0, tk.END)
        self.game_results_text.insert(tk.END, f"Player dice: {', '.join(player_names)}\n")
        self.game_results_text.insert(tk.END, f"AI dice: {', '.join(ai_names)}\n")
        self.game_results_text.insert(tk.END, f"AI profile: {stats.get('ai_profile')}\n")
        self.game_results_text.insert(tk.END, f"Win target: {stats.get('win_target')}\n")
        self.game_results_text.insert(tk.END, f"Games: {stats.get('games')}\n\n")

        self.game_results_text.insert(tk.END, f"Player Win%: {stats.get('player_win_rate', 0.0)*100:.2f}%\n")
        self.game_results_text.insert(tk.END, f"AI Win%: {stats.get('ai_win_rate', 0.0)*100:.2f}%\n")
        self.game_results_text.insert(tk.END, f"Average turns per game: {stats.get('avg_turns', 0.0):.2f}\n")
        self.game_results_text.insert(tk.END, f"Average margin (Player - AI): {stats.get('avg_margin', 0.0):.2f}\n")

        length_dist = stats.get('length_distribution', {})
        if isinstance(length_dist, dict) and length_dist:
            self.game_results_text.insert(tk.END, "\nGame length distribution (turns => %):\n")
            for k, v in sorted(length_dist.items(), key=lambda x: x[0])[:10]:
                self.game_results_text.insert(tk.END, f"  {k}: {v:.2f}%\n")

        # Example detailed logs
        ex_win = stats.get('example_player_win')
        ex_loss = stats.get('example_player_loss')
        if ex_win:
            self.game_results_text.insert(tk.END, "\nExample game (Player WIN):\n")
            self.game_results_text.insert(tk.END, ex_win + "\n")
        if ex_loss:
            self.game_results_text.insert(tk.END, "\nExample game (Player LOSS):\n")
            self.game_results_text.insert(tk.END, ex_loss + "\n")

        self.game_results_text.insert(tk.END, f"\nElapsed: {stats.get('elapsed_sec', 0.0):.2f}s\n")

        self.run_game_sim_btn.config(state="normal")
        self.game_status_var.set("Done")
        self.game_progress_var.set(100)
    
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
        calc_btn = ttk.Button(
            input_frame, 
            text="Calculate Best Combination", 
            command=self.calculate_best_combination
        )
        calc_btn.grid(row=2, column=0, pady=10, sticky="w")
        add_tooltip(calc_btn, "Compute the best die for each position given your targets.")

        # Send to Single Combo Simulator button (disabled until a result exists)
        self.send_to_single_button = ttk.Button(
            input_frame,
            text="Send to Single Combo Simulator",
            command=self.send_to_single_combo,
            state="disabled"
        )
        self.send_to_single_button.grid(row=2, column=1, pady=10, sticky="w", padx=(10, 0))
        add_tooltip(self.send_to_single_button, "Open the Single Combo Simulator with the best dice pre-selected.")
        
        # Send to Game Simulator button (disabled until a result exists)
        self.send_to_game_button = ttk.Button(
            input_frame,
            text="Send to Game Simulator",
            command=self.send_to_game_from_calculator,
            state="disabled"
        )
        self.send_to_game_button.grid(row=2, column=2, pady=10, sticky="w", padx=(10, 0))
        add_tooltip(self.send_to_game_button, "Open the Game Simulator with the best dice pre-filled as Player dice.")
        
        # Bottom frame for results
        results_frame = ttk.LabelFrame(frame, text="Results", padding=PADDING)
        results_frame.pack(fill="both", expand=True)
        
        # Add text area for results (Target Calculator)
        self.target_results_text = tk.Text(results_frame, height=10, wrap="word")
        self.target_results_text.pack(fill="both", expand=True, pady=(0, 10))
        
        # Frame for the probability chart
        self.result_chart_frame = ttk.Frame(results_frame)
        self.result_chart_frame.pack(fill="both", expand=True)
    
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
            
            # Save for cross-tab sending and enable button
            try:
                ordered = [best_combo[pos][0].name for pos in sorted(best_combo.keys())]
                self.last_best_combo_names = ordered
                self.send_to_single_button.config(state="normal")
                # Also enable send-to-game
                if hasattr(self, 'send_to_game_button'):
                    self.send_to_game_button.config(state="normal")
            except Exception:
                pass
        
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))

    def send_to_single_combo(self):
        """Open Single Combo tab with the last best combo pre-selected in dropdowns."""
        if not self.last_best_combo_names or len(self.last_best_combo_names) != 6:
            messagebox.showwarning("No Combination", "Please calculate a best combination first.")
            return
        # Switch tab first
        try:
            self.tab_control.select(self.single_combo_tab)
        except Exception:
            pass
        # Apply names to the 6 selectors, if present in the list of dice
        names = set(get_all_dice_names())
        for i, name in enumerate(self.last_best_combo_names):
            if i < len(self.single_combo_vars) and name in names:
                self.single_combo_vars[i].set(name)
                try:
                    self.single_combo_boxes[i].set(name)
                except Exception:
                    pass
    
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
            # Collect names in position order for later sending
            best_names = []
            for position, (die, target_num, probability) in best_combo.items():
                self.target_results_text.insert(tk.END, 
                    f"Die position {position}: {die.name} - {probability:.2f}% chance of rolling a {target_num}\n")
                total_probability *= (probability / 100.0)
                best_names.append(die.name)
            
            # Overall probability (multiply individual probabilities)
            overall_percent = total_probability * 100.0
            self.target_results_text.insert(tk.END, 
                f"\nOverall probability of getting all target numbers: {overall_percent:.4f}%\n")
            
            # Update chart with results
            self.update_results_chart_for_positions(best_combo)
            # Save for cross-tab sending and enable button
            # Ensure order is Die 1..6; best_combo keys are positions
            ordered = [best_combo[pos][0].name for pos in sorted(best_combo.keys())]
            self.last_best_combo_names = ordered
            self.send_to_single_button.config(state="normal")
            
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))

    def send_to_single_combo(self):
        """Open Single Combo tab with the last best combo pre-selected in dropdowns."""
        if not self.last_best_combo_names or len(self.last_best_combo_names) != 6:
            messagebox.showwarning("No Combination", "Please calculate a best combination first.")
            return
        # Switch tab first
        try:
            self.tab_control.select(self.single_combo_tab)
        except Exception:
            pass
        # Apply names to the 6 selectors, if present in the list of dice
        names = set(get_all_dice_names())
        for i, name in enumerate(self.last_best_combo_names):
            if i < len(self.single_combo_vars):
                # Only set if the name exists in data
                if name in names:
                    self.single_combo_vars[i].set(name)
                    # Also update the combobox displayed value
                    try:
                        self.single_combo_boxes[i].set(name)
                    except Exception:
                        pass

    def _apply_player_dice_to_game(self, names: List[str]):
        """Helper: apply a list of 6 dice names to the Game Simulator's Player dice selectors."""
        if not hasattr(self, 'player_combo_vars') or len(getattr(self, 'player_combo_vars', [])) < 6:
            messagebox.showerror("Game Simulator", "Player selectors are not initialized.")
            return False
        all_names = set(get_all_dice_names())
        if len(names) != 6 or any(n not in all_names for n in names):
            messagebox.showerror("Game Simulator", "Invalid or incomplete set of 6 dice names.")
            return False
        for i, n in enumerate(names):
            try:
                self.player_combo_vars[i].set(n)
            except Exception:
                pass
        return True

    def send_to_game_from_calculator(self):
        """Open Game Simulator tab with best-combination dice filled as Player dice."""
        if not self.last_best_combo_names or len(self.last_best_combo_names) != 6:
            messagebox.showwarning("No Combination", "Please calculate a best combination first.")
            return
        if self._apply_player_dice_to_game(self.last_best_combo_names):
            try:
                self.tab_control.select(self.game_sim_tab)
            except Exception:
                pass

    def send_to_game_from_single(self):
        """Open Game Simulator tab using the current Single Combo selection as Player dice."""
        names = [v.get() for v in getattr(self, 'single_combo_vars', [])]
        if any(not n for n in names) or len(names) != 6:
            messagebox.showerror("Input Error", "Please select a die for all 6 positions in Single Combo.")
            return
        if self._apply_player_dice_to_game(names):
            try:
                self.tab_control.select(self.game_sim_tab)
            except Exception:
                pass
    
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
        strategies_frame = ttk.Frame(frame)
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
            err_msg = str(e)
            self.root.after(0, lambda msg=err_msg: messagebox.showerror("Simulation Error", msg))
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
        if 'avg_score' in result:
            self.strategy_results_text.insert(tk.END, f"Average Score Per Turn: {result['avg_score']:.2f}\n")
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
        
        # Save top 100 combinations to a timestamped text file and CSV (Top100- prefix) in app directory
        try:
            combos = result.get("all_combinations", [])
            if combos:
                top = combos[:100]
                lines = []
                lines.append("KCD2 Dice Calculator - Top 100 Combinations\n")
                lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                for i, item in enumerate(top, start=1):
                    name = item.get("name", "<unknown>")
                    avg = item.get("avg_score", 0.0)
                    ev = item.get("expected_value", 0.0)
                    bust = item.get("bust_rate", 0.0)
                    avg_rolls = item.get("avg_rolls", 0.0)
                    rank = item.get("rank_score", 0.0)
                    comp = item.get("dice_combination", {})
                    comp_str = ", ".join(f"{v}x {k}" for k, v in comp.items()) if isinstance(comp, dict) else str(comp)
                    lines.append(f"{i:3d}. {name}\n")
                    lines.append(f"     Avg/Turn: {avg:.2f} | EV: {ev:.2f} | Bust: {bust:.2%} | Avg Rolls: {avg_rolls:.2f} | Rank: {rank:.3f}\n")
                    lines.append(f"     Composition: {comp_str}\n\n")

                base_dir = os.path.dirname(os.path.abspath(__file__))
                filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
                out_path = os.path.join(base_dir, filename)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                
                # Write CSV with Top100- prefix
                csv_name = "Top100-" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".csv"
                csv_path = os.path.join(base_dir, csv_name)
                with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["rank", "name", "avg_score", "expected_value", "bust_rate", "avg_rolls", "rank_score", "composition"])
                    for i, item in enumerate(top, start=1):
                        name = item.get("name", "<unknown>")
                        avg = item.get("avg_score", 0.0)
                        ev = item.get("expected_value", 0.0)
                        bust = item.get("bust_rate", 0.0)
                        avg_rolls = item.get("avg_rolls", 0.0)
                        rank = item.get("rank_score", 0.0)
                        comp = item.get("dice_combination", {})
                        comp_str = ", ".join(f"{v}x {k}" for k, v in comp.items()) if isinstance(comp, dict) else str(comp)
                        writer.writerow([i, name, f"{avg:.4f}", f"{ev:.4f}", f"{bust:.4f}", f"{avg_rolls:.4f}", f"{rank:.4f}", comp_str])
                # Let the user know where it was saved
                self.strategy_results_text.insert(tk.END, f"\nSaved top 100 combinations to: {out_path}\n")
                self.strategy_results_text.insert(tk.END, f"Saved CSV: {csv_path}\n")
        except Exception as e:
            # Non-fatal; continue updating UI
            self.strategy_results_text.insert(tk.END, f"\nWarning: could not save results file ({e})\n")

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
