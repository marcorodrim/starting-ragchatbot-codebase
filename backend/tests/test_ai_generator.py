"""Tests that AIGenerator calls the CourseSearchTool correctly"""
from unittest.mock import Mock

import pytest

from ai_generator import AIGenerator
from search_tools import CourseSearchTool, ToolManager

from conftest import make_response, text_block, thinking_block, tool_use_block


SEARCH_TOOL_DEF = CourseSearchTool(Mock()).get_tool_definition()


@pytest.fixture
def generator():
    gen = AIGenerator(api_key="test-key", model="test-model")
    gen.client = Mock()
    return gen


@pytest.fixture
def tool_manager():
    manager = Mock(spec=ToolManager)
    manager.execute_tool.return_value = "[Some Course - Lesson 1]\nsearch result text"
    return manager


def create_calls(gen):
    return gen.client.messages.create.call_args_list


class TestDirectResponses:

    def test_passes_tools_with_auto_choice(self, generator, tool_manager):
        generator.client.messages.create.return_value = make_response(text_block("hi"))
        generator.generate_response("q", tools=[SEARCH_TOOL_DEF], tool_manager=tool_manager)
        kwargs = create_calls(generator)[0].kwargs
        assert kwargs["tools"] == [SEARCH_TOOL_DEF]
        assert kwargs["tool_choice"] == {"type": "auto"}
        assert kwargs["model"] == "test-model"
        assert kwargs["messages"] == [{"role": "user", "content": "q"}]

    def test_no_tools_key_when_tools_absent(self, generator):
        generator.client.messages.create.return_value = make_response(text_block("hi"))
        generator.generate_response("q")
        assert "tools" not in create_calls(generator)[0].kwargs

    def test_history_goes_into_system_prompt(self, generator):
        generator.client.messages.create.return_value = make_response(text_block("hi"))
        generator.generate_response("q", conversation_history="User: earlier\nAssistant: answer")
        system = create_calls(generator)[0].kwargs["system"]
        assert system.startswith(AIGenerator.SYSTEM_PROMPT)
        assert "Previous conversation:\nUser: earlier\nAssistant: answer" in system

    def test_text_response_does_not_execute_tools(self, generator, tool_manager):
        generator.client.messages.create.return_value = make_response(text_block("Paris"))
        out = generator.generate_response("q", tools=[SEARCH_TOOL_DEF], tool_manager=tool_manager)
        assert out == "Paris"
        tool_manager.execute_tool.assert_not_called()
        assert len(create_calls(generator)) == 1

    def test_skips_thinking_blocks(self, generator):
        generator.client.messages.create.return_value = make_response(thinking_block(), text_block("answer"))
        assert generator.generate_response("q") == "answer"

    def test_refusal_returns_fallback(self, generator):
        generator.client.messages.create.return_value = make_response(stop_reason="refusal")
        assert generator.generate_response("q") == "Sorry, I can't help with that request."


