"""
Agent implementations for the Misinformation Arena v2.

This module defines the two types of agents: spreaders (who promote misinformation)
and debunkers (who correct factual inaccuracies). Both agents produce deterministic
responses based on conversation history to ensure repeatable behavior.

Supports both DummyAgent implementations (deterministic rule-based) and OpenAIAgent
implementations (using OpenAI's Responses API for advanced language model capabilities).
"""

from typing import List, Optional
import hashlib
import os
from arena.types import AgentRole, Message, Turn, Citation, AgentConfig

# ===================================================================
# USER PROMPT TEMPLATE - Exposed for snapshot persistence
# ===================================================================
# WHY EXPOSE THIS CONSTANT?
# - Enables prompt snapshot persistence for reproducibility
# - Allows future prompt customization without code changes
# - Maintains exact same behavior as before (no logic changes)
# Role-specific user prompt templates.
# The neutral "Debate claim:" phrasing caused GPT-4o to default to the factually
# correct position regardless of role. Explicit framing ensures role adherence.
SPREADER_USER_PROMPT_TEMPLATE = "You are arguing IN FAVOR of this claim: {topic}\n\nOpponent's last message:\n{opponent_text}\n\nWrite your next argument defending the claim:"
DEBUNKER_USER_PROMPT_TEMPLATE = "You are arguing AGAINST this claim: {topic}\n\nOpponent's last message:\n{opponent_text}\n\nWrite your next rebuttal countering the claim:"

# Legacy alias for backward compat
DEFAULT_USER_PROMPT_TEMPLATE = SPREADER_USER_PROMPT_TEMPLATE

# ===================================================================
# STREAMLIT IMPORT FOR ERROR REPORTING
# ===================================================================
# WHY IMPORT STREAMLIT IN AGENTS MODULE?
# - OpenAI errors need to be visible in the UI
# - Session state is the cleanest way to communicate errors
# - This is acceptable for a UI-focused application
# - Errors are transient and don't affect core agent logic
import streamlit as st

# ===================================================================
# DEVELOPMENT SECRETS IMPORT
# ===================================================================
# WHY IMPORT FROM PARENT DIRECTORY?
# - secrets.py is at project root for easy access
# - Contains hardcoded API key for development
# - Not committed to version control (.gitignore)
# - Allows local development without environment variables
try:
    from local_secrets import OPENAI_API_KEY
except ImportError:
    # Fallback if local_secrets.py doesn't exist or OPENAI_API_KEY not defined
    OPENAI_API_KEY = None


class BaseAgent:
    """
    Base class for all debate agents.

    Provides common functionality and defines the interface that all agents
    must implement.
    """

    def __init__(self, role: AgentRole, name: str = None):
        """
        Initialize the agent with a specific role.

        Args:
            role: Whether this agent spreads or debunks misinformation
            name: Optional human-readable name for the agent
        """
        self.role = role
        self.name = name or f"{role.value.title()}Agent"

    def generate_response(self, conversation_history: List[Turn]) -> Message:
        """
        Generate a response based on the conversation history.

        This method must be implemented by subclasses to define how the agent
        responds to the ongoing debate. Returns a Message object with text content
        and optional structured citations.

        WHY MESSAGE OBJECTS INSTEAD OF STRINGS?
        - Citations field allows future evidence retrieval without signature changes
        - UI can render citations consistently regardless of agent type
        - Judge can score evidence quality based on citation structure
        - Maintains backward compatibility (citations start empty)
        - Enables rich, evidence-based argumentation

        Args:
            conversation_history: All previous turns in the debate

        Returns:
            The agent's response as a Message object (text + citations)
        """

    def generate(self, context: dict) -> str:
        """
        Generate a response based on context dictionary (new chat interface).

        This is the new method used by the chat-based UI. It provides more
        direct control over the agent's response generation by specifying
        exactly what context information is available.

        WHY A SEPARATE METHOD?
        - Chat UI needs different context than turn-based UI
        - Allows gradual migration from old to new interface
        - Maintains backward compatibility with existing code

        Args:
            context: Dictionary with context information:
                - "topic": The debate topic/claim
                - "turn_idx": Current turn number (0-based)
                - "last_opponent_text": Last message from opponent
                - "system_prompt": Agent's system prompt

        Returns:
            The agent's response as a plain string
        """
        # Default implementation: convert old interface to new
        # Subclasses should override for better performance
        conversation_history = []  # Empty for now - could be enhanced
        message = self.generate_response(conversation_history)
        return message.content


