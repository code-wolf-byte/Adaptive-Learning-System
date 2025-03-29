import math
import numpy as np
from datetime import datetime, timedelta
from copy import deepcopy
from bkt.engine import BKTEngine

class IBKTEngine(BKTEngine):
    """
    Individualized Bayesian Knowledge Tracing (IBKT) engine.
    Extends BKT by learning personalized parameters for each student.
    """
    def __init__(self, p_init=0.2, p_transit=0.3, p_slip=0.1, p_guess=0.1, p_lapse=0.3,
                 param_history=None, response_count=0):
        super().__init__(p_init, p_transit, p_slip, p_guess, p_lapse)
        
        # Initialize parameter history if none provided
        self.param_history = param_history or {
            'responses': [],  # List of (question_id, is_correct) tuples
            'p_transit_history': [],  # History of p_transit values
            'p_slip_history': [],  # History of p_slip values
            'p_guess_history': []  # History of p_guess values
        }
        
        self.response_count = response_count
        self.update_frequency = 5  # Update parameters every 5 responses
        self.min_responses_for_update = 10  # Need at least 10 responses before updating
        
        # Learning rates for parameter updates
        self.lr_transit = 0.05
        self.lr_slip = 0.05
        self.lr_guess = 0.05
        
        # Bounds for parameters
        self.param_bounds = {
            'p_transit': (0.05, 0.5),
            'p_slip': (0.05, 0.3),
            'p_guess': (0.05, 0.3)
        }
    
    def add_response(self, question_id, is_correct):
        """
        Add a response to the history and update parameters if needed.
        
        Args:
            question_id: Identifier for the question
            is_correct: Whether the response was correct
        """
        # Add response to history
        self.param_history['responses'].append((question_id, is_correct))
        self.response_count += 1
        
        # Store current parameters in history
        self.param_history['p_transit_history'].append(self.p_transit)
        self.param_history['p_slip_history'].append(self.p_slip)
        self.param_history['p_guess_history'].append(self.p_guess)
        
        # Check if we should update parameters
        if (self.response_count >= self.min_responses_for_update and
                self.response_count % self.update_frequency == 0):
            self._update_parameters()
    
    def _update_parameters(self):
        """Update model parameters based on response history using EM-inspired approach."""
        # Calculate performance metrics
        responses = self.param_history['responses']
        recent_responses = responses[-20:] if len(responses) > 20 else responses
        
        # Calculate recent performance
        recent_correct = sum(1 for _, is_correct in recent_responses if is_correct)
        recent_total = len(recent_responses)
        recent_performance = recent_correct / recent_total if recent_total > 0 else 0.5
        
        # Calculate error rates and transition patterns
        transition_evidence = self._calculate_transition_evidence(recent_responses)
        slip_evidence = self._calculate_slip_evidence(recent_responses)
        guess_evidence = self._calculate_guess_evidence(recent_responses)
        
        # Update transition probability
        target_p_transit = min(max(transition_evidence, 
                                  self.param_bounds['p_transit'][0]), 
                              self.param_bounds['p_transit'][1])
        self.p_transit += self.lr_transit * (target_p_transit - self.p_transit)
        
        # Update slip probability
        target_p_slip = min(max(slip_evidence, 
                                self.param_bounds['p_slip'][0]), 
                            self.param_bounds['p_slip'][1])
        self.p_slip += self.lr_slip * (target_p_slip - self.p_slip)
        
        # Update guess probability
        target_p_guess = min(max(guess_evidence, 
                                 self.param_bounds['p_guess'][0]), 
                             self.param_bounds['p_guess'][1])
        self.p_guess += self.lr_guess * (target_p_guess - self.p_guess)
    
    def _calculate_transition_evidence(self, responses):
        """Estimate transition probability from response patterns."""
        if len(responses) < 3:
            return self.p_transit
        
        # Look for patterns of incorrect followed by correct
        transitions = 0
        opportunities = 0
        
        for i in range(len(responses) - 1):
            # Check for same question repeated or evidence of learning
            if responses[i][0] == responses[i+1][0]:  # Same question
                if not responses[i][1] and responses[i+1][1]:  # Incorrect -> Correct
                    transitions += 1
                opportunities += 1
        
        # Calculate transition rate with smoothing
        alpha = 1.0  # Smoothing factor
        return (transitions + alpha) / (opportunities + 2 * alpha) if opportunities > 0 else self.p_transit
    
    def _calculate_slip_evidence(self, responses):
        """Estimate slip probability from response patterns."""
        correct_to_incorrect = 0
        correct_total = 0
        
        # Group responses by question
        question_responses = {}
        for q_id, is_correct in responses:
            if q_id not in question_responses:
                question_responses[q_id] = []
            question_responses[q_id].append(is_correct)
        
        # Look for slips (correct followed by incorrect on same question)
        for q_id, results in question_responses.items():
            if len(results) < 2:
                continue
                
            for i in range(len(results) - 1):
                if results[i]:  # If correct
                    correct_total += 1
                    if not results[i+1]:  # But next attempt incorrect
                        correct_to_incorrect += 1
        
        # Calculate slip rate with smoothing
        alpha = 1.0
        return (correct_to_incorrect + alpha) / (correct_total + 2 * alpha) if correct_total > 0 else self.p_slip
    
    def _calculate_guess_evidence(self, responses):
        """Estimate guess probability from response patterns."""
        incorrect_to_correct = 0
        incorrect_total = 0
        
        # Group responses by question
        question_responses = {}
        for q_id, is_correct in responses:
            if q_id not in question_responses:
                question_responses[q_id] = []
            question_responses[q_id].append(is_correct)
        
        # Look for guesses (incorrect followed by correct without intervening practice)
        for q_id, results in question_responses.items():
            if len(results) < 2:
                continue
                
            for i in range(len(results) - 1):
                if not results[i]:  # If incorrect
                    incorrect_total += 1
                    if results[i+1]:  # But next attempt correct
                        incorrect_to_correct += 1
        
        # Calculate guess rate with smoothing
        alpha = 1.0
        return (incorrect_to_correct + alpha) / (incorrect_total + 2 * alpha) if incorrect_total > 0 else self.p_guess
    
    def get_parameter_history(self):
        """Return a dictionary of parameter history for analysis."""
        return {
            'p_transit': self.param_history['p_transit_history'],
            'p_slip': self.param_history['p_slip_history'],
            'p_guess': self.param_history['p_guess_history'],
            'response_count': self.response_count
        } 