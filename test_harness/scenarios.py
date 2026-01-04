"""
Standard test scenarios for validating the voice pipeline
"""

from typing import Any


class TestScenario:
    """Standard test scenarios"""

    @staticmethod
    def basic_greeting() -> dict[str, Any]:
        """Test basic greeting interaction"""
        return {
            "scenario_name": "Basic Greeting",
            "input_text": "Hello Claude",
            "expected_response_contains": "hello",
            "max_latency_ms": 2000,
        }

    @staticmethod
    def short_question() -> dict[str, Any]:
        """Test short factual question"""
        return {
            "scenario_name": "Short Question",
            "input_text": "What is 2 plus 2?",
            "expected_response_contains": "4",
            "max_latency_ms": 2000,
        }

    @staticmethod
    def multi_sentence_response() -> dict[str, Any]:
        """Test response with multiple sentences (tests chunking)"""
        return {
            "scenario_name": "Multi-Sentence Response",
            "input_text": "Tell me about yourself in detail",
            "expected_response_contains": "claude",
            "max_latency_ms": 3000,
        }

    @staticmethod
    def empty_input() -> dict[str, Any]:
        """Test handling of empty input"""
        return {
            "scenario_name": "Empty Input",
            "input_text": "",
            "expected_response_contains": None,  # Should handle gracefully
            "max_latency_ms": 1000,
        }

    @staticmethod
    def long_question() -> dict[str, Any]:
        """Test longer, more complex question"""
        return {
            "scenario_name": "Long Question",
            "input_text": "Can you explain how streaming works in voice assistants and why it's better than waiting for the full response?",
            "expected_response_contains": "streaming",
            "max_latency_ms": 4000,
        }


def create_standard_scenarios() -> list[dict[str, Any]]:
    """
    Create list of standard test scenarios

    Returns:
        List of scenario configurations
    """
    return [
        TestScenario.basic_greeting(),
        TestScenario.short_question(),
        TestScenario.multi_sentence_response(),
        TestScenario.long_question(),
        # Empty input test disabled by default (needs special handling)
        # TestScenario.empty_input(),
    ]


def create_latency_scenarios() -> list[dict[str, Any]]:
    """
    Scenarios focused on latency testing

    Returns:
        List of latency-focused scenarios
    """
    return [
        {
            "scenario_name": "Sub-1s Response",
            "input_text": "Hi",
            "expected_response_contains": None,
            "max_latency_ms": 1000,
        },
        {
            "scenario_name": "Sub-2s Complex Query",
            "input_text": "What's the weather like?",
            "expected_response_contains": None,
            "max_latency_ms": 2000,
        },
    ]


def create_edge_case_scenarios() -> list[dict[str, Any]]:
    """
    Edge case scenarios for robustness testing

    Returns:
        List of edge case scenarios
    """
    return [
        {
            "scenario_name": "Very Long Input",
            "input_text": "Tell me about " + "artificial intelligence " * 50,
            "expected_response_contains": None,
            "max_latency_ms": 5000,
        },
        {
            "scenario_name": "Special Characters",
            "input_text": "What is 1 + 1? !@#$%^&*()",
            "expected_response_contains": "2",
            "max_latency_ms": 2000,
        },
        {
            "scenario_name": "Numbers Only",
            "input_text": "123 456 789",
            "expected_response_contains": None,
            "max_latency_ms": 2000,
        },
    ]
