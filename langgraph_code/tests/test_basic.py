"""
Basic tests for MACT LangGraph implementation.
"""

import pytest
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mact_langgraph.state import (
    MACTState, ActionType, ActionCandidate, TableInfo,
    create_initial_state
)
from mact_langgraph.graph import MACTGraph, run_mact_on_question_async
from mact_langgraph.utils.table_utils import table_linear, table2df, exact_match
from mact_langgraph.utils.action_utils import parse_action, parse_thought_action
from mact_langgraph.utils.mmqa_utils import process_mmqa_tables


class TestState:
    """Test state management."""

    def test_create_initial_state(self):
        """Test initial state creation."""
        question = "Test question"
        tables_data = [
            {
                "table_columns": ["col1", "col2"],
                "table_content": [["val1", "val2"]]
            }
        ]

        state = create_initial_state(question, tables_data)

        assert state["question"] == question
        assert len(state["tables"]) == 1
        assert state["current_step"] == 1
        assert state["is_finished"] is False
        assert state["is_halted"] is False

    def test_action_candidate_serialization(self):
        """Test ActionCandidate serialization."""
        candidate = ActionCandidate(
            thought="Test thought",
            action="Retrieve[test]",
            action_type=ActionType.RETRIEVE,
            argument="test",
            score=0.5
        )

        # Convert to dict and back
        candidate_dict = candidate.to_dict()
        restored_candidate = ActionCandidate.from_dict(candidate_dict)

        assert restored_candidate.thought == candidate.thought
        assert restored_candidate.action == candidate.action
        assert restored_candidate.action_type == candidate.action_type
        assert restored_candidate.argument == candidate.argument
        assert restored_candidate.score == candidate.score

    def test_table_info_serialization(self):
        """Test TableInfo serialization."""
        table = TableInfo(
            name="test_table",
            columns=["col1", "col2"],
            content=[["val1", "val2"]]
        )

        # Convert to dict and back
        table_dict = table.to_dict()
        restored_table = TableInfo.from_dict(table_dict)

        assert restored_table.name == table.name
        assert restored_table.columns == table.columns
        assert restored_table.content == table.content


class TestUtils:
    """Test utility functions."""

    def test_table_linear(self):
        """Test table linear representation."""
        table = [
            ["Name", "Age"],
            ["Alice", 25],
            ["Bob", 30]
        ]

        result = table_linear(table, num_row=None)

        assert "| Name | Age |" in result
        assert "| Alice | 25 |" in result
        assert "| Bob | 30 |" in result

    def test_table2df(self):
        """Test table to DataFrame code generation."""
        table = [
            ["Name", "Age"],
            ["Alice", 25],
            ["Bob", 30]
        ]

        result = table2df(table)

        assert "import pandas as pd" in result
        assert "df=pd.DataFrame(data)" in result
        assert "'Name'" in result
        assert "'Age'" in result

    def test_exact_match(self):
        """Test exact match function."""
        assert exact_match("Treasury", "treasury") is True
        assert exact_match("The Treasury", "treasury") is True
        assert exact_match("Treasury Dept", "treasury") is False
        assert exact_match("123", "123.0") is True

    def test_parse_action(self):
        """Test action parsing."""
        action_type, argument = parse_action("Retrieve[data from table]")
        assert action_type == "Retrieve"
        assert argument == "data from table"

        action_type, argument = parse_action("Calculate[2 + 2]")
        assert action_type == "Calculate"
        assert argument == "2 + 2"

        action_type, argument = parse_action("Invalid action")
        assert action_type is None
        assert argument is None

    def test_parse_thought_action(self):
        """Test thought-action parsing."""
        response = """Thought: I need to find the data
Action: Retrieve[specific data]"""

        thought, action = parse_thought_action(response)
        assert "I need to find the data" in thought
        assert action == "Retrieve[specific data]"


class TestMMQAUtils:
    """Test MMQA utility functions."""

    def test_process_mmqa_tables(self):
        """Test MMQA table processing."""
        tables_data = [
            {
                "table_columns": ["ID", "Name", "Value"],
                "table_content": [
                    [1, "Item1", 100],
                    [2, "Item2", 200]
                ]
            }
        ]

        tables = process_mmqa_tables(tables_data)

        assert len(tables) == 1
        table = tables[0]
        assert table.name == "table_0"
        assert table.columns == ["ID", "Name", "Value"]
        assert len(table.content) == 2
        assert table.df_code is not None
        assert table.linear_representation is not None


@pytest.mark.asyncio
class TestGraphExecution:
    """Test graph execution."""

    async def test_simple_question(self):
        """Test simple question processing."""
        question = "How many items are there?"
        tables_data = [
            {
                "table_columns": ["ID", "Name"],
                "table_content": [
                    [1, "Item1"],
                    [2, "Item2"],
                    [3, "Item3"]
                ]
            }
        ]

        config = {
            "plan_model": "gpt-3.5-turbo",
            "code_model": "gpt-3.5-turbo",
            "max_steps": 3,
            "plan_sample": 2,
            "code_sample": 2
        }

        # This test requires OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OpenAI API key not available")

        result = await run_mact_on_question_async(question, tables_data, config)

        assert result["question"] == question
        assert "final_answer" in result
        assert isinstance(result["steps_taken"], int)
        assert isinstance(result["confidence"], float)

    def test_graph_structure(self):
        """Test graph structure creation."""
        graph = MACTGraph()

        # Test that graph is created without errors
        assert graph.graph is not None

        # Test graph visualization
        viz = graph.get_graph_visualization()
        assert "input_processor" in viz
        assert "planner" in viz
        assert "action_selector" in viz

    def test_state_validation(self):
        """Test state validation."""
        graph = MACTGraph()

        # Valid state
        valid_state = create_initial_state("test", [])
        assert graph.validate_state(valid_state) is True

        # Invalid state (missing required field)
        invalid_state = {"question": "test"}
        assert graph.validate_state(invalid_state) is False


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__])