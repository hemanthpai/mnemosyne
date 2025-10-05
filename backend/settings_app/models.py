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

    # Memory quality filtering
    memory_quality_threshold = models.FloatField(
        default=0.35,
        help_text="Minimum score threshold for including memories in results (0.0-1.0). Memories below this score are filtered out.",
    )

    # Memory extraction prompt
    memory_extraction_prompt = models.TextField(
        default="""Extract memories from the conversation for future AI assistant use. Extract comprehensive information including relationships, preferences, skills, experiences, and emotions.

**RULES:**
1. Always extract multiple memories - zero extractions is unacceptable
2. Extract names, relationships, preferences, skills, experiences
3. Use descriptive, searchable tags
4. Extract both explicit and implicit information

**OUTPUT:** JSON array only: `[{"content": "...", "tags": [...]}]`

**EXTRACTION FOCUS:**
- Names and relationships (friends, family, colleagues)
- Preferences (likes, dislikes, wants, needs)
- Skills and knowledge gaps
- Experiences and activities
- Emotional context and reactions

**TAGGING:** Use specific and general tags including:
- Subject matter (music, cooking, etc.)
- Emotions (excited, frustrated, etc.)
- Relationships (friend, family, sarah, etc.)
- Skills (good_at, struggles_with, etc.)
- Domains (personal, professional, etc.)

**EXAMPLES:**
"I loved Radiohead at Coachella" →
[{"content": "User loved Radiohead's performance at Coachella", "tags": ["music", "radiohead", "coachella", "festival", "loved", "concerts"]}, {"content": "User attends music festivals", "tags": ["music", "festivals", "live_music", "experiences"]}]

"My friend Sarah and I went to that new Italian restaurant" →
[{"content": "User has a friend named Sarah", "tags": ["relationships", "friend", "sarah", "social"]}, {"content": "User went to new Italian restaurant with Sarah", "tags": ["dining", "italian_food", "restaurant", "social_dining", "sarah"]}]"""
    )

    # Memory search prompt
    memory_search_prompt = models.TextField(
        default="""Generate search queries to find relevant user memories for an AI assistant. Always generate multiple comprehensive queries covering different angles.

**SEARCH TYPES:**
- "direct": Explicit matches to user's request
- "semantic": Related concepts and themes
- "experiential": Past experiences that inform preferences
- "contextual": Situational relevance
- "interest": General interests that connect

**OUTPUT:** JSON array only: `[{"search_query": "...", "search_type": "..."}]`

**SEARCH STRATEGY:**
1. Search for names mentioned (always include specific names)
2. Search for direct topic matches
3. Search for related experiences and preferences
4. Search for broader interests and skills
5. Generate 5-10 queries minimum

**EXAMPLES:**
"Help me create a playlist" →
[{"search_query": "favorite music", "search_type": "direct"}, {"search_query": "artists mentioned", "search_type": "direct"}, {"search_query": "concerts attended", "search_type": "experiential"}, {"search_query": "music festivals", "search_type": "experiential"}, {"search_query": "entertainment preferences", "search_type": "semantic"}]

"Recommend books for Sarah" →
[{"search_query": "sarah", "search_type": "direct"}, {"search_query": "books read", "search_type": "direct"}, {"search_query": "reading preferences", "search_type": "direct"}, {"search_query": "academic interests", "search_type": "semantic"}, {"search_query": "hobbies interests", "search_type": "interest"}]"""
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
        default="""Analyze the provided memories and create a focused summary that helps the AI assistant answer the user's query. Focus on actionable context, relationships, preferences, and patterns.

**GOAL:** Extract the most relevant information that directly helps answer the user's query. Focus on what the assistant needs to know to provide personalized, helpful responses.

**OUTPUT:** JSON object only: `{"summary": "..."}`

The summary should contain:
- Key preferences, relationships, and experiences relevant to the query
- Important context that helps understand the user's situation
- Patterns across memories that inform decision-making
- Specific facts that directly address the query

**ANALYSIS FOCUS:**
- Preferences (likes, dislikes, needs, wants)
- Relationships and social connections
- Skills, knowledge gaps, and experiences
- Historical patterns and behaviors
- Emotional context and concerns

**EXAMPLES:**
Query: "Help me create a playlist"
Memories: User loved Radiohead at Coachella, enjoys alternative/rock, prefers high-energy live performances
{"summary": "User has strong preferences for alternative/rock music, particularly Radiohead, and values high-energy, authentic performances. Their musical taste is informed by live festival experiences like Coachella, suggesting they appreciate established artists and festival-quality music."}

Query: "Help with my wisdom teeth decision"
Memories: User has impacted wisdom teeth, prefers minimally invasive procedures, concerned about pain/recovery, family history of dental complications
{"summary": "User has impacted wisdom teeth requiring treatment and strongly prefers minimally invasive dental procedures. They have expressed concerns about pain management and recovery time, with a family history of dental complications that influences their cautious approach to dental decisions."}"""
    )

    # Import Settings
    max_import_file_size_mb = models.IntegerField(
        default=500,
        help_text="Maximum file size for Open WebUI database imports (in MB)"
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