def create_agent(cfg: AgentConfig):
    """
    BACKWARD-COMPATIBLE WRAPPER - Creates agents from AgentConfig.

    WHY THIS WRAPPER EXISTS:
    - Provides clean AgentConfig-based API for new code
    - Routes to existing agent creation logic
    - Maintains backward compatibility
    - Centralizes agent creation validation

    Args:
        cfg: AgentConfig with role, agent_type, model, temperature, name

    Returns:
        Agent instance (DummyAgent or OpenAIAgent)

    Raises:
        ValueError: If cfg.role is missing or unknown
    """
    if not cfg.role:
        raise ValueError("AgentConfig.role is required but missing")

    # Normalize role to lowercase for case-insensitive matching
    role_lower = cfg.role.lower()

    # Validate role
    valid_roles = {'spreader', 'debunker', 'judge'}
    if role_lower not in valid_roles:
        raise ValueError(f"AgentConfig.role must be one of {valid_roles}, got '{cfg.role}'")

    # Route to existing agent creation logic
    if role_lower in {'spreader', 'debunker'}:
        # Use existing agent creation logic
        return _create_agent_impl(cfg.role, cfg.agent_type, cfg.model, cfg.temperature, cfg.name)
    elif role_lower == 'judge':
        # For judge, we need to create a judge agent
        # This would route to judge creation logic if it existed
        # For now, raise an error since judge creation is handled elsewhere
        raise ValueError("Judge agents should be created via create_judge() function, not create_agent()")


class DummyAgent(BaseAgent):
    """
    Deterministic agent that generates responses based on predefined patterns.

    This agent produces consistent, rule-based responses for testing and
    fallback scenarios when OpenAI is not available.
    """

    def __init__(self, role: AgentRole, name: str = None, note: str = None):
        super().__init__(role, name)
        self.note = note  # Optional note about why this agent was chosen

    def generate_response(self, conversation_history: List[Turn]) -> Message:
        """Generate a deterministic response based on role and turn number."""
        turn_number = len(conversation_history) + 1

        if self.role == AgentRole.SPREADER:
            content = f"This is turn {turn_number}. As a spreader, I believe the misinformation claim is true and will defend it passionately."
        else:
            content = f"This is turn {turn_number}. As a debunker, I will provide factual corrections to counter the misinformation."

        if self.note:
            content += f" [{self.note}]"

        return Message(role=self.role, content=content, citations=[])

    def generate(self, context: dict) -> str:
        """Generate a simple response for the chat interface."""
        role_name = "spreader" if self.role == AgentRole.SPREADER else "debunker"
        turn_idx = context.get("turn_idx", 0) + 1
        topic = context.get("topic", "the topic")
        opponent_text = context.get("last_opponent_text", "")

        if self.role == AgentRole.SPREADER:
            # Generate spreader responses
            responses = [
                f"I stand by my position on {topic}. The evidence clearly supports my view.",
                f"You're misunderstanding the facts about {topic}. Let me clarify my argument.",
                f"My perspective on {topic} is well-founded and backed by solid reasoning.",
                f"I disagree with your take on {topic}. Here's why my position makes more sense.",
                f"The truth about {topic} is not what you're claiming. Allow me to explain.",
            ]
        else:
            # Generate debunker responses
            responses = [
                f"Your claims about {topic} don't hold up under scrutiny. Here's the factual reality.",
                f"I must correct the misinformation about {topic}. The accurate information is different.",
                f"You're spreading falsehoods about {topic}. Let me provide the correct facts.",
                f"That's not accurate regarding {topic}. Here's what reliable sources actually say.",
                f"Your argument about {topic} is misleading. Let me set the record straight.",
            ]

        # Select response based on turn number for some variety
        response_idx = turn_idx % len(responses)
        response = responses[response_idx]

        # Add note if present
        if self.note:
            response += f" [{self.note}]"

        return response


