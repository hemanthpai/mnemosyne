from django.db import models
from django.template import Context, Template


class LLMSettings(models.Model):
    PROVIDER_CHOICES = [
        ("openai", "OpenAI"),
        ("openai_compatible", "OpenAI Compatible"),
        ("ollama", "Ollama"),
    ]

    # Memory extraction LLM settings
    extraction_endpoint_url = models.URLField(default="http://localhost:11434")
    extraction_model = models.CharField(max_length=200, default="llama3")
    extraction_provider_type = models.CharField(
        max_length=20, choices=PROVIDER_CHOICES, default="ollama"
    )
    extraction_endpoint_api_key = models.CharField(
        blank=True, null=True, default="none"
    )
    extraction_timeout = models.IntegerField(default=30)  # seconds

    # Embeddings settings
    embeddings_endpoint_url = models.URLField(default="http://localhost:11434")
    embeddings_model = models.CharField(max_length=200, default="mxbai-embed-large")
    embeddings_provider_type = models.CharField(
        max_length=20, choices=PROVIDER_CHOICES, default="ollama"
    )
    embeddings_endpoint_api_key = models.CharField(
        blank=True, null=True, default="none"
    )
    embeddings_timeout = models.IntegerField(default=30)  # seconds

    memory_extraction_prompt = models.TextField(
        default="""You are an automated JSON data extraction system. Your ONLY function is to identify user-specific, persistent facts, preferences, goals, relationships, or interests from the user's messages and output them STRICTLY as a JSON array of operations.

**ABSOLUTE OUTPUT REQUIREMENT: FAILURE TO COMPLY WILL BREAK THE SYSTEM.**
1.  Your **ENTIRE** response **MUST** be **ONLY** a valid JSON array starting with `[` and ending with `]`. 
2.  **NO EXTRA TEXT**: Do **NOT** include **ANY** text, explanations, greetings, apologies, notes, or markdown formatting (like ```json) before or after the JSON array. 
3.  **ARRAY ALWAYS**: Even if you find only one memory, it **MUST** be enclosed in an array: `[{"operation": ...}]`. Do **NOT** output a single JSON object `{...}`.
4.  **EMPTY ARRAY**: If NO relevant user-specific memories are found, output **ONLY** an empty JSON array: `[]`.

**JSON OBJECT STRUCTURE (Each element in the array):**
*   Each element **MUST** be a JSON object: `{"operation": "NEW", "content": "...", "tags": ["..."], "memory_bank": "...", "confidence": float}`
*   **confidence**: You **MUST** include a confidence score (float between 0.0 and 1.0) indicating certainty that the extracted text is a persistent user fact/preference. High confidence (0.8-1.0) for direct statements, lower (0.5-0.7) for inferences or less certain preferences.
*   **memory_bank**: You **MUST** include a `memory_bank` field, choosing from: "General", "Personal", "Work". Default to "General" if unsure.
*   **tags**: You **MUST** include a `tags` field with a list of relevant tags from: [{{ memory_categories_json }}].

**INFORMATION TO EXTRACT (User-Specific ONLY):**
*   **Categories to focus on:** {{ memory_categories_list }}

**RULES (Reiteration - Critical):**
+1. **JSON ARRAY ONLY**: `[`...`]` - Nothing else!
+2. **CONFIDENCE REQUIRED**: Every object needs a `"confidence": float` field.
+3. **MEMORY BANK REQUIRED**: Every object needs a `"memory_bank": "..."` field.
+4. **TAGS REQUIRED**: Every object needs a `"tags": [...]` field with tags from: [{{ memory_categories_json }}].
+5. **USER INFO ONLY**: Discard trivia, questions *to* the AI, temporary thoughts.

**FAILURE EXAMPLES (DO NOT DO THIS):**
*   `Okay, here is the JSON: [...]` <-- INVALID (extra text)
*   ` ```json
[{"operation": ...}]
``` ` <-- INVALID (markdown)
*   `{"memories": [...]}` <-- INVALID (not an array)
*   `{"operation": ...}` <-- INVALID (not in an array)
*   `[{"operation": ..., "content": ..., "tags": [...]}]` <-- INVALID (missing confidence/bank)

**GOOD EXAMPLE OUTPUT (Strictly adhere to this):**
```
[
  {
    "operation": "NEW",
    "content": "User has been a software engineer for 8 years",
    "tags": ["identity", "behavior"],
    "memory_bank": "Work",
    "confidence": 0.95
  },
  {
    "operation": "NEW",
    "content": "User has a cat named Whiskers",
    "tags": ["relationship", "possession"],
    "memory_bank": "Personal",
    "confidence": 0.9
  },
  {
    "operation": "NEW",
    "content": "User prefers working remotely",
    "tags": ["preference", "behavior"],
    "memory_bank": "Work",
    "confidence": 0.7
  },
  {
    "operation": "NEW",
    "content": "User's favorite book might be The Hitchhiker's Guide to the Galaxy",
    "tags": ["preference"],
    "memory_bank": "Personal",
    "confidence": 0.6
  }
]
```

Analyze the following user message(s) and provide **ONLY** the JSON array output. 
Double-check your response starts with `[` and ends with `]` and contains **NO** other text whatsoever.""",
    )

    memory_search_prompt = models.TextField(
        default="""
You are a memory search system. Your ONLY function is to generate search queries to find relevant user memories based on the provided user message.
**ABSOLUTE OUTPUT REQUIREMENT: FAILURE TO COMPLY WILL BREAK THE SYSTEM.**
1. Your **ENTIRE** response **MUST** be **ONLY** a valid JSON array starting with `[]` and ending with `]`.
2. **NO EXTRA TEXT**: Do **NOT** include **ANY** text, explanations, greetings, apologies, notes, or markdown formatting (like ```json) before or after the JSON object.
3. **ARRAY ALWAYS**: Even if you find only one relevant query, it **MUST** be enclosed in an array: `[{"search_query": "...", "tags": [...] }]`. Do **NOT** output a single JSON object `{...}`.
4. **EMPTY OBJECT**: If there are NO relevant queries, output **ONLY** an empty JSON object: `{}`.

**JSON OBJECT STRUCTURE**: Each element in the array **MUST** be a JSON object with the following fields:
1. **SEARCH QUERY**: The object **MUST** contain a `search_query` field with a string that is a concise, relevant search query based on the user message.
2. **CONFIDENCE**: The object **MUST** contain a `confidence` field (float between 0.0 and 1.0) indicating how confident you are that this query will yield memories relevant to the user's message.

**HOW TO GENERATE SEARCH QUERY:**
*   Memories are stored and tagged with specific categories. Here are the categories: [{{ memory_categories_list }}].
*   Analyze the user message(s) and create a concise search query that captures the essence of what to look for in the user's memories.
*   Use keywords that are likely to match existing memory entries.
*   If the user message is vague or contains multiple topics, create a query for each distinct topic.
*   For each query, assign a confidence score based on how likely it is to yield memories relevant to the user's message.
*   The retrieved memories will undergo additional filtering in the context of the user's message, in a subsequent step. So, your queries should be broad enough to capture as many relevant memories as possible but specific enough to avoid irrelevant results. 

**EXAMPLES OF HOW TO GENERATE SEARCH QUERIES:**
*   If the user message is "I am bored, can you suggest something to do?", you might generate:
    `{"search_query": "User's favorite activities", "confidence": 1.0}`
    `{"search_query": "User's hobbies and interests", "confidence": 1.0}`
    `{"search_query": "User's recent activities", "confidence": 0.8}`
    `{"search_query": "User's preferred ways to spend free time", "confidence": 0.9}`
    `{"search_query": "User's favorite pastimes", "confidence": 0.85}`
*   If the user message is "Suggest a good book to read next", you might generate:
    `{"search_query": "Topics user is interested in", "confidence": 1.0}`
    `{"search_query": "User's favorite genres", "confidence": 0.9}`
    `{"search_query": "User's favorite authors", "confidence": 1.0}`
    `{"search_query": "User's reading preferences", "confidence": 0.9}`
    `{"search_query": "User's personal goals", "confidence": 0.8}`
    `{"search_query": "User's professional goals", "confidence": 0.85}`
    `{"search_query": "User's health goals", "confidence": 0.8}`

**EXAMPLES OF HOW MEMORIES MIGHT BE STORED:**
* User enjoys hiking in the mountains.
* User's favorite color is blue.
* User has a pet dog named Max.
* User's goal is to learn a new programming language this year.
* User's favorite vacation destination is Hawaii.
* User has a close relationship with their sister.
* User's preferred method of communication is email.

**EXAMPLES OF GOOD SEARCH QUERIES:**
*   `{"search_query": "User's favorite hobbies", "confidence": 0.9}`
*   `{"search_query": "User's recent travel experiences", "confidence": 0.8}`
*   `{"search_query": "User's professional background", "confidence": 0.85}`
*   `{"search_query": "User's family relationships", "confidence": 0.95}`
*   `{"search_query": "User's favorite books", "confidence": 0.7}`
*   `{"search_query": "User's goals for the next year", "confidence": 0.75}`
*   `{"search_query": "User's interests in technology", "confidence": 0.8}`
*   `{"search_query": "User's recent achievements", "confidence": 0.9}`
*   `{"search_query": "User's preferred communication style", "confidence": 0.6}`
*   `{"search_query": "User's favorite foods", "confidence": 0.7}`
*   `{"search_query": "User's opinions on current events", "confidence": 0.65}`

** RULES (Reiteration - Critical):**
+1. **JSON ARRAY ONLY**: `[]` - Nothing else!
+2. **SEARCH QUERY REQUIRED**: Every object needs a `"search_query": "..."` field.
+3. **CONFIDENCE REQUIRED**: Every object needs a `"confidence": float` field.

** FAILURE EXAMPLES (DO NOT DO THIS):**
*   `Okay, here is the JSON: [...]` <-- INVALID (extra text)
*   ` ```json
[{"search_query": ...}]
``` ` <-- INVALID (markdown)
*   `{"queries": [...]}` <-- INVALID (not an array)
*   `{"search_query": ...}` <-- INVALID (not in an array)

Analyze the following user message(s) and provide **ONLY** the JSON array output.
Double-check your response starts with `[` and ends with `]` and contains **NO** other text whatsoever.
"""
    )

    # Memory extraction settings
    memory_categories = models.TextField(
        default="identity,behavior,preference,goal,relationship,possession",
        help_text="Comma-separated list of memory categories",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM Settings"
        verbose_name_plural = "LLM Settings"

    def __str__(self):
        return f"LLM Settings (Updated: {self.updated_at})"

    def get_memory_categories_list(self):
        """Return memory categories as a list"""
        if self.memory_categories:
            return [
                cat.strip() for cat in self.memory_categories.split(",") if cat.strip()
            ]
        return []

    def set_memory_categories_list(self, categories):
        """Set memory categories from a list"""
        self.memory_categories = ",".join(categories)

    @classmethod
    def get_settings(cls):
        """Get the current settings, creating default if none exist"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

    def get_memory_extraction_prompt_rendered(self):
        """
        Get the memory extraction prompt with Django template rendering
        """
        categories = self.get_memory_categories_list()

        template = Template(self.memory_extraction_prompt)
        context = Context(
            {
                "memory_categories": categories,
                "memory_categories_json": ", ".join([f'"{cat}"' for cat in categories]),
                "memory_categories_list": ", ".join(categories),
            }
        )

        return template.render(context)

    def get_memory_search_prompt_rendered(self):
        """
        Get the memory search prompt with Django template rendering
        """
        categories = self.get_memory_categories_list()

        template = Template(self.memory_search_prompt)
        context = Context(
            {
                "memory_categories": categories,
                "memory_categories_json": ", ".join([f'"{cat}"' for cat in categories]),
                "memory_categories_list": ", ".join(categories),
            }
        )

        return template.render(context)

    def get_available_template_variables(self):
        """
        Get list of available template variables for the prompt
        """
        return [
            "{{ memory_categories_json }} - JSON-formatted list of memory categories",
            "{{ memory_categories_list }} - Comma-separated list of memory categories",
            "{{ memory_categories }} - Python list of memory categories",
        ]

    def get_template_preview(self):
        """
        Get a preview of the rendered template with current data
        """
        try:
            return self.get_memory_extraction_prompt_rendered()[:500] + "..."
        except Exception as e:
            return f"Template error: {str(e)}"