class TestToolUse:

    def test_executes_search_tool_and_sends_result_back(self, generator, tool_manager):
        tool_input = {"query": "vector databases", "course_name": "RAG"}
        first = make_response(
            text_block("Let me search."),
            tool_use_block("search_course_content", tool_input, block_id="toolu_abc"),
            stop_reason="tool_use",
        )
        generator.client.messages.create.side_effect = [first, make_response(text_block("Final answer"))]

        out = generator.generate_response("q", tools=[SEARCH_TOOL_DEF], tool_manager=tool_manager)

        assert out == "Final answer"
        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="vector databases", course_name="RAG"
        )

        calls = create_calls(generator)
        assert len(calls) == 2
        messages = calls[1].kwargs["messages"]
        assert messages[0] == {"role": "user", "content": "q"}
        assert messages[1] == {"role": "assistant", "content": first.content}
        assert messages[2] == {"role": "user", "content": [{
            "type": "tool_result",
            "tool_use_id": "toolu_abc",
            "content": "[Some Course - Lesson 1]\nsearch result text",
        }]}
        assert calls[1].kwargs["system"] == calls[0].kwargs["system"]
        # Round 2 keeps tools available so Claude can search again if needed
        assert calls[1].kwargs["tools"] == [SEARCH_TOOL_DEF]

    def test_executes_all_tool_calls_in_one_message(self, generator, tool_manager):
        tool_manager.execute_tool.side_effect = ["result A", "result B"]
        first = make_response(
            tool_use_block("search_course_content", {"query": "a"}, block_id="t1"),
            tool_use_block("get_course_outline", {"course_title": "b"}, block_id="t2"),
            stop_reason="tool_use",
        )
        generator.client.messages.create.side_effect = [first, make_response(text_block("done"))]

        generator.generate_response("q", tools=[SEARCH_TOOL_DEF], tool_manager=tool_manager)

        assert tool_manager.execute_tool.call_count == 2
        tool_results = create_calls(generator)[1].kwargs["messages"][2]["content"]
        assert [r["tool_use_id"] for r in tool_results] == ["t1", "t2"]
        assert [r["content"] for r in tool_results] == ["result A", "result B"]

    def test_tool_use_without_manager_returns_text(self, generator):
        generator.client.messages.create.return_value = make_response(
            text_block("partial"), tool_use_block("search_course_content", {"query": "a"}),
            stop_reason="tool_use",
        )
        assert generator.generate_response("q", tools=[SEARCH_TOOL_DEF]) == "partial"
        assert len(create_calls(generator)) == 1

    def test_with_real_tool_manager(self, generator, mock_store):
        """End-to-end through a real ToolManager + CourseSearchTool (mocked store)"""
        from vector_store import SearchResults
        mock_store.search.return_value = SearchResults(
            documents=["chunk text"], metadata=[{"course_title": "C", "lesson_number": 2}], distances=[0.1]
        )
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_store))
        generator.client.messages.create.side_effect = [
            make_response(tool_use_block("search_course_content", {"query": "x", "lesson_number": 2}),
                          stop_reason="tool_use"),
            make_response(text_block("ok")),
        ]

        generator.generate_response("q", tools=manager.get_tool_definitions(), tool_manager=manager)

        mock_store.search.assert_called_once_with(query="x", course_name=None, lesson_number=2)
        result = create_calls(generator)[1].kwargs["messages"][2]["content"][0]["content"]
        assert result == "[C - Lesson 2]\nchunk text"


def tool_response(name, tool_input, block_id):
    return make_response(tool_use_block(name, tool_input, block_id=block_id), stop_reason="tool_use")


