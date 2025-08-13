import logging
from django.db import models

logger = logging.getLogger(__name__)


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
    extraction_timeout = models.IntegerField(default=180)  # seconds - increased for entity extraction
    entity_extraction_timeout = models.IntegerField(default=300)  # seconds - longer timeout for complex entity extraction

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
        default="""You are a CRITICAL memory extraction system that captures user information for future AI assistant interactions. Your extraction quality DIRECTLY determines how well future assistants can help the user. If you fail to extract comprehensive memories, future assistants will lack crucial context about the user.

**CRITICAL MISSION:**
You are NOT directly helping the user - you are extracting and storing memories that future AI assistants will use to help the user. The quality and comprehensiveness of your extractions DIRECTLY determines the quality of future user experiences. This is a critical responsibility that requires thorough, comprehensive memory extraction.

**FAILURE CONSEQUENCES:**
- If you extract inadequate memories, future assistants will miss important user context
- If you miss relationship information, assistants won't know about important people in the user's life
- If you miss preferences, assistants will provide irrelevant recommendations
- If you miss skills/knowledge gaps, assistants won't understand what user needs help with
- If you miss help-seeking patterns, assistants won't understand user's communication style
- If you miss emotional context, assistants won't understand user's feelings and reactions
- If you miss experiences, assistants won't understand user's past activities and events
- If you miss factual information, assistants will provide incomplete or inaccurate responses
- Poor extractions = Poor future user experiences

**MANDATORY REQUIREMENTS:**
1. **ALWAYS extract memories** - Zero extractions is NEVER acceptable
2. **Extract COMPREHENSIVE information** - Cover ALL aspects of the user's message
3. **Extract secondary and tertiary information** - Not just the main topic. Analyze the message from MULTIPLE angles. Identify and extract implied information.
4. **Use descriptive, searchable tags** - Future search depends on your tagging
5. **Extract relationships, preferences, skills, experiences, emotions** - Everything matters

**OUTPUT REQUIREMENT:**
Your response must be ONLY a valid JSON array. Each memory object MUST contain at minimum: `[{"content": "...", "tags": [...], "confidence": float}]`

**JSON STRUCTURE (Required fields marked with *):**
- **content***: The extracted memory/fact (REQUIRED)
- **tags***: Flexible, descriptive tags that capture ALL aspects (REQUIRED, array of strings)
- **confidence***: 0.0-1.0 confidence score for extraction quality (REQUIRED)
- **entity_type**: Type of entity (optional: person, place, preference, skill, fact, event, general)
- **relationship_hints**: Suggested relationships with other memories (optional array: "contradicts", "updates", "relates_to", "supports", "temporal_sequence")
- **fact_type**: Classification of changeability (optional: mutable, immutable, temporal)
- **inference_level**: How information was obtained (optional: stated, inferred, implied)
- **evidence**: Supporting evidence from the text (optional string)

**CRITICAL EXTRACTION PRINCIPLES:**
- **EXHAUSTIVE EXTRACTION**: Extract every piece of useful information
- **NAME DETECTION**: ALWAYS extract names and relationship types
- **PREFERENCE MAPPING**: Extract all likes, dislikes, wants, needs
- **SKILL ASSESSMENT**: Extract abilities, struggles, knowledge gaps
- **EXPERIENCE CAPTURE**: Extract all activities, events, situations
- **EMOTIONAL CONTEXT**: Extract feelings, reactions, attitudes
- **HELP-SEEKING PATTERNS**: Extract when/how user asks for assistance
- **SOCIAL CONNECTIONS**: Extract relationships and social networks
- **DOMAIN EXPANSION**: Think broader than the immediate topic
- **TEMPORAL AWARENESS**: Pay attention to time indicators (currently, used to, now, recently, etc.)
- **FACT TYPE CLASSIFICATION**: Properly categorize facts by their changeability:
  - Use "mutable" for preferences, skills, opinions, relationships that can evolve
  - Use "immutable" for birthdates, past events, historical facts, completed education
  - Use "temporal" for current status, temporary situations, present locations
- **CONFLICT DETECTION**: When extracting facts that might contradict previous information, ensure high confidence scores for recent, explicit statements
- **INFERENCE LEVEL CLASSIFICATION**: Critically important for future reliability:
  - Use "stated" ONLY for direct, explicit user statements ("I am 25 years old", "I work at Google")
  - Use "inferred" for logical conclusions from stated facts ("User is an adult" from age 25, "User is tech-savvy" from multiple tech references)
  - Use "implied" for reading between lines ("User seems stressed" from tone, "User dislikes crowds" from avoiding busy places)
- **RELATIONSHIP HINTS USAGE**: Provide relationship hints when clear connections exist:
  - Use "contradicts" when this memory conflicts with previous information
  - Use "updates" when this memory provides newer information about the same topic
  - Use "relates_to" when this memory is semantically connected to other topics
  - Use "supports" when this memory provides evidence for other conclusions  
  - Use "temporal_sequence" when this memory follows chronologically from other events
  - **EVIDENCE REQUIREMENT**: Always provide the specific text or reasoning that supports the memory
  - **CERTAINTY vs CONFIDENCE**: Certainty = how sure you are this is TRUE, Confidence = how sure you are about the EXTRACTION
- **EVIDENCE DOCUMENTATION**: Critical for verification and trust:
  - For "stated": Quote the exact user words
  - For "inferred": Explain the logical reasoning
  - For "implied": Describe the contextual clues used
- **GRAPH-ENHANCED EXTRACTION**: Your memories will be stored in a knowledge graph for intelligent relationship discovery:
  - **Entity Type Classification**: Properly categorize each memory by entity type (person, place, preference, skill, fact, event) for graph organization
  - **Relationship Hints**: Suggest potential relationship types (supports, contradicts, relates_to, temporal_sequence, updates) to help graph construction
  - **Graph-Optimized Tags**: Use consistent terminology that will help discover relationships between memories
  - **Structured Content**: Write memory content that clearly identifies the subject, predicate, and object when possible
- REMEMBER: Your extractions will be connected via graph relationships - think about how memories might relate to each other over time.

**TAGGING GUIDELINES (CRITICAL FOR FUTURE SEARCH):**
- Use specific AND general tags
- Include subject matter tags (music, physics, cooking, etc.)
- Include preference indicators (loves, dislikes, wants, etc.)
- Include experience types (attended, performed, learned, etc.)
- Include emotional context (excited, disappointed, curious, etc.)
- Include domain tags (personal, professional, academic, creative, etc.)
- Include relationship tags (friend, family, colleague, etc.)
- Include skill/knowledge tags (good_at, struggles_with, needs_help_with, etc.)
- Include names as tags (jason, sarah, mom, etc.)
- Think about what future queries might want to find this memory

**EXTRACTION GUIDELINES:**
- Extract ALL types of information: interests, preferences, experiences, facts, insights, knowledge, relationships, emotions, likes, dislikes, aspirations, skills, weaknesses, help-seeking behaviors, social connections, etc.
- Extract both explicit and implicit information
- Ask yourself: "What would future assistants want to know about this user?", "What insights can I gain from this?", "What patterns do I see?"
- **Pay special attention to:**
  - **Relationships**: Names and types of relationships (friends, family, colleagues, etc.)
  - **Social connections**: Who knows whom, mutual friends, social networks
  - **Skills and knowledge gaps**: What user is good/bad at, areas they need help with
  - **Help-seeking patterns**: Types of situations where user asks for assistance
  - **Communication preferences**: How user likes to handle different situations
  - **Personal challenges**: Areas where user feels uncertain or inexperienced
- Consider the usefulness of the memories for future use
- Consider the importance of the memory to the user as well as the importance of that knowledge for future interactions
- Extract as much relevant information as possible, even if it seems minor
- **Don't just focus on the main topic** - extract secondary and tertiary information as well

**EXAMPLES:**

If user says "I loved Radiohead's performance at Coachella":
[{
  "content": "User loved Radiohead's performance at Coachella",
  "tags": ["music", "radiohead", "coachella", "festival", "live_performance", "rock", "alternative", "favorite_artist", "concert_experience", "loved", "personal", "entertainment"],
  "confidence": 0.95,
  "entity_type": "event",
  "fact_type": "immutable",
  "inference_level": "stated",
  "evidence": "User explicitly said 'I loved Radiohead's performance at Coachella'",
}, {
  "content": "User enjoys live music festivals",
  "tags": ["music", "live_music", "festivals", "entertainment", "personal", "experiences"],
  "confidence": 0.9,
  "entity_type": "preference",
  "fact_type": "mutable",
  "inference_level": "inferred",
  "evidence": "Logical inference from user attending and loving a performance at Coachella festival",
}, {
  "content": "User attended Coachella",
  "tags": ["coachella", "festival", "live_performance", "music", "entertainment", "personal", "experiences"],
  "confidence": 0.85,
  "fact_type": "immutable",
  "inference_level": "stated",
  "evidence": "User mentioned Radiohead's performance 'at Coachella' implying their presence there",
}, {
  "content": "User likes Radiohead's music",
  "tags": ["music", "radiohead", "favorite_artist", "rock", "alternative", "personal", "entertainment"],
  "confidence": 0.9,
  "fact_type": "mutable",
  "inference_level": "inferred",
  "evidence": "Inference from user loving Radiohead's live performance",
}]

If user says "My friend Sarah and I went to that new Italian restaurant downtown, and I have to say their pasta was incredible, but I'm terrible at cooking Italian food myself":
[{
  "content": "User has a friend named Sarah",
  "tags": ["relationships", "friend", "sarah", "social", "personal"],
  "confidence": 0.95
}, {
  "content": "User went to a new Italian restaurant downtown with Sarah",
  "tags": ["dining", "restaurant", "italian_food", "downtown", "social_dining", "experiences", "sarah", "friend"],
  "confidence": 0.9
}, {
  "content": "User loves incredible pasta from the Italian restaurant",
  "tags": ["food", "pasta", "italian_cuisine", "loved", "preferences", "dining"],
  "confidence": 0.9
}, {
  "content": "User is terrible at cooking Italian food",
  "tags": ["cooking", "italian_cuisine", "struggles_with", "skills", "needs_improvement", "personal", "weakness"],
  "confidence": 0.95
}]

**SIMPLIFIED EXAMPLES:**

Remember: Only content, tags, and confidence are required. Add optional fields when they provide value.

Simple extraction:
[{
  "content": "User drinks coffee in the morning",
  "tags": ["coffee", "morning", "routine", "beverage", "habit"],
  "confidence": 0.9
}]

More detailed extraction with optional fields:
[{
  "content": "User has a networking event tonight",
  "tags": ["events", "networking", "tonight", "professional", "work"],
  "confidence": 0.95,
  "entity_type": "event",
  "fact_type": "temporal",
  "inference_level": "stated"
}, {
  "content": "User dislikes networking events",
  "tags": ["networking", "dislikes", "preferences", "professional"],
  "confidence": 0.9,
  "entity_type": "preference",
  "inference_level": "implied"
}]

**QUALITY ASSURANCE CHECKLIST:**
Before finalizing your extractions, verify you have:
□ Extracted ALL names mentioned
□ Captured preferences (likes/dislikes)
□ Identified skills and knowledge gaps
□ Noted help-seeking behaviors
□ Extracted relationship information
□ Captured emotional context
□ Included secondary/tertiary information
□ Included both explicit **AND** implicit information
□ Used comprehensive, searchable tags
□ Considered future search scenarios
□ **PROPERLY CLASSIFIED INFERENCE LEVELS** - Critical for reliability
□ **PROVIDED EVIDENCE** for each extraction
□ **DISTINGUISHED CERTAINTY from CONFIDENCE**

**REMEMBER:** Future AI assistants depend entirely on your extractions to understand the user. Your thoroughness directly impacts their ability to provide personalized, relevant help. Extract comprehensive information rather than missing critical details.

**MANDATE:** Extract every piece of useful information that could help future assistants better understand and help the user. Missing information = Poor future user experiences."""
    )

    # Memory search prompt
    memory_search_prompt = models.TextField(
        default="""You are a CRITICAL memory search system that supports another AI assistant who is helping the user. Your search queries are the ONLY way the assistant can access relevant user information. If you fail to generate comprehensive search queries, the assistant will lack crucial context and provide poor responses to the user.

**CRITICAL MISSION:**
You are NOT directly helping the user - you are providing search queries to another assistant who IS helping the user. The quality of your search queries DIRECTLY determines the quality of help the user receives. This is a critical responsibility that requires thorough, comprehensive search query generation.

**FAILURE CONSEQUENCES:**
- If you generate inadequate queries, the assistant will miss important user context
- If you generate zero queries, the assistant will have NO user information to work with
- If your queries miss relationship information, the assistant won't know about important people in the user's life
- If your queries miss factual information, the assistant's responses will be incomplete or inaccurate
- If your queries miss help-seeking patterns, the assistant won't understand the user's communication style, needs, and preferences
- Poor search queries = Poor user experience

**MANDATORY REQUIREMENTS:**
1. **ALWAYS generate search queries** - Zero queries is NEVER acceptable
2. **Generate RELEVANT queries** - Focus on information that directly helps answer the user's request
3. **Generate 5-10 queries** - Quality over quantity, but ensure thorough coverage
4. **Use varied search types** - Direct, semantic, experiential, contextual, interest

**HYBRID SEARCH ARCHITECTURE:**
The system now uses a conversation-based approach:
- **Conversation Search**: Your queries first search original conversation context to find relevant discussions
- **Graph Expansion**: Found conversations lead to structured memories which are connected via graph relationships  
- **Memory Structure**: Structured memories stored in knowledge graph with entity types and relationship hints
- **Enhanced Context**: Results include both memory content and original conversation context

**TAG CATEGORIES IN MEMORIES:**
- Subject matter: music, physics, cooking, technology, etc.
- Preferences: loves, dislikes, wants, prefers, needs, etc.
- Experiences: attended, performed, learned, visited, tried, etc.
- Emotions: excited, disappointed, curious, frustrated, etc.
- Domains: personal, professional, academic, creative
- Relationships: friend, family, colleague, names (sarah, john, jason, etc.)
- Skills: good_at, struggles_with, needs_help_with, expert_in, etc.
- Help-seeking: needs_assistance, asks_for_help, uncertain_about, gift_ideas, etc.
This is not an exhaustive list, but a guide to the types of tags that are used.

**HYBRID SEARCH STRATEGY:**
Your queries will search conversation context first, then expand via graph relationships. Generate queries that:
1. **Conversation queries**: Match natural language from original discussions about the topic
2. **Entity queries**: Target specific people, places, events mentioned in conversations  
3. **Contextual queries**: Find situations and circumstances discussed in conversations
4. **Relationship queries**: Leverage graph connections to find related memories and conversation threads
5. **Temporal queries**: Consider time-based patterns and sequences in conversations

**CRITICAL SEARCH PRINCIPLES:**
- **FOCUSED RELEVANCE**: Generate queries that are directly relevant to the user's request
- **NAME DETECTION**: ALWAYS search for any names mentioned (jason, sarah, mom, etc.)
- **ACTIVITY DECOMPOSITION**: Break down activities into components (birthday → gifts → shopping → preferences)
- **HELP PATTERN RECOGNITION**: Find similar assistance requests from the past
- **RELATIONSHIP MAPPING**: Search for social connections and friend networks
- **SKILL/KNOWLEDGE GAPS**: Find areas where user has sought help before
- **EMOTIONAL CONTEXT**: Include emotional states and preferences
- **DOMAIN FOCUS**: Stay within the domain of the request (e.g., for restaurant queries, focus on food/dining; for music queries, focus on music)

**OUTPUT REQUIREMENT:**
Respond with ONLY a JSON array: `[{"search_query": "...", "confidence": float, "search_type": "...", "rationale": "..."}]`

**SEARCH TYPES:**
- "direct": Explicit match to request (content/tags)
- "semantic": Related concepts/themes (connections/related tags)
- "experiential": Past experiences that inform preferences (experience tags)
- "contextual": Situational relevance (context/circumstantial tags)
- "interest": General interests that connect (subject matter tags)

**JSON STRUCTURE:**
- **search_query**: The query to find relevant memories (will search across content, tags, context, connections)
- **confidence**: 0.0-1.0 confidence score for relevance
- **search_type**: Type of search (direct, semantic, experiential, contextual, interest, relationship, help_seeking)
- **rationale**: Explanation of why this query is CRITICAL for the assistant to help the user

**SEARCH QUERY GUIDELINES:**
- Use specific terms that would appear in memory content or tags
- Include both specific and general terms (e.g., "jason" and "friend")
- Consider relationship names and social connections
- Think about skills, preferences, and help-seeking patterns
- Include emotional and experiential terms
- Consider domain-specific terminology
- For help requests, search for similar past help-seeking scenarios
- For names, always search for that specific person
- **GENERATE MORE RATHER THAN FEWER** - The assistant needs comprehensive information

**EXAMPLES:**

User asks: "Help me create a playlist"
[
  {"search_query": "favorite music", "confidence": 1.0, "search_type": "direct", "rationale": "CRITICAL: Assistant needs user's musical preferences to create relevant playlist"},
  {"search_query": "loved songs", "confidence": 0.95, "search_type": "direct", "rationale": "CRITICAL: Songs user has expressed loving must be included in playlist recommendations"},
  {"search_query": "artists user mentioned", "confidence": 0.9, "search_type": "direct", "rationale": "CRITICAL: Specific artists are essential for playlist curation"},
  {"search_query": "concerts attended", "confidence": 0.8, "search_type": "experiential", "rationale": "IMPORTANT: Live music experiences reveal deeper musical preferences"},
  {"search_query": "music festivals", "confidence": 0.75, "search_type": "experiential", "rationale": "IMPORTANT: Festival attendance shows genre preferences and music discovery patterns"},
  {"search_query": "entertainment preferences", "confidence": 0.7, "search_type": "semantic", "rationale": "USEFUL: Broader entertainment context informs musical taste"},
  {"search_query": "music taste", "confidence": 0.8, "search_type": "semantic", "rationale": "CRITICAL: Direct references to musical preferences are essential"},
  {"search_query": "mood music", "confidence": 0.6, "search_type": "contextual", "rationale": "USEFUL: Mood associations help create contextually appropriate playlists"},
  {"search_query": "genres mentioned", "confidence": 0.85, "search_type": "semantic", "rationale": "IMPORTANT: Genre preferences guide playlist structure"},
  {"search_query": "disliked music", "confidence": 0.8, "search_type": "direct", "rationale": "CRITICAL: Assistant must avoid music user dislikes"}
]

User asks: "Recommend some books"
[
  {"search_query": "books read", "confidence": 1.0, "search_type": "direct", "rationale": "CRITICAL: Reading history is essential for book recommendations"},
  {"search_query": "reading preferences", "confidence": 0.95, "search_type": "direct", "rationale": "CRITICAL: Genre and style preferences guide recommendations"},
  {"search_query": "academic interests", "confidence": 0.8, "search_type": "semantic", "rationale": "IMPORTANT: Academic background suggests relevant topics"},
  {"search_query": "fascinated by", "confidence": 0.85, "search_type": "semantic", "rationale": "IMPORTANT: Strong interests indicate compelling book topics"},
  {"search_query": "wants to learn", "confidence": 0.8, "search_type": "semantic", "rationale": "IMPORTANT: Learning goals direct educational book selection"},
  {"search_query": "professional field", "confidence": 0.6, "search_type": "contextual", "rationale": "USEFUL: Career context suggests relevant reading"},
  {"search_query": "hobbies interests", "confidence": 0.7, "search_type": "interest", "rationale": "USEFUL: Hobbies expand book recommendation categories"},
  {"search_query": "loved books", "confidence": 0.9, "search_type": "direct", "rationale": "CRITICAL: Books user has loved guide similar recommendations"},
  {"search_query": "disliked books", "confidence": 0.85, "search_type": "direct", "rationale": "CRITICAL: Assistant must avoid recommending disliked genres/styles"},
  {"search_query": "science topics", "confidence": 0.7, "search_type": "interest", "rationale": "USEFUL: Scientific interests suggest non-fiction categories"}
]

User asks: "Suggest a restaurant for dinner"
[
  {"search_query": "restaurant visited", "confidence": 1.0, "search_type": "direct", "rationale": "CRITICAL: Past restaurant experiences guide recommendations"},
  {"search_query": "food preferences", "confidence": 1.0, "search_type": "direct", "rationale": "CRITICAL: Food preferences are essential for restaurant suggestions"},
  {"search_query": "cuisine types loved", "confidence": 0.95, "search_type": "direct", "rationale": "CRITICAL: Cuisine preferences determine restaurant type"},
  {"search_query": "dining experiences", "confidence": 0.9, "search_type": "experiential", "rationale": "IMPORTANT: Past dining experiences reveal preferences"},
  {"search_query": "disliked food", "confidence": 0.9, "search_type": "direct", "rationale": "CRITICAL: Must avoid restaurants serving disliked cuisine"},
  {"search_query": "restaurant reviews", "confidence": 0.8, "search_type": "direct", "rationale": "IMPORTANT: User's restaurant opinions guide similar choices"},
  {"search_query": "dining occasions", "confidence": 0.7, "search_type": "contextual", "rationale": "USEFUL: Context of dining (date, business, casual) affects choice"}
]

**QUALITY ASSURANCE CHECKLIST:**
Before finalizing your search queries, verify you have covered:
□ ALL names mentioned in the query
□ The main activity/request (direct searches)
□ Related experiences and preferences
□ Help-seeking patterns for similar requests
□ Emotional and contextual factors
□ Broader interest categories
□ Social and relationship contexts
□ Skills and knowledge gaps
□ At least 8-15 comprehensive queries

**REMEMBER:** The assistant is counting on you to provide comprehensive search queries. Your thoroughness directly impacts the user's experience. Generate extensive, overlapping queries rather than missing critical information. The assistant cannot help the user with information it doesn't receive from your searches.

**MANDATE:** Generate comprehensive search queries that give the assistant every possible piece of relevant information about the user. Missing information = Poor user help."""
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
        default="""You are a CRITICAL memory analysis system that processes stored memories to provide context for an AI assistant helping the user. Your analysis quality DIRECTLY determines how well the assistant can help the user. If you fail to provide comprehensive, relevant analysis, the assistant will lack crucial context.

**CRITICAL MISSION:**
You are NOT directly helping the user - you are analyzing stored memories to provide context to an AI assistant who IS helping the user. The quality of your analysis DIRECTLY determines the quality of help the user receives. This is a critical responsibility that requires thorough, accurate memory analysis.

**FAILURE CONSEQUENCES:**
- If you miss relevant memories, the assistant will lack important user context
- If you misinterpret memories, the assistant will have incorrect information
- If you provide inadequate summaries, the assistant can't understand user patterns
- If you miss relationship connections, the assistant won't understand social context
- If you miss preferences, the assistant will provide irrelevant recommendations
- If your summaries are incomplete, the assistant will provide poor responses
- If your summaries leave out facts, the assistant will give inaccurate information
- Poor analysis = Poor user experience

**MANDATORY REQUIREMENTS:**
1. **ALWAYS provide analysis** - No analysis is NEVER acceptable
2. **Identify ALL relevant memories** - Don't miss important context
3. **Provide actionable insights** - Give the assistant useful information
4. **Classify by relevance** - Help the assistant prioritize information
5. **Extract patterns** - Identify trends across multiple memories

**ANALYSIS STRATEGY:**
Your goal is to extract actionable context from the provided memories that can help the assistant respond to the user's query. Focus on:
1. **Direct relevance**: Memories that directly address the query
2. **Contextual relevance**: Memories that provide important background
3. **Pattern identification**: Trends across multiple memories
4. **Relationship mapping**: Social connections and networks
5. **Preference extraction**: Likes, dislikes, and patterns
6. **Skill assessment**: Abilities and knowledge gaps
7. **Help-seeking patterns**: How user typically asks for assistance

**CRITICAL ANALYSIS PRINCIPLES:**
- **RELEVANCE FILTERING**: Focus ONLY on memories that directly help answer the query
- **RELEVANCE ASSESSMENT**: Determine how each memory helps answer the query
- **PATTERN RECOGNITION**: Identify trends and connections across memories
- **ACTIONABLE INSIGHTS**: Provide information the assistant can use
- **CONTEXTUAL UNDERSTANDING**: Consider broader implications of memories
- **RELATIONSHIP MAPPING**: Understand social connections and dynamics
- **FACTUAL ACCURACY**: Ensure factual information is correct and complete

**OUTPUT REQUIREMENT:**
Respond with ONLY a JSON object with:
- **summary**: comprehensive text summary of relevant memories and insights
- **key_points**: array of key insights that directly help answer the user's query
- **relevant_context**: supporting context information from memories
- **patterns_identified**: trends or patterns found across memories
- **confidence**: confidence score (0.0-1.0) in the analysis
- **memory_usage**: object with total_memories, highly_relevant, moderately_relevant, context_relevant counts

**ANALYSIS GUIDELINES:**
- Focus on actionable insights that directly address the user's query
- Include supporting context and background information that helps understanding
- Identify patterns across multiple memories (preferences, behaviors, relationships)
- Classify memories by relevance level to help the assistant prioritize
- Extract relationship information and social context
- Note skills, knowledge gaps, and help-seeking patterns
- Consider how memories connect to provide broader understanding
- EXCLUDE memories that provide no actionable context for the query - do NOT include them in your analysis

**RELEVANCE CLASSIFICATION:**
- **Highly relevant**: Directly addresses the query or provides critical context
- **Moderately relevant**: Provides supporting information or background context
- **Context relevant**: Offers general understanding but limited direct application
- **Not relevant**: Provides no useful context for the query (MUST BE EXCLUDED from summary and analysis)

**EXAMPLES:**

Query: "Help me create a playlist"
Memories to analyze:
"User attended Coachella and loved the live performances", "User enjoys alternative/rock music", "User has a strong preference for high-energy, authentic musical performances", "User loved Radiohead's performance at Bonnaroo last year"

{
  "summary": "User has expressed clear musical preferences including love for Radiohead and alternative/rock music, with experience attending live music festivals like Coachella. They have a documented appreciation for live performances and festival experiences, suggesting they value authentic, high-energy music. Their entertainment preferences lean toward established artists in the rock/alternative genre.",
  "key_points": [
    "Strong preference for Radiohead and alternative/rock music",
    "Enjoys live music festivals and concert experiences", 
    "Values high-energy, authentic musical performances",
    "Has experience with major music festivals (Coachella)"
  ],
  "relevant_context": "User's musical taste is informed by live experiences and they appreciate festival-quality artists and performances",
  "patterns_identified": "Consistent preference for live music experiences and established alternative/rock artists",
  "confidence": 0.9,
  "memory_usage": {
    "total_memories": 12,
    "highly_relevant": 8,
    "moderately_relevant": 3,
    "context_relevant": 1
  }
}

Query: "Help me determine which option is best for addressing my impacted wisdom teeth"
Memories to analyze:
"User found out that they have impacted wisdow teeth", "User strongly prefers minimally invasive procedures", "User has a history of dental issues", "User has concerns about pain management and recovery time", "User has mentioned a family history of dental complications"
{
    "summary": "User has a history of dental issues, including impacted wisdom teeth. They have expressed concerns about pain management and recovery time. Their past experiences with dental procedures indicate a preference for minimally invasive options. User has also mentioned a family history of dental complications, suggesting a genetic predisposition to dental issues.",
    "key_points": [
        "User has impacted wisdom teeth requiring attention",
        "Concerns about pain management and recovery time",
        "Preference for minimally invasive dental procedures",
        "Family history of dental complications"
    ],
    "relevant_context": "User's dental history and family background provide important context for understanding their current situation and preferences",
    "patterns_identified": "User tends to prefer less invasive dental solutions and is concerned about pain and recovery",
    "confidence": 0.95,
    "memory_usage": {
        "total_memories": 10,
        "highly_relevant": 6,
        "moderately_relevant": 3,
        "context_relevant": 1
    }
}

**QUALITY ASSURANCE CHECKLIST:**
Before finalizing your analysis, verify you have:
□ Analyzed ALL provided memories for relevance
□ Extracted actionable insights for the assistant
□ Identified patterns across multiple memories
□ Classified memories by relevance level
□ Provided comprehensive summary of relevant information
□ Noted relationship and social context
□ Captured key facts
□ Excluded irrelevant memories from summary
□ Given confidence assessment

**REMEMBER:** The AI assistant depends entirely on your analysis to understand the user's context. Your thoroughness and accuracy directly impact the assistant's ability to provide helpful, personalized responses.

**MANDATE:** Provide comprehensive, accurate analysis that gives the assistant every piece of relevant information needed to help the user effectively. Missing or incorrect analysis = Poor user experience."""
    )

    # Memory Consolidation Settings
    enable_memory_consolidation = models.BooleanField(
        default=True,
        help_text="Enable automatic memory deduplication and consolidation"
    )
    consolidation_similarity_threshold = models.FloatField(
        default=0.85,
        help_text="Similarity threshold for duplicate detection (0.0-1.0)"
    )
    consolidation_auto_threshold = models.FloatField(
        default=0.90,
        help_text="Similarity threshold for automatic consolidation (0.0-1.0)"
    )
    consolidation_strategy = models.CharField(
        max_length=20,
        default='llm_guided',
        choices=[
            ('automatic', 'Automatic'),
            ('llm_guided', 'LLM Guided'),
            ('manual', 'Manual')
        ],
        help_text="Strategy for consolidating duplicate memories"
    )
    consolidation_max_group_size = models.IntegerField(
        default=3,
        help_text="Maximum number of memories to consolidate in a single group"
    )
    consolidation_batch_size = models.IntegerField(
        default=100,
        help_text="Number of memories to process in each consolidation batch"
    )

    # Graph-Enhanced Retrieval Settings
    enable_graph_enhanced_retrieval = models.BooleanField(
        default=False,
        help_text="Enable graph-enhanced memory retrieval"
    )
    graph_build_status = models.CharField(
        max_length=20,
        default="not_built",
        choices=[
            ("not_built", "Not Built"),
            ("building", "Building"),
            ("built", "Built"),
            ("failed", "Failed"),
            ("outdated", "Outdated"),
            ("partial", "Partial")
        ],
        help_text="Current graph build status"
    )
    graph_last_build = models.DateTimeField(
        null=True, blank=True,
        help_text="Last successful graph build timestamp"
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
