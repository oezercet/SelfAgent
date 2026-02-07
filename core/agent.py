"""Main agent loop — think, plan, execute, observe."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from core.config import get_config
from core.memory import Memory
from core.model_router import AgentResponse, ModelRouter
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

        # Get active tasks
        active_tasks = await self.tasks.format_active_tasks()

        # Get relevant memories from past conversations
        relevant_memories = ""
        if current_message:
            memories = await self.memory.search_relevant(current_message, top_k=5)
            if memories:
                relevant_memories = "\n".join(
                    f"- [{m.get('timestamp', '?')}] {m['role']}: {m['content'][:200]}"
                    for m in memories
                )

        # Get user profile
        profile = await self.memory.get_user_profile()
        profile_text = ""
        if profile:
            profile_text = "\n".join(f"- {k}: {v}" for k, v in profile.items())

        # Message count for context
        msg_count = await self.memory.get_message_count()

        home_dir = Path.home()

        # Get email config for system prompt
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

        prompt = f"""You are SelfAgent, a personal AI assistant with full access to the user's computer.
You can browse the web, manage files, read/send emails, and execute system commands.

CURRENT DATE: {now}
OPERATING SYSTEM: macOS
HOME DIRECTORY: {home_dir}
TOTAL MESSAGES IN MEMORY: {msg_count}{email_info}

IMPORTANT PATH RULES:
- Always use the real home directory path: {home_dir}
- Desktop is at: {home_dir}/Desktop
- Documents is at: {home_dir}/Documents
- Downloads is at: {home_dir}/Downloads
- Do NOT use /home/user/ — this is macOS, not Linux.

ACTIVE TASKS:
{active_tasks}
"""

        if relevant_memories:
            prompt += f"""
RELEVANT CONTEXT FROM PAST CONVERSATIONS:
{relevant_memories}
"""

        if profile_text:
            prompt += f"""
USER PROFILE:
{profile_text}
"""

        prompt += """
RULES:
1. Always complete tasks step by step. If a task requires multiple steps,
   plan them out and execute them one by one.
2. If you encounter an error, try alternative approaches before giving up.
3. For destructive or irreversible actions (deleting files, sending emails,
   making purchases), ALWAYS ask for user confirmation first.
4. When browsing the web, extract only relevant information.
   Don't dump entire page contents.
5. Keep the user informed of your progress on multi-step tasks.
6. If you create or find something, save it and tell the user where.
7. Remember user preferences and apply them in future interactions.
8. When filling forms on websites, stop at payment/password fields
   and ask the user to complete those manually.
9. Communicate in the user's preferred language.
10. If you're unsure about something, ask rather than assume.

CODE & WEBSITE RULES:
11. When writing code, ALWAYS test it by running it. If it fails,
    read the error, fix the code, and try again (max 3 retries).
12. When building websites, ALWAYS make them mobile responsive,
    include SEO meta tags, and use semantic HTML.
13. Before creating a project, check if similar files/folders already
    exist to avoid overwriting the user's work.
14. When asked to build a website, create a COMPLETE working site —
    not just boilerplate. Include real content, styling, and interactivity.
15. For coding tasks, prefer the user's language/framework preferences
    from memory. If unknown, ask or default to Python.
16. When debugging, explain what went wrong in simple terms before fixing.
17. Always create a README.md for new projects.
18. Git commit messages should be clear and follow conventional style.
19. When creating websites, start a local preview server so the user
    can see the result immediately.
20. For data analysis, always show a summary first, then offer
    deeper analysis or visualizations.

EMAIL RULES:
- Your email address is shown in CONFIGURED EMAIL above. Use it for sending.
- When asked to send an email, use the email tool directly — do NOT search
  for email settings or try to configure email. It is already configured.
- When sending info to the user, send to CONFIGURED EMAIL unless they specify another address.

WEB BROWSING EFFICIENCY:
- Do NOT waste steps filling complex search forms when a direct URL works.
  Example: instead of filling Google Flights form fields one by one, construct
  a search URL or use web_search to find info directly.
- If a site shows CAPTCHA or blocks automation, immediately switch to a
  different site or use web_search instead. Do NOT retry the same blocked site.
- When filling forms with autocomplete (city names, airports, etc.):
  1) fill the input field, 2) wait_for the suggestion dropdown, 3) click the right suggestion.
- Use get_elements to discover selectors BEFORE trying to click/fill.
- Prefer text= selectors (e.g. text=Submit) over fragile CSS selectors.
- Use evaluate_js as a last resort for complex interactions.

EFFICIENCY:
- Be direct and efficient. Don't repeat failed approaches — try alternatives.
- Minimize unnecessary tool calls. Plan your approach, then execute.
- When browsing, extract the needed info and move on. Don't explore aimlessly.
- If you have the information, provide it. Don't do extra verification steps
  that the user didn't ask for.

TASK MANAGEMENT:
- If the user gives you a task, track it. If you complete it, mark it done.
- If a task is complex, break it into subtasks.
- Always check your active tasks list and update progress."""

        return prompt

    def clear_conversation(self) -> None:
        """Reset the conversation history."""
        self.conversation.clear()
        self.memory.clear()