class TestSequentialToolUse:

    def test_two_rounds_then_final_call_without_tools(self, generator, tool_manager):
        """Outline lookup -> search using the lesson title -> final answer"""
        tool_manager.execute_tool.side_effect = [
            "Course Title: X\nLesson 4: Tool Design",
            "[Course Y - Lesson 2]\ntool design content",
        ]
        generator.client.messages.create.side_effect = [
            tool_response("get_course_outline", {"course_title": "X"}, "t1"),
            tool_response("search_course_content", {"query": "Tool Design"}, "t2"),
            make_response(text_block("Course Y covers it")),
        ]

        out = generator.generate_response("q", tools=[SEARCH_TOOL_DEF], tool_manager=tool_manager)

        assert out == "Course Y covers it"
        assert [c.args for c in tool_manager.execute_tool.call_args_list] == [
            ("get_course_outline",), ("search_course_content",)
        ]
        assert [c.kwargs for c in tool_manager.execute_tool.call_args_list] == [
            {"course_title": "X"}, {"query": "Tool Design"}
        ]
        calls = create_calls(generator)
        assert len(calls) == 3
        assert calls[0].kwargs["tools"] == [SEARCH_TOOL_DEF]
        assert calls[1].kwargs["tools"] == [SEARCH_TOOL_DEF]
        assert "tools" not in calls[2].kwargs
        assert "tool_choice" not in calls[2].kwargs

    def test_context_preserved_between_rounds(self, generator, tool_manager):
        tool_manager.execute_tool.side_effect = ["result 1", "result 2"]
        first = tool_response("get_course_outline", {"course_title": "X"}, "t1")
        second = tool_response("search_course_content", {"query": "y"}, "t2")
        generator.client.messages.create.side_effect = [first, second, make_response(text_block("done"))]

        generator.generate_response("q", conversation_history="User: hi", tools=[SEARCH_TOOL_DEF],
                                    tool_manager=tool_manager)

        calls = create_calls(generator)
        assert len(calls[0].kwargs["messages"]) == 1
        assert len(calls[1].kwargs["messages"]) == 3
        final_messages = calls[2].kwargs["messages"]
        assert final_messages == [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": first.content},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "result 1"}]},
            {"role": "assistant", "content": second.content},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "result 2"}]},
        ]
        # Round 2 saw exactly the prefix of the conversation
        assert calls[1].kwargs["messages"] == final_messages[:3]
        assert len({c.kwargs["system"] for c in calls}) == 1
        assert "User: hi" in calls[0].kwargs["system"]

    def test_stops_after_max_rounds(self, generator, tool_manager):
        """Even if Claude keeps requesting tools, only 2 rounds execute"""
        generator.client.messages.create.side_effect = [
            tool_response("search_course_content", {"query": "a"}, "t1"),
            tool_response("search_course_content", {"query": "b"}, "t2"),
            make_response(text_block("partial"),
                          tool_use_block("search_course_content", {"query": "c"}, block_id="t3"),
                          stop_reason="tool_use"),
        ]

        out = generator.generate_response("q", tools=[SEARCH_TOOL_DEF], tool_manager=tool_manager)

        assert out == "partial"
        assert tool_manager.execute_tool.call_count == 2
        calls = create_calls(generator)
        assert len(calls) == 3
        assert "tools" not in calls[2].kwargs

    def test_tool_exception_ends_rounds_gracefully(self, generator, tool_manager):
        tool_manager.execute_tool.side_effect = RuntimeError("boom")
        generator.client.messages.create.side_effect = [
            tool_response("search_course_content", {"query": "a"}, "t1"),
            make_response(text_block("Search is unavailable right now.")),
        ]

        out = generator.generate_response("q", tools=[SEARCH_TOOL_DEF], tool_manager=tool_manager)

        assert out == "Search is unavailable right now."
        assert tool_manager.execute_tool.call_count == 1
        calls = create_calls(generator)
        assert len(calls) == 2
        assert "tools" not in calls[1].kwargs
        result = calls[1].kwargs["messages"][2]["content"][0]
        assert result["tool_use_id"] == "t1"
        assert result["is_error"] is True
        assert "boom" in result["content"]

    def test_one_of_two_tools_failing_returns_all_results(self, generator, tool_manager):
        tool_manager.execute_tool.side_effect = [RuntimeError("boom"), "result B"]
        generator.client.messages.create.side_effect = [
            make_response(
                tool_use_block("search_course_content", {"query": "a"}, block_id="t1"),
                tool_use_block("get_course_outline", {"course_title": "b"}, block_id="t2"),
                stop_reason="tool_use",
            ),
            make_response(text_block("done")),
        ]

        generator.generate_response("q", tools=[SEARCH_TOOL_DEF], tool_manager=tool_manager)

        calls = create_calls(generator)
        assert len(calls) == 2
        assert "tools" not in calls[1].kwargs
        failed, ok = calls[1].kwargs["messages"][2]["content"]
        assert failed["tool_use_id"] == "t1" and failed["is_error"] is True
        assert ok == {"type": "tool_result", "tool_use_id": "t2", "content": "result B"}

    def test_refusal_in_second_round(self, generator, tool_manager):
        generator.client.messages.create.side_effect = [
            tool_response("search_course_content", {"query": "a"}, "t1"),
            make_response(stop_reason="refusal"),
        ]

        out = generator.generate_response("q", tools=[SEARCH_TOOL_DEF], tool_manager=tool_manager)

        assert out == "Sorry, I can't help with that request."
        assert len(create_calls(generator)) == 2

    def test_real_tool_manager_store_failure(self, generator, mock_store):
        mock_store.search.side_effect = RuntimeError("db down")
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_store))
        generator.client.messages.create.side_effect = [
            tool_response("search_course_content", {"query": "x"}, "t1"),
            make_response(text_block("Sorry, search failed.")),
        ]

        out = generator.generate_response("q", tools=manager.get_tool_definitions(), tool_manager=manager)

        assert out == "Sorry, search failed."
        calls = create_calls(generator)
        assert len(calls) == 2
        result = calls[1].kwargs["messages"][2]["content"][0]
        assert result["is_error"] is True and "db down" in result["content"]