class OpenAIAgent(BaseAgent):
    """
    Agent powered by OpenAI's language models.

    This agent uses advanced language models to generate contextually appropriate
    responses in debates. It can be configured with different models and parameters.
    """

    def __init__(self, role: AgentRole, model: str = "gpt-4o-mini", temperature: float = 0.7, name: str = None):
        super().__init__(role, name)
        self.model = model
        self.temperature = temperature
        self._client = None

    def generate_response(self, conversation_history: List[Turn]) -> Message:
        """Generate a response using OpenAI's API."""
        # For now, return a placeholder message
        # The actual implementation would use the OpenAI client
        role_name = "spreader" if self.role == AgentRole.SPREADER else "debunker"
        content = f"[OpenAI {role_name} response would go here using {self.model}]"
        return Message(role=self.role, content=content, citations=[])

    def generate(self, context: dict) -> str:
        """Generate a response using OpenAI with system prompt from context."""
        try:
            # Lazy import to avoid issues when OpenAI not installed
            from openai import OpenAI

            # Get API key using canonical method
            from arena.utils.openai_config import get_openai_api_key
            api_key = get_openai_api_key()
            if not api_key:
                return "[Error: OpenAI API key not available]"

            # Create client if not already created
            if self._client is None:
                self._client = OpenAI(api_key=api_key)

            # DEBUG: Log prompt details (only in debug mode)
            # Check for debug flag in context or environment (UI-agnostic)
            debug_enabled = (
                context.get('DEBUG_DIAG', False) or
                os.getenv('DEBUG_DIAG', '').lower() in ('true', '1', 'yes')
            )
            if debug_enabled:
                system_prompt = context.get("system_prompt", "")
                print(f"DEBUG_PROMPT {self.role.value} system_prompt_first_120='{system_prompt[:120]}...'")
                user_content = DEFAULT_USER_PROMPT_TEMPLATE.format(
                    topic=context.get('topic', ''),
                    opponent_text=context.get('last_opponent_text', '')
                )
                print(f"DEBUG_PROMPT {self.role.value} user_template_first_120='{user_content[:120]}...'")

            # Build messages for chat completion
            # Substitute {claim} placeholder with the active debate topic
            _raw_system_prompt = context.get("system_prompt", "")
            _topic = context.get("topic", "")
            _system_prompt = _raw_system_prompt.replace("{claim}", _topic) if _topic else _raw_system_prompt

            # Use role-specific user prompt to reinforce role adherence
            _user_template = SPREADER_USER_PROMPT_TEMPLATE if self.role == AgentRole.SPREADER else DEBUNKER_USER_PROMPT_TEMPLATE
            messages = [
                {"role": "system", "content": _system_prompt},
                {"role": "user", "content": _user_template.format(
                    topic=context.get('topic', ''),
                    opponent_text=context.get('last_opponent_text', '')
                )}
            ]

            # Make API call
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=500,  # Reasonable limit for debate responses
            )

            # Extract the actual generated text
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                return "[Error: No response from OpenAI]"

        except Exception as e:
            # Provide clearer error messages for common issues
            error_str = str(e)
            if "401" in error_str or "Incorrect API key" in error_str or "invalid_api_key" in error_str:
                raise RuntimeError(
                    "OpenAI authentication failed (401). Your OPENAI_API_KEY is missing or invalid. "
                    "Update it in environment variables or Streamlit secrets and restart the app."
                ) from e
            else:
                # Store error for UI display - raise exception to be handled by UI layer
                raise RuntimeError(f"OpenAI API Error: {error_str}") from e


class AnthropicAgent(BaseAgent):
    """
    Agent powered by Anthropic's Claude models.

    Uses the Anthropic SDK to call Claude models. Shares the same
    generate() interface as OpenAIAgent so the rest of the codebase
    is provider-agnostic.
    """

    def __init__(self, role: AgentRole, model: str = "claude-sonnet-4-20250514", temperature: float = 0.7, name: str = None):
        super().__init__(role, name)
        self.model = model
        self.temperature = temperature
        self._client = None

    def generate_response(self, conversation_history: List[Turn]) -> Message:
        role_name = "spreader" if self.role == AgentRole.SPREADER else "debunker"
        content = f"[Anthropic {role_name} response would go here using {self.model}]"
        return Message(role=self.role, content=content, citations=[])

    def generate(self, context: dict) -> str:
        """Generate a response using Anthropic's Claude API."""
        try:
            import anthropic

            from arena.utils.api_keys import get_anthropic_api_key
            api_key = get_anthropic_api_key()
            if not api_key:
                return "[Error: ANTHROPIC_API_KEY not available — set it in .streamlit/secrets.toml or the sidebar]"

            if self._client is None:
                self._client = anthropic.Anthropic(api_key=api_key)

            _raw_system_prompt = context.get("system_prompt", "")
            _topic = context.get("topic", "")
            _system_prompt = _raw_system_prompt.replace("{claim}", _topic) if _topic else _raw_system_prompt

            _user_template = SPREADER_USER_PROMPT_TEMPLATE if self.role == AgentRole.SPREADER else DEBUNKER_USER_PROMPT_TEMPLATE
            user_content = _user_template.format(
                topic=context.get("topic", ""),
                opponent_text=context.get("last_opponent_text", ""),
            )

            response = self._client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=self.temperature,
                system=_system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )

            if response.content and len(response.content) > 0:
                return response.content[0].text.strip()
            else:
                return "[Error: No response from Anthropic]"

        except Exception as e:
            error_str = str(e)
            if "401" in error_str or "authentication" in error_str.lower():
                raise RuntimeError(
                    "Anthropic authentication failed. Your ANTHROPIC_API_KEY is missing or invalid."
                ) from e
            else:
                raise RuntimeError(f"Anthropic API Error: {error_str}") from e


