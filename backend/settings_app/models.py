from django.db import models


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

    # LLM Generation Parameters
    llm_temperature = models.FloatField(
        default=0.6, help_text="Controls randomness (0.0-2.0)"
    )
    llm_top_p = models.FloatField(
        default=0.95, help_text="Controls diversity via nucleus sampling (0.0-1.0)"
    )
    llm_top_k = models.IntegerField(
        default=20, help_text="Controls diversity via top-k sampling"
    )
    llm_max_tokens = models.IntegerField(
        default=2048, help_text="Maximum tokens to generate"
    )

    # Search Configuration
    enable_semantic_connections = models.BooleanField(
        default=True,
        help_text="Enable semantic connection enhancement for memory search",
    )
    semantic_enhancement_threshold = models.IntegerField(
        default=3,
        help_text="Minimum number of initial results needed to trigger semantic enhancement",
    )

    # Search Type Thresholds
    search_threshold_direct = models.FloatField(
        default=0.7, help_text="Similarity threshold for direct searches"
    )
    search_threshold_semantic = models.FloatField(
        default=0.5, help_text="Similarity threshold for semantic searches"
    )
    search_threshold_experiential = models.FloatField(
        default=0.6, help_text="Similarity threshold for experiential searches"
    )
    search_threshold_contextual = models.FloatField(
        default=0.4, help_text="Similarity threshold for contextual searches"
    )
    search_threshold_interest = models.FloatField(
        default=0.5, help_text="Similarity threshold for interest searches"
    )

    # Memory extraction prompt
    memory_extraction_prompt = models.TextField(
        default="""You are an automated memory extraction system. Extract user-specific facts, preferences, experiences, and insights as a JSON array.

**OUTPUT REQUIREMENT:**
Your response must be ONLY a valid JSON array: `[{"content": "...", "tags": [...], "confidence": float, "context": "...", "connections": [...]}]`

**JSON STRUCTURE:**
- **content**: The extracted memory/fact
- **tags**: Flexible, descriptive tags that capture ALL aspects (not limited to predefined categories)
- **confidence**: 0.0-1.0 confidence score
- **context**: Brief description of the situation/context where this was mentioned
- **connections**: List of broader topics/themes this memory relates to

**TAGGING GUIDELINES:**
- Use specific AND general tags
- Include subject matter tags (music, physics, cooking, etc.)
- Include preference indicators (loves, dislikes, wants, etc.)
- Include experience types (attended, performed, learned, etc.)
- Include emotional context (excited, disappointed, curious, etc.)
- Include domain tags (personal, professional, academic, creative, etc.) if relevant
- Think about what future queries might want to find this memory

**EXAMPLES:**
If user says "I loved Radiohead's performance at Coachella":
```json
[{
  "content": "User loved Radiohead's performance at Coachella",
  "tags": ["music", "radiohead", "coachella", "festival", "live_performance", "rock", "alternative", "favorite_artist", "concert_experience", "loved", "personal", "entertainment"],
  "confidence": 0.95,
  "context": "Discussing music festival experience",
  "connections": ["music_taste", "live_music", "festival_experiences", "favorite_bands", "entertainment_preferences"]
}]
```

If user says "I'm fascinated by quantum entanglement":
```json
[{
  "content": "User is fascinated by quantum entanglement",
  "tags": ["physics", "quantum_physics", "quantum_entanglement", "science", "fascinated", "academic_interest", "theoretical_physics", "learning", "academic", "research"],
  "confidence": 0.9,
  "context": "Expressing scientific interests",
  "connections": ["science_interests", "physics_topics", "learning_preferences", "intellectual_curiosity", "book_recommendations", "educational_content"]
}]
```

Analyze the user message and extract memories with rich, flexible tagging."""
    )

    # Memory search prompt
    memory_search_prompt = models.TextField(
        default="""You are an intelligent memory search system. Generate search queries that capture both direct and indirect connections to find relevant user memories.

**OUTPUT REQUIREMENT:**
Respond with ONLY a JSON array: `[{"search_query": "...", "confidence": float, "search_type": "...", "rationale": "..."}]`

**SEARCH STRATEGY:**
1. **Direct queries**: Explicit matches for the user's request
2. **Semantic queries**: Related concepts and broader themes  
3. **Contextual queries**: Situations where this topic might be relevant
4. **Experience queries**: Past experiences that inform preferences
5. **Interest queries**: General interests that connect to the request

**SEARCH TYPES:**
- "direct": Explicit match to request
- "semantic": Related concepts/themes
- "experiential": Past experiences that inform preferences
- "contextual": Situational relevance
- "interest": General interests that connect

**JSON STRUCTURE:**
- **search_query**: The query to find relevant memories
- **confidence**: 0.0-1.0 confidence score for relevance
- **search_type**: Type of search (direct, semantic, experiential, contextual, interest)
- **rationale**: Explanation of why this query is relevant

**EXAMPLES:**

User asks: "Help me create a playlist"
```json
[
  {"search_query": "user's favorite music", "confidence": 1.0, "search_type": "direct", "rationale": "Direct musical preferences"},
  {"search_query": "user's favorite artists", "confidence": 1.0, "search_type": "direct", "rationale": "Specific artist preferences"},
  {"search_query": "concerts user attended", "confidence": 0.8, "search_type": "experiential", "rationale": "Live music experiences show preferences"},
  {"search_query": "music user loved", "confidence": 0.9, "search_type": "semantic", "rationale": "Any music they expressed enjoying"},
  {"search_query": "festivals user went to", "confidence": 0.7, "search_type": "experiential", "rationale": "Festival experiences reveal music taste"},
  {"search_query": "songs user mentioned", "confidence": 0.8, "search_type": "semantic", "rationale": "Any songs they've referenced"},
  {"search_query": "user's mood preferences", "confidence": 0.6, "search_type": "contextual", "rationale": "Mood affects playlist preferences"}
]
```

User asks: "Recommend some books"
```json
[
  {"search_query": "books user read", "confidence": 1.0, "search_type": "direct", "rationale": "Reading history shows preferences"},
  {"search_query": "user's academic interests", "confidence": 0.8, "search_type": "semantic", "rationale": "Academic interests suggest book topics"},
  {"search_query": "subjects user is fascinated by", "confidence": 0.9, "search_type": "semantic", "rationale": "Fascination indicates reading interest"},
  {"search_query": "user's hobbies", "confidence": 0.7, "search_type": "contextual", "rationale": "Hobbies suggest relevant book topics"},
  {"search_query": "topics user wants to learn", "confidence": 0.8, "search_type": "semantic", "rationale": "Learning goals indicate book interests"},
  {"search_query": "user's professional field", "confidence": 0.6, "search_type": "contextual", "rationale": "Career suggests relevant reading"},
  {"search_query": "sciences user mentioned", "confidence": 0.7, "search_type": "semantic", "rationale": "Scientific interests suggest book topics"}
]
```

Generate comprehensive search queries that find both obvious and subtle connections."""
    )

    # Semantic connection analysis prompt
    semantic_connection_prompt = models.TextField(
        default="""Analyze the found memories against the user's query to identify subtle semantic connections that might reveal additional relevant memories.

**TASK:** 
Determine if there are subtle connections between these memories and the user's query that suggest additional search terms. Look for:
1. Implicit interests revealed by the memories
2. Related topics that weren't directly searched
3. Contextual connections (e.g., if user went to a music festival, they might have favorite artists from that event)
4. Experience-based connections (e.g., academic background suggesting reading interests)

**OUTPUT REQUIREMENT:**
Respond with ONLY a JSON object with:
- **has_connections**: boolean indicating if connections were found
- **additional_searches**: array of search objects with search_query, rationale, and confidence
- **reasoning**: explanation of the analysis"""
    )

    # Memory summarization prompt
    memory_summarization_prompt = models.TextField(
        default="""You are an expert memory analyst tasked with summarizing only the relevant memories based on a user's query. 
Your **ONLY** goal is to extract actionable context from the provided memories that can help answer or respond to the user's query.

**TASK:**
1. From the provided memories, first identify all the memories that are relevant to the user's query.
2. Then, create a comprehensive summary of only the relevant memories, focusing on actionable context.
3. Any memory that does not provide actionable context should be excluded from the summary.

**ANALYSIS REQUIREMENTS:**
- Focus on actionable insights that directly address the user's query  
- Include supporting context and background information
- Identify patterns across multiple memories
- Classify memories by relevance level (high/moderate/contextual)

**OUTPUT REQUIREMENT:**
Respond with ONLY a JSON object with:
- **summary**: comprehensive text summary
- **key_points**: array of key insights
- **relevant_context**: supporting context information
- **confidence**: confidence score (0.0-1.0)
- **memory_usage**: object with total_memories, highly_relevant, moderately_relevant, context_relevant counts"""
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM Settings"
        verbose_name_plural = "LLM Settings"

    def __str__(self):
        return f"LLM Settings (Updated: {self.updated_at})"

    @classmethod
    def get_settings(cls):
        """Get the current settings, creating default if none exist"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
