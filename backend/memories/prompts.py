"""
A-MEM Prompt Templates

Prompt templates for A-MEM note construction, link generation, and memory evolution.
Based on A-MEM paper (NeurIPS 2025) Appendix B.
"""

# =============================================================================
# Note Construction Prompt (Section 3.1, Appendix B.1)
# =============================================================================

AMEM_NOTE_CONSTRUCTION_PROMPT = """Generate a structured analysis of the following content by:
1. Identifying the most salient keywords (focus on nouns, verbs, and key concepts)
2. Extracting core themes and contextual elements
3. Creating relevant categorical tags

Format the response as a JSON object:
{{
  "keywords": [
    // several specific, distinct keywords that capture key concepts and terminology
    // Order from most to least important
    // Don't include keywords that are the name of the speaker or time
    // At least three keywords, but don't be too redundant.
  ],
  "context": // one sentence summarizing:
             // - Main topic/domain
             // - Key arguments/points
             // - Intended audience/purpose,
  "tags": [
    // several broad categories/themes for classification
    // Include domain, format, and type tags
    // At least three tags, but don't be too redundant.
  ]
}}

Content for analysis:
{content}

Timestamp: {timestamp}
"""


# =============================================================================
# Link Generation Prompt (Section 3.2, Appendix B.2)
# =============================================================================

AMEM_LINK_GENERATION_PROMPT = """You are an AI memory evolution agent responsible for managing and evolving a knowledge base.

Analyze the new memory note according to keywords and context, also with their several nearest neighbors memory.

The new memory:
Context: {new_context}
Content: {new_content}
Keywords: {new_keywords}

The nearest neighbors memories:
{nearest_neighbors}

Based on this information, determine:
Should this memory be evolved? Consider its relationships with other memories.

**IMPORTANT**: The "target_note_id" field MUST be one of the exact note IDs listed above in "The nearest neighbors memories" section.
Do NOT generate, invent, or create new IDs. Only use the actual IDs provided above.

Return your decision in JSON format:
{{
  "should_link": true/false,
  "links": [
    {{
      "target_note_id": "<<use exact ID from neighbors list above>>",
      "relationship_type": "string",
      "strength": 0.0-1.0,
      "rationale": "why this link makes sense"
    }}
  ]
}}
"""


# =============================================================================
# Memory Evolution Prompt (Section 3.3, Appendix B.3)
# =============================================================================

AMEM_MEMORY_EVOLUTION_PROMPT = """You are an AI memory evolution agent responsible for managing and evolving a knowledge base.

Analyze the new memory note according to keywords and context, also with their several nearest neighbors memory.

Make decisions about its evolution.

The new memory:
Context: {new_context}
Content: {new_content}
Keywords: {new_keywords}

The nearest neighbors memories:
{nearest_neighbors}

Based on this information, determine:
1. What specific actions should be taken (strengthen, update_neighbor)?
1.1 If choose to strengthen the connection, which memory should it be connected to? Can you give the updated tags of this memory?
1.2 If choose to update neighbor, you can update the context and tags of these memories based on the understanding of these memories.

Tags should be determined by the content of these characteristic of these memories, which can be used to retrieve them later and categorize them.

All the above information should be returned in a list format according to the sequence: [[new_memory],[neighbor_memory_1],...[neighbor_memory_n]]

Return your decision in JSON format:
{{
  "should_evolve": true/false,
  "actions": ["strengthen", "merge", "prune"],
  "suggested_connections": ["neighbor_memory_ids"],
  "tags_to_update": ["tag_1",...,"tag_n"],
  "new_context_neighborhood": ["new context",...,"new context"],
  "new_tags_neighborhood": [["tag_1",...,"tag_n"],...["tag_1",...,"tag_n"]]
}}
"""
