"""
Action parsing and processing utilities.
"""

import re
import random
from typing import Tuple, Optional, List


def parse_action(action_string: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse action string to extract action type and argument.

    Args:
        action_string: String containing action in format "ActionType[argument]"

    Returns:
        Tuple of (action_type, argument) or (None, None) if parsing fails
    """
    # Look for different action patterns
    patterns = [
        r'Retrieve\[(.+?)\]',
        r'Operate\[(.+?)\]',
        r'Finish\[(.+?)\]',
        r'Search\[(.+?)\]',
        r'Calculate\[(.+?)\]'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, action_string)
        if matches:
            action_type = pattern.split('\\[')[0].replace('r\'', '')
            argument = matches[0]
            return action_type, argument

    # Generic pattern
    pattern = r'^(\w+)\[(.+)\]$'
    match = re.match(pattern, action_string.strip())
    if match:
        action_type = match.group(1)
        argument = match.group(2)
        return action_type, argument

    return None, None


def parse_thought_action(response: str) -> Tuple[str, str]:
    """
    Parse LLM response to extract thought and action.

    Args:
        response: Raw LLM response

    Returns:
        Tuple of (thought, action)
    """
    lines = response.strip().split('\n')
    thought = ""
    action = ""

    # Look for thought and action patterns
    for line in lines:
        line = line.strip()
        if line.startswith("Thought"):
            thought = line.split(":", 1)[-1].strip()
        elif line.startswith("Action"):
            action = line.split(":", 1)[-1].strip()

    # If no explicit markers, try to infer
    if not thought or not action:
        # Look for action patterns
        action_patterns = [
            r'(Retrieve\[.+?\])',
            r'(Calculate\[.+?\])',
            r'(Search\[.+?\])',
            r'(Operate\[.+?\])',
            r'(Finish\[.+?\])'
        ]

        for pattern in action_patterns:
            matches = re.findall(pattern, response)
            if matches:
                action = matches[-1]  # Take the last match
                break

        # Everything before the action is thought
        if action:
            action_pos = response.rfind(action)
            if action_pos > 0:
                thought = response[:action_pos].strip()
        else:
            thought = response.strip()

    return thought, action


def extract_from_outputs(outputs: str, num_choices: int) -> int:
    """
    Extract choice number from LLM evaluation output.

    Args:
        outputs: LLM output containing choice
        num_choices: Total number of choices available

    Returns:
        Selected choice index (0-based)
    """
    try:
        # Look for "The best path is X" or "The best result is X"
        extracted = re.findall(r'The best path is \d', outputs) + \
                   re.findall(r'The best result is \d', outputs)

        if len(extracted) > 0:
            target_choice = int(re.findall(r'\d', extracted[0])[0]) - 1
        else:
            target_choice = random.randint(0, num_choices - 1)

        # Ensure choice is within valid range
        if target_choice >= num_choices:
            target_choice = random.randint(0, num_choices - 1)

    except:
        target_choice = 0

    return target_choice


def extract_answer_from_response(response: str, method: str = "smart") -> str:
    """
    Extract answer from LLM response using various methods.

    Args:
        response: LLM response text
        method: Extraction method ("last_line", "boxed", "answer_prefix", "smart")

    Returns:
        Extracted answer string
    """
    if not response or not response.strip():
        return ""

    response = response.strip()

    if method == "smart":
        # Try multiple extraction methods in order
        for extraction_method in ["answer_prefix", "boxed", "last_line"]:
            result = extract_answer_from_response(response, extraction_method)
            if result and result != response:  # Found a shorter, extracted answer
                return result
        return response  # Fallback to full response

    elif method == "last_line":
        # Get the last non-empty line
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        return lines[-1] if lines else ""

    elif method == "boxed":
        # Look for \\boxed{answer} pattern
        boxed_pattern = r'\\boxed\{([^}]+)\}'
        matches = re.findall(boxed_pattern, response)
        return matches[-1] if matches else ""

    elif method == "answer_prefix":
        # Look for common answer patterns
        patterns = [
            r'(?:Answer|Final Answer|The answer is):\s*(.+)',
            r'(?:Answer|Final Answer|The answer is)\s+(.+)',
            r'.*?\$([0-9.,]+\s*million)',  # Dollar amounts first
            r'.*?(?:was|is|were|are)\s+([^.]+?)\.',
            r'.*?utilizing\s+(.+?)\.',
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                # Clean up common prefixes/suffixes
                extracted = re.sub(r'^(the|a|an)\s+', '', extracted, flags=re.IGNORECASE)
                return extracted

        return ""

    else:
        return response


def clean_action_argument(argument: str) -> str:
    """Clean and normalize action argument."""
    argument = argument.strip()

    # Remove common prefixes/suffixes
    argument = re.sub(r'^(the|a|an)\s+', '', argument, flags=re.IGNORECASE)
    argument = re.sub(r'\s*(please|kindly)\s*', '', argument, flags=re.IGNORECASE)

    return argument


def validate_action(action_type: str, argument: str) -> bool:
    """
    Validate if an action is properly formatted.

    Args:
        action_type: Type of action
        argument: Action argument

    Returns:
        True if action is valid, False otherwise
    """
    if not action_type or not argument:
        return False

    valid_actions = {"Retrieve", "Calculate", "Search", "Operate", "Finish"}
    if action_type not in valid_actions:
        return False

    # Basic argument validation
    argument = argument.strip()
    if len(argument) == 0:
        return False

    # Action-specific validation
    if action_type == "Calculate":
        # Should contain some mathematical expression
        math_indicators = ['+', '-', '*', '/', '=', 'sum', 'count', 'average', 'max', 'min']
        return any(indicator in argument.lower() for indicator in math_indicators)

    elif action_type == "Retrieve":
        # Should contain some filtering or selection criteria
        return len(argument) > 3

    elif action_type == "Search":
        # Should be a reasonable search query
        return len(argument) > 2

    elif action_type == "Operate":
        # Should contain some operation description
        return len(argument) > 5

    elif action_type == "Finish":
        # Should contain an answer
        return len(argument) > 0

    return True