# ---------------------------------------------------------------------------
# Model → provider routing
# ---------------------------------------------------------------------------

class GeminiAgent(BaseAgent):
    """
    Agent powered by Google's Gemini models via the google-genai SDK.
    """

    def __init__(self, role: AgentRole, model: str = "gemini-2.0-flash", temperature: float = 0.7, name: str = None):
        super().__init__(role, name)
        self.model = model
        self.temperature = temperature
        self._client = None

    def generate_response(self, conversation_history: List[Turn]) -> Message:
        role_name = "spreader" if self.role == AgentRole.SPREADER else "debunker"
        content = f"[Gemini {role_name} response using {self.model}]"
        return Message(role=self.role, content=content, citations=[])

    def generate(self, context: dict) -> str:
        """Generate a response using Google Gemini."""
        try:
            from google import genai

            from arena.utils.api_keys import get_gemini_api_key
            api_key = get_gemini_api_key()
            if not api_key:
                return "[Error: GEMINI_API_KEY not available — set it in .streamlit/secrets.toml or the sidebar]"

            if self._client is None:
                self._client = genai.Client(api_key=api_key)

            _raw_system_prompt = context.get("system_prompt", "")
            _topic = context.get("topic", "")
            _system_prompt = _raw_system_prompt.replace("{claim}", _topic) if _topic else _raw_system_prompt

            _user_template = SPREADER_USER_PROMPT_TEMPLATE if self.role == AgentRole.SPREADER else DEBUNKER_USER_PROMPT_TEMPLATE
            user_content = _user_template.format(
                topic=context.get("topic", ""),
                opponent_text=context.get("last_opponent_text", ""),
            )

            response = self._client.models.generate_content(
                model=self.model,
                contents=user_content,
                config=genai.types.GenerateContentConfig(
                    system_instruction=_system_prompt,
                    temperature=self.temperature,
                    max_output_tokens=500,
                ),
            )

            if response.text:
                return response.text.strip()
            else:
                return "[Error: No response from Gemini]"

        except Exception as e:
            error_str = str(e)
            if "403" in error_str or "API key" in error_str.lower():
                raise RuntimeError(
                    "Gemini authentication failed. Your GEMINI_API_KEY is missing or invalid."
                ) from e
            else:
                raise RuntimeError(f"Gemini API Error: {error_str}") from e


class GrokAgent(BaseAgent):
    """
    Agent powered by xAI's Grok models.

    Grok uses an OpenAI-compatible API, so we reuse the OpenAI SDK
    with a custom base_url pointing to xAI's endpoint.
    """

    def __init__(self, role: AgentRole, model: str = "grok-3-mini", temperature: float = 0.7, name: str = None):
        super().__init__(role, name)
        self.model = model
        self.temperature = temperature
        self._client = None

    def generate_response(self, conversation_history: List[Turn]) -> Message:
        role_name = "spreader" if self.role == AgentRole.SPREADER else "debunker"
        content = f"[Grok {role_name} response using {self.model}]"
        return Message(role=self.role, content=content, citations=[])

    def generate(self, context: dict) -> str:
        """Generate a response using xAI Grok (OpenAI-compatible API)."""
        try:
            from openai import OpenAI

            from arena.utils.api_keys import get_xai_api_key
            api_key = get_xai_api_key()
            if not api_key:
                return "[Error: XAI_API_KEY not available — set it in .streamlit/secrets.toml or the sidebar]"

            if self._client is None:
                self._client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

            _raw_system_prompt = context.get("system_prompt", "")
            _topic = context.get("topic", "")
            _system_prompt = _raw_system_prompt.replace("{claim}", _topic) if _topic else _raw_system_prompt

            _user_template = SPREADER_USER_PROMPT_TEMPLATE if self.role == AgentRole.SPREADER else DEBUNKER_USER_PROMPT_TEMPLATE
            user_content = _user_template.format(
                topic=context.get("topic", ""),
                opponent_text=context.get("last_opponent_text", ""),
            )

            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=self.temperature,
                max_tokens=500,
            )

            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                return "[Error: No response from Grok]"

        except Exception as e:
            error_str = str(e)
            if "401" in error_str or "authentication" in error_str.lower():
                raise RuntimeError(
                    "xAI authentication failed. Your XAI_API_KEY is missing or invalid."
                ) from e
            else:
                raise RuntimeError(f"xAI Grok API Error: {error_str}") from e


