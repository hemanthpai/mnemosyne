"""
Django management command to test fact vs inference classification.

This command tests the memory extraction with various example inputs
to verify that inference levels are properly classified.
"""

import json
import logging
from django.core.management.base import BaseCommand
from memories.llm_service import MEMORY_EXTRACTION_FORMAT, llm_service
from settings_app.models import LLMSettings


class Command(BaseCommand):
    help = 'Test fact vs inference classification in memory extraction'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Run in interactive mode to test custom inputs',
        )

    def handle(self, *args, **options):
        interactive = options.get('interactive')

        self.stdout.write(
            self.style.SUCCESS("Testing Fact vs Inference Classification")
        )
        
        # Test cases with expected inference levels
        test_cases = [
            {
                "input": "I am 25 years old and work at Google as a software engineer.",
                "expected_levels": ["stated", "stated", "stated"],
                "description": "Direct statements should be classified as 'stated'"
            },
            {
                "input": "I went to Stanford. I love solving complex problems.",
                "expected_levels": ["stated", "stated", "inferred"],  # Tech background might be inferred
                "description": "Mix of direct statements and potential inferences"
            },
            {
                "input": "Ugh, I hate going to networking events. They're so draining.",
                "expected_levels": ["implied", "stated", "implied"],  # Introversion might be implied
                "description": "Emotional expressions with implied personality traits"
            },
            {
                "input": "My friend Sarah recommended this great Italian place downtown.",
                "expected_levels": ["stated", "stated", "inferred"],  # Trust in Sarah's taste might be inferred
                "description": "Direct facts with potential relationship inferences"
            }
        ]

        if interactive:
            self._run_interactive_mode()
        else:
            self._run_test_cases(test_cases)

    def _run_test_cases(self, test_cases):
        """Run predefined test cases"""
        settings = LLMSettings.get_settings()
        
        for i, test_case in enumerate(test_cases, 1):
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"TEST CASE {i}: {test_case['description']}")
            self.stdout.write(f"{'='*60}")
            self.stdout.write(f"Input: '{test_case['input']}'")
            
            # Extract memories
            result = self._extract_memories(test_case['input'])
            
            if result['success']:
                self._analyze_results(result['memories'], test_case.get('expected_levels', []))
            else:
                self.stdout.write(self.style.ERROR(f"Extraction failed: {result['error']}"))

    def _run_interactive_mode(self):
        """Run in interactive mode"""
        self.stdout.write("\nEntering interactive mode. Type 'quit' to exit.")
        
        while True:
            try:
                user_input = input("\nEnter text to analyze: ").strip()
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                    
                if not user_input:
                    continue
                    
                result = self._extract_memories(user_input)
                
                if result['success']:
                    self._analyze_results(result['memories'])
                else:
                    self.stdout.write(self.style.ERROR(f"Extraction failed: {result['error']}"))
                    
            except KeyboardInterrupt:
                break
                
        self.stdout.write("\nExiting interactive mode.")

    def _extract_memories(self, text):
        """Extract memories from text"""
        settings = LLMSettings.get_settings()
        system_prompt = settings.memory_extraction_prompt
        
        llm_result = llm_service.query_llm(
            system_prompt=system_prompt,
            prompt=text,
            response_format=MEMORY_EXTRACTION_FORMAT,
            temperature=0.3,  # Lower temperature for more consistent results
        )
        
        if not llm_result["success"]:
            return {
                "success": False,
                "error": llm_result["error"],
                "memories": []
            }
        
        try:
            memories_data = json.loads(llm_result["response"])
            if not isinstance(memories_data, list):
                raise ValueError("Expected a JSON array")
                
            return {
                "success": True,
                "memories": memories_data,
                "model": llm_result.get("model", "unknown")
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            return {
                "success": False,
                "error": f"Failed to parse response: {e}",
                "memories": []
            }

    def _analyze_results(self, memories, expected_levels=None):
        """Analyze and display extraction results"""
        if not memories:
            self.stdout.write(self.style.WARNING("No memories extracted"))
            return
            
        self.stdout.write(f"\nExtracted {len(memories)} memories:")
        
        inference_counts = {"stated": 0, "inferred": 0, "implied": 0}
        
        for i, memory in enumerate(memories, 1):
            content = memory.get("content", "")
            inference_level = memory.get("inference_level", "unknown")
            evidence = memory.get("evidence", "")
            certainty = memory.get("certainty", 0.0)
            confidence = memory.get("confidence", 0.0)
            
            inference_counts[inference_level] = inference_counts.get(inference_level, 0) + 1
            
            # Color coding for inference levels
            level_style = {
                "stated": self.style.SUCCESS,
                "inferred": self.style.WARNING,
                "implied": lambda x: self.style.HTTP_INFO(x)
            }.get(inference_level, self.style.ERROR)
            
            self.stdout.write(f"\n{i}. {level_style(inference_level.upper())}: {content}")
            self.stdout.write(f"   Evidence: {evidence}")
            self.stdout.write(f"   Certainty: {certainty:.2f} | Confidence: {confidence:.2f}")
            
            # Check against expected if provided
            if expected_levels and i <= len(expected_levels):
                expected = expected_levels[i-1]
                if inference_level == expected:
                    self.stdout.write(f"   ✅ Expected: {expected}")
                else:
                    self.stdout.write(f"   ❌ Expected: {expected}, Got: {inference_level}")
        
        # Summary statistics
        self.stdout.write(f"\n📊 INFERENCE LEVEL DISTRIBUTION:")
        total = len(memories)
        for level, count in inference_counts.items():
            if count > 0:
                percentage = (count / total) * 100
                self.stdout.write(f"   {level.capitalize()}: {count} ({percentage:.1f}%)")
        
        # Quality assessment
        stated_ratio = inference_counts.get("stated", 0) / total
        if stated_ratio > 0.6:
            self.stdout.write(self.style.SUCCESS("✅ Good: High ratio of stated facts"))
        elif stated_ratio > 0.4:
            self.stdout.write(self.style.WARNING("⚠️  Moderate: Balanced mix of fact types"))
        else:
            self.stdout.write(self.style.ERROR("❌ Concerning: Low ratio of stated facts"))

    def _get_style_for_level(self, level):
        """Get appropriate style for inference level"""
        styles = {
            "stated": self.style.SUCCESS,
            "inferred": self.style.WARNING,
            "implied": self.style.HTTP_INFO,
        }
        return styles.get(level, self.style.ERROR)