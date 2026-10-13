import anthropic
from typing import List, Optional, Dict, Any, Tuple

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Available Tools:
- **search_course_content**: Search within course materials. Use **only** for questions about specific course content or detailed educational materials
- **get_course_outline**: Get a course's title, link and complete lesson list. Use for questions about a course's outline, structure, syllabus, or which lessons it contains

Tool Usage:
- You may use tools in up to **2 sequential rounds** per query; after each round you will see the results before deciding the next step
- Use a second round only when the first result is needed to form the next call (e.g. get a course outline to find a lesson title, then search content for that lesson)
- If a tool reports an error, do not retry; answer with what you have and state the limitation briefly
- Synthesize tool results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

Outline Responses:
- For outline-related queries, always return the **course title**, the **course link**, and **every lesson** with its **lesson number and lesson title**
- List all lessons in order — do not summarize, skip, or truncate the list

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course content questions**: Search first, then answer
- **Course outline questions**: Get the course outline first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    # Maximum sequential tool-use rounds per query
    MAX_TOOL_ROUNDS = 2

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        # (no temperature: rejected by newer models; thinking shares max_tokens, so leave headroom)
        self.base_params = {
            "model": self.model,
            "max_tokens": 16000
        }

    @staticmethod
    def _extract_text(response) -> str:
        """Join the text blocks of a response, skipping thinking/tool_use blocks"""
        if response.stop_reason == "refusal":
            return "Sorry, I can't help with that request."
        return "".join(block.text for block in response.content if block.type == "text").strip()
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        messages = [{"role": "user", "content": query}]
        tool_params = {"tools": tools, "tool_choice": {"type": "auto"}} if tools else {}

        # Each round is a separate API call where Claude sees all prior tool results
        for _ in range(self.MAX_TOOL_ROUNDS):
            # Pass a copy so each call keeps its own snapshot of the conversation
            response = self.client.messages.create(
                **self.base_params, **tool_params,
                messages=list(messages),
                system=system_content
            )

            # Done: no tool use (also covers refusal) or nothing to run tools with
            if response.stop_reason != "tool_use" or not tool_manager:
                return self._extract_text(response)

            messages.append({"role": "assistant", "content": response.content})
            tool_results, failed = self._run_tools(response, tool_manager)
            messages.append({"role": "user", "content": tool_results})

            if failed:
                break

        # Rounds exhausted or a tool failed: final call without tools forces a text answer
        final_response = self.client.messages.create(
            **self.base_params,
            messages=list(messages),
            system=system_content
        )
        return self._extract_text(final_response)

    @staticmethod
    def _run_tools(response, tool_manager) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Execute every tool_use block in a response.

        Returns:
            (tool_result blocks, whether any tool raised)
        """
        results, failed = [], False
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = {"type": "tool_result", "tool_use_id": block.id}
            try:
                result["content"] = tool_manager.execute_tool(block.name, **block.input)
            except Exception as e:
                result["content"] = f"Tool '{block.name}' failed: {e}"
                result["is_error"] = True
                failed = True
            results.append(result)
        return results, failed