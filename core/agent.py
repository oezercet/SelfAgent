"""Main agent loop — think, plan, execute, observe."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from core.config import get_config
from core.memory import Memory
from core.model_router import AgentResponse, ModelRouter
from core.prompts import (
    RELEVANT_CONTEXT_SECTION,
    RULES_SECTION,
    SYSTEM_PROMPT_TEMPLATE,
    USER_PROFILE_SECTION,
)
from core.task_manager import TaskManager
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 25
TOOL_TIMEOUT = 60  # seconds


class Agent:
    """Core agent with an iterative tool-use loop and persistent memory."""

    def __init__(
        self,
        model_router: ModelRouter,
        tool_registry: ToolRegistry,
        memory: Memory,
        task_manager: TaskManager,
    ) -> None:
        self.router = model_router
        self.tools = tool_registry
        self.memory = memory
        self.tasks = task_manager
        self.conversation: list[dict[str, Any]] = []
        # Cumulative token usage for this session
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0

    async def process_message(
        self, user_message: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process a user message through the full agent loop.

        Yields event dicts:
          {"type": "text", "content": "..."}
          {"type": "tool_start", "name": "...", "arguments": {...}}
          {"type": "tool_result", "name": "...", "result": "..."}
          {"type": "done"}
          {"type": "error", "content": "..."}
        """
        # Save user message to persistent memory
        self.conversation.append({"role": "user", "content": user_message})
        self.memory.add("user", user_message)
        await self.memory.save_message("user", user_message)

        # Build system prompt with context injection
        system_prompt = await self._build_system_prompt(user_message)
        tools_schema = self.tools.get_schemas() or None

        for iteration in range(MAX_ITERATIONS):
            try:
                response = await self.router.chat(
                    messages=self.conversation,
                    tools=tools_schema,
                    system_prompt=system_prompt,
                )
            except Exception as e:
                logger.exception("Model call failed")
                yield {"type": "error", "content": str(e)}
                return

            # Track token usage
            self.total_input_tokens += response.input_tokens
            self.total_output_tokens += response.output_tokens
            yield {
                "type": "usage",
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "model": response.model,
            }

            logger.info(
                "Iteration %d: text=%s, tool_calls=%d, tools=%s",
                iteration,
                repr(response.text[:100]) if response.text else "(none)",
                len(response.tool_calls),
                [tc.name for tc in response.tool_calls],
            )

            # If the model produced text with no tool calls, we're done
            if not response.has_tool_calls:
                if response.text:
                    self.conversation.append(
                        {"role": "assistant", "content": response.text}
                    )
                    # Save assistant response to persistent memory
                    self.memory.add("assistant", response.text)
                    await self.memory.save_message("assistant", response.text)
                    yield {"type": "text", "content": response.text}
                yield {"type": "done"}
                return

            # Model wants to call tools — record assistant message with calls
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": response.text or "",
            }
            assistant_msg["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in response.tool_calls
            ]
            self.conversation.append(assistant_msg)

            if response.text:
                yield {"type": "text", "content": response.text}

            # Execute each tool call
            for tc in response.tool_calls:
                yield {
                    "type": "tool_start",
                    "name": tc.name,
                    "arguments": tc.arguments,
                }

                try:
                    result = await asyncio.wait_for(
                        self.tools.execute(tc.name, **tc.arguments),
                        timeout=TOOL_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    result = f"Error: Tool '{tc.name}' timed out after {TOOL_TIMEOUT}s"
                except Exception as e:
                    result = f"Error: {e}"

                # Extract screenshot if present
                screenshot_b64 = ""
                if "__SCREENSHOT_BASE64__:" in result:
                    text_part, screenshot_b64 = result.split("__SCREENSHOT_BASE64__:", 1)
                    result = text_part.strip()
                else:
                    text_part = result

                logger.info("Tool %s result: %s", tc.name, result[:200])

                tool_msg: dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": result,
                }
                if screenshot_b64:
                    tool_msg["screenshot_b64"] = screenshot_b64

                self.conversation.append(tool_msg)
                yield {"type": "tool_result", "name": tc.name, "result": result}

        # Safety: max iterations reached
        final_msg = (
            "I've reached the maximum number of steps for this request. "
            "Here's what I've done so far — let me know if you'd like me to continue."
        )
        self.memory.add("assistant", final_msg)
        await self.memory.save_message("assistant", final_msg)
        yield {"type": "text", "content": final_msg}
        yield {"type": "done"}

    async def _build_system_prompt(self, current_message: str = "") -> str:
        """Build the system prompt with injected context from memory."""
        config = get_config()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        active_tasks = await self.tasks.format_active_tasks()
        msg_count = await self.memory.get_message_count()
        home_dir = Path.home()

        # Get email config
        email_info = ""
        try:
            email_cfg = getattr(config, "email", None)
            if email_cfg:
                email_addr = ""
                if isinstance(email_cfg, dict):
                    email_addr = email_cfg.get("username", "") or email_cfg.get("email", "")
                else:
                    email_addr = getattr(email_cfg, "email", "") or getattr(email_cfg, "username", "")
                if email_addr:
                    email_info = f"\nCONFIGURED EMAIL: {email_addr}"
        except Exception:
            pass

        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            now=now, home_dir=home_dir, msg_count=msg_count,
            email_info=email_info, active_tasks=active_tasks,
        )

        # Relevant memories
        if current_message:
            memories = await self.memory.search_relevant(current_message, top_k=5)
            if memories:
                relevant = "\n".join(
                    f"- [{m.get('timestamp', '?')}] {m['role']}: {m['content'][:200]}"
                    for m in memories
                )
                prompt += RELEVANT_CONTEXT_SECTION.format(relevant_memories=relevant)

        # User profile
        profile = await self.memory.get_user_profile()
        if profile:
            profile_text = "\n".join(f"- {k}: {v}" for k, v in profile.items())
            prompt += USER_PROFILE_SECTION.format(profile_text=profile_text)

        prompt += RULES_SECTION
        return prompt

    def clear_conversation(self) -> None:
        """Reset the conversation history."""
        self.conversation.clear()
        self.memory.clear()
