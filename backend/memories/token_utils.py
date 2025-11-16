import logging

# SVC-P2-11 fix: Removed unused 're' import after optimizing regex operations

logger = logging.getLogger(__name__)


class TokenCounter:
    """
    Simple token counter that provides rough estimates for various models.
    Uses a combination of word counting and character-based heuristics.
    """

    # Rough tokens per character for different model families
    TOKENS_PER_CHAR = {
        "gpt": 0.25,  # GPT models (OpenAI)
        "claude": 0.24,  # Claude models
        "llama": 0.25,  # Llama models
        "qwen": 0.20,  # Qwen models (often more efficient)
        "default": 0.25,  # Default fallback
    }

    @classmethod
    def estimate_tokens(cls, text: str, model_name: str = "") -> int:
        """
        Estimate token count for given text and model.
        This is a rough approximation - actual tokenization may vary.
        """
        if not text:
            return 0

        # Clean the text
        text = text.strip()

        # Determine model family
        model_family = cls._get_model_family(model_name.lower())
        tokens_per_char = cls.TOKENS_PER_CHAR.get(
            model_family, cls.TOKENS_PER_CHAR["default"]
        )

        # Method 1: Character-based estimation
        char_estimate = len(text) * tokens_per_char

        # Method 2: Word-based estimation (roughly 1.3 tokens per word for English)
        words = len(text.split())
        word_estimate = words * 1.3

        # Method 3: More sophisticated estimation considering punctuation and special chars
        # SVC-P2-11 fix: Count character types in a single pass instead of 4 regex operations
        # This is much more efficient, especially for large texts
        word_chars = 0
        number_chars = 0
        punct_chars = 0
        space_chars = 0

        for char in text:
            if char.isalpha():
                word_chars += 1
            elif char.isdigit():
                number_chars += 1
            elif char.isspace():
                space_chars += 1
            else:
                punct_chars += 1

        sophisticated_estimate = (
            word_chars * 0.25  # Letters
            + number_chars * 0.5  # Numbers (often tokenized differently)
            + punct_chars * 0.3  # Punctuation
            + space_chars * 0.1  # Spaces
        )

        # Use the average of methods, weighted toward the more conservative estimates
        final_estimate = (
            char_estimate * 0.4 + word_estimate * 0.4 + sophisticated_estimate * 0.2
        )

        # Add some padding for safety (10%)
        padded_estimate = final_estimate * 1.1

        return max(1, int(padded_estimate))

    @classmethod
    def _get_model_family(cls, model_name: str) -> str:
        """Determine model family from model name"""
        model_name = model_name.lower()

        if any(x in model_name for x in ["gpt", "davinci", "curie", "babbage", "ada"]):
            return "gpt"
        elif "claude" in model_name:
            return "claude"
        elif any(x in model_name for x in ["llama", "alpaca", "vicuna"]):
            return "llama"
        elif "qwen" in model_name:
            return "qwen"
        else:
            return "default"

    @classmethod
    def calculate_required_context(
        cls,
        prompt: str,
        user_input: str = "",
        model_name: str = "",
        safety_margin: int = 512,
    ) -> int:
        """
        Calculate the minimum context size needed for the given prompt and input.

        Args:
            prompt: System/instruction prompt
            user_input: User input text
            model_name: Name of the model being used
            safety_margin: Additional tokens to add for response generation

        Returns:
            Recommended context size in tokens
        """
        prompt_tokens = cls.estimate_tokens(prompt, model_name)
        input_tokens = cls.estimate_tokens(user_input, model_name)

        total_input_tokens = prompt_tokens + input_tokens
        recommended_context = total_input_tokens + safety_margin

        # Use more reasonable context sizes for memory extraction
        # Most memory extraction tasks need much less than 32k tokens
        if recommended_context <= 1024:
            return 1024
        elif recommended_context <= 2048:
            return 2048
        elif recommended_context <= 4096:
            return 4096
        elif recommended_context <= 8192:
            return 8192
        elif recommended_context <= 16384:
            return 16384
        else:
            # For very large inputs, round up to 8K boundaries instead of 32K
            return ((recommended_context + 8191) // 8192) * 8192


def get_token_counts_for_prompts(settings) -> dict:
    """
    Calculate token counts for all prompts in settings.

    Args:
        settings: LLMSettings object

    Returns:
        Dictionary with token counts for each prompt
    """
    model_name = getattr(settings, "extraction_model", "")

    return {
        "memory_extraction_prompt": TokenCounter.estimate_tokens(
            settings.memory_extraction_prompt, model_name
        ),
        "memory_search_prompt": TokenCounter.estimate_tokens(
            settings.memory_search_prompt, model_name
        ),
        "semantic_connection_prompt": TokenCounter.estimate_tokens(
            settings.semantic_connection_prompt, model_name
        ),
        "memory_summarization_prompt": TokenCounter.estimate_tokens(
            settings.memory_summarization_prompt, model_name
        ),
    }