# ---------------------------------------------------------------------------
# Model → provider routing
# ---------------------------------------------------------------------------

ANTHROPIC_MODEL_PREFIXES = ("claude-",)
GEMINI_MODEL_PREFIXES = ("gemini-",)
GROK_MODEL_PREFIXES = ("grok-",)

def is_anthropic_model(model: str) -> bool:
    return any(model.startswith(p) for p in ANTHROPIC_MODEL_PREFIXES)

def is_gemini_model(model: str) -> bool:
    return any(model.startswith(p) for p in GEMINI_MODEL_PREFIXES)

def is_grok_model(model: str) -> bool:
    return any(model.startswith(p) for p in GROK_MODEL_PREFIXES)


def _create_agent_impl(role: str, agent_type: str, model: str | None = None, temperature: float = 0.7, name: str | None = None):
    """
    INTERNAL AGENT CREATION LOGIC - Called by create_agent wrapper.

    This contains the actual agent creation logic that was previously
    in the create_agent function at the end of this file.
    """
    # Convert string role to AgentRole enum
    try:
        agent_role = AgentRole(role.lower())
    except ValueError:
        raise ValueError(f"Invalid role '{role}'. Must be 'spreader' or 'debunker'.")

    # ── Auto-route by model prefix ──
    if model and is_anthropic_model(model):
        from arena.utils.api_keys import get_anthropic_api_key
        key = get_anthropic_api_key()
        if not key:
            print(f"Warning: Claude model requested for {role} but ANTHROPIC_API_KEY not set. Falling back to DummyAgent.")
            return DummyAgent(agent_role, name, note="ANTHROPIC_API_KEY not set; falling back to DummyAgent.")
        return AnthropicAgent(agent_role, model, temperature, name)

    if model and is_gemini_model(model):
        from arena.utils.api_keys import get_gemini_api_key
        key = get_gemini_api_key()
        if not key:
            print(f"Warning: Gemini model requested for {role} but GEMINI_API_KEY not set. Falling back to DummyAgent.")
            return DummyAgent(agent_role, name, note="GEMINI_API_KEY not set; falling back to DummyAgent.")
        return GeminiAgent(agent_role, model, temperature, name)

    if model and is_grok_model(model):
        from arena.utils.api_keys import get_xai_api_key
        key = get_xai_api_key()
        if not key:
            print(f"Warning: Grok model requested for {role} but XAI_API_KEY not set. Falling back to DummyAgent.")
            return DummyAgent(agent_role, name, note="XAI_API_KEY not set; falling back to DummyAgent.")
        return GrokAgent(agent_role, model, temperature, name)

    if agent_type.upper() == "OPENAI":
        from arena.utils.api_keys import get_openai_api_key
        key = get_openai_api_key()

        # Normalize / guard against placeholder
        if not key or str(key).strip() == "" or str(key).strip() == "PASTE_YOUR_KEY_HERE":
            print(f"Warning: OpenAI requested for {role} but OPENAI_API_KEY not set. Falling back to DummyAgent.")
            fallback_note = "OPENAI_API_KEY not set; falling back to DummyAgent."
            return DummyAgent(agent_role, name, note=fallback_note)

        # Ensure env var is set so OpenAIAgent's internal client picks it up
        if not os.environ.get("OPENAI_API_KEY") and key:
            os.environ["OPENAI_API_KEY"] = str(key)

        return OpenAIAgent(agent_role, model or "gpt-4o-mini", temperature, name)

    elif agent_type.upper() == "DUMMY":
        # Create dummy agent
        return DummyAgent(agent_role, name)

    else:
        raise ValueError(f"Unknown agent_type '{agent_type}'. Must be 'Dummy' or 'OpenAI'.")