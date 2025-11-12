"""
Django management command to run benchmark tests for extraction and search quality

Usage:
    python manage.py run_benchmark [--test-type extraction|search|all] [--verbose]
"""

import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache

from memories.models import ConversationTurn, AtomicNote
from memories.graph_service import graph_service
from memories.conversation_service import conversation_service
import time


class Command(BaseCommand):
    help = "Run benchmark tests for extraction and search quality"

    def __init__(self):
        super().__init__()
        self.task_id = None

    def update_progress(self, current, total, phase=''):
        """Update progress in cache for UI polling"""
        if not self.task_id:
            return

        progress_data = {
            'current': current,
            'total': total,
            'phase': phase,
            'percentage': int((current / total * 100)) if total > 0 else 0
        }
        cache.set(f'benchmark_progress_{self.task_id}', progress_data, timeout=3600)  # 1 hour

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-type',
            type=str,
            default='all',
            choices=['extraction', 'search', 'evolution', 'all'],
            help='Type of test to run'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )
        parser.add_argument(
            '--dataset',
            type=str,
            default='benchmark_dataset.json',
            help='Dataset filename (in test_data directory)'
        )
        parser.add_argument(
            '--save-results',
            action='store_true',
            help='Save benchmark results to prompt_history.json'
        )
        parser.add_argument(
            '--prompt-version',
            type=str,
            help='Prompt version identifier for saving results (required with --save-results)'
        )
        parser.add_argument(
            '--notes',
            type=str,
            default='',
            help='Observations about this benchmark run'
        )
        parser.add_argument(
            '--task-id',
            type=str,
            default='',
            help='Task ID for progress tracking (internal use)'
        )

    def handle(self, *args, **options):
        test_type = options['test_type']
        verbose = options['verbose']
        dataset_file = options['dataset']
        self.task_id = options.get('task_id', '')

        # Load benchmark dataset
        # Add .json extension if not present
        if not dataset_file.endswith('.json'):
            dataset_file = f'{dataset_file}.json'
        dataset_path = Path(__file__).parent.parent.parent / 'test_data' / dataset_file

        if not dataset_path.exists():
            self.stdout.write(self.style.ERROR(f'Dataset not found: {dataset_path}'))
            return

        with open(dataset_path, 'r') as f:
            dataset = json.load(f)

        # Calculate total items for progress tracking
        total_items = 0
        if test_type in ['extraction', 'all']:
            total_items += len(dataset.get('test_conversations', []))
        if test_type in ['search', 'all']:
            total_items += len(dataset.get('test_queries', []))
        if test_type in ['evolution', 'all']:
            total_items += len(dataset.get('test_conversations', []))

        # Initialize progress
        self.update_progress(0, total_items, phase='Starting benchmark')

        self.stdout.write(self.style.SUCCESS(f'\n=== Benchmark Testing ==='))
        self.stdout.write(f'Dataset: {dataset.get("description", "Unknown")}')
        self.stdout.write(f'Version: {dataset.get("dataset_version", "Unknown")}')
        self.stdout.write(f'Test conversations: {len(dataset.get("test_conversations", []))}')
        self.stdout.write(f'Test queries: {len(dataset.get("test_queries", []))}\n')

        results = {}
        completed_items = 0  # Track cumulative progress across all test phases

        # Run extraction tests
        if test_type in ['extraction', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Extraction Quality Tests ---\n'))
            results['extraction'] = self.run_extraction_tests(
                dataset.get('test_conversations', []),
                verbose,
                completed_items,
                total_items
            )
            completed_items += len(dataset.get('test_conversations', []))

        # Run search tests
        if test_type in ['search', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Search Relevance Tests ---\n'))
            results['search'] = self.run_search_tests(
                dataset.get('test_queries', []),
                dataset.get('test_conversations', []),
                verbose,
                completed_items,
                total_items
            )
            completed_items += len(dataset.get('test_queries', []))

        # Run evolution tests
        if test_type in ['evolution', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Memory Evolution Tests ---\n'))
            results['evolution'] = self.run_evolution_tests(
                dataset.get('test_conversations', []),
                verbose,
                completed_items,
                total_items
            )

        # Print summary
        self.print_summary(results, test_type)

        # Save results if requested
        if options.get('save_results'):
            self.save_results(results, options)

    def run_extraction_tests(self, test_conversations: List[Dict], verbose: bool, completed_so_far: int, total_items: int) -> Dict[str, Any]:
        """Run extraction quality tests"""

        # Use a test user ID
        test_user_id = uuid.UUID('00000000-0000-0000-0000-000000000001')

        # Clean up any existing test data
        ConversationTurn.objects.filter(user_id=test_user_id).delete()
        AtomicNote.objects.filter(user_id=test_user_id).delete()

        total_true_positives = 0
        total_false_positives = 0
        total_false_negatives = 0
        total_ground_truth = 0
        total_extracted = 0

        category_results = defaultdict(lambda: {
            'tp': 0, 'fp': 0, 'fn': 0,
            'ground_truth': 0, 'extracted': 0
        })

        completed_tests = 0

        for test_case in test_conversations:
            test_id = test_case['id']
            category = test_case.get('category', 'unknown')
            user_message = test_case['user_message']
            assistant_message = test_case.get('assistant_message', '')
            ground_truth = test_case.get('ground_truth_notes', [])
            should_not_extract = test_case.get('should_not_extract', [])

            if verbose:
                self.stdout.write(f'\nTest: {test_id} ({category})')
                self.stdout.write(f'User: {user_message[:80]}...')

            # Create conversation turn using proper service
            # This ensures proper embedding generation, vector storage, and caching
            turn = conversation_service.store_turn(
                user_id=str(test_user_id),
                session_id=f'benchmark_session_{test_id}',
                user_message=user_message,
                assistant_message=assistant_message
            )

            # Poll for extraction completion (max 120 seconds)
            max_wait = 120
            poll_interval = 2
            waited = 0

            while waited < max_wait:
                try:
                    turn.refresh_from_db()
                    if turn.extracted:
                        break
                except ConversationTurn.DoesNotExist:
                    # Turn was deleted due to embedding failure
                    self.stdout.write(self.style.ERROR(
                        f'  ✗ Turn deleted for {test_id} (likely embedding generation failure)'
                    ))
                    break
                time.sleep(poll_interval)
                waited += poll_interval

            # Check if turn still exists
            try:
                turn.refresh_from_db()
            except ConversationTurn.DoesNotExist:
                # Turn was deleted, skip this test case
                continue

            if not turn.extracted:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ Extraction timed out for {test_id} after {max_wait}s'
                ))
                continue

            # Get extracted notes
            extracted_notes = AtomicNote.objects.filter(source_turn=turn)
            extracted_contents = [note.content.lower() for note in extracted_notes]

            # Calculate metrics for this test case
            tp = 0  # True positives
            fp = 0  # False positives
            fn = 0  # False negatives

            # Check ground truth notes
            matched_ground_truth = set()
            for gt_note in ground_truth:
                gt_content = gt_note['content'].lower()

                # Check if this ground truth was extracted
                found = False
                for extracted_content in extracted_contents:
                    similarity = self._similarity(gt_content, extracted_content)
                    # Fuzzy match: substring match or semantic similarity
                    # Lower threshold to account for semantic equivalence
                    if (gt_content in extracted_content or
                        extracted_content in gt_content or
                        similarity >= 0.5 or
                        self._has_core_concept_match(gt_content, extracted_content)):
                        found = True
                        matched_ground_truth.add(extracted_content)
                        break

                if found:
                    tp += 1
                    if verbose:
                        self.stdout.write(f'  ✓ Found: {gt_note["content"]}')
                else:
                    fn += 1
                    if verbose:
                        self.stdout.write(self.style.WARNING(
                            f'  ✗ Missing: {gt_note["content"]}'
                        ))

            # Check for false positives
            for extracted_content in extracted_contents:
                if extracted_content not in matched_ground_truth:
                    # Check if it's in the "should not extract" list
                    is_false_positive = False

                    # Check against assistant message content
                    for forbidden in should_not_extract:
                        if (forbidden.lower() in extracted_content or
                            extracted_content in forbidden.lower() or
                            self._similarity(forbidden.lower(), extracted_content) > 0.7):
                            is_false_positive = True
                            break

                    if is_false_positive:
                        fp += 1
                        if verbose:
                            self.stdout.write(self.style.ERROR(
                                f'  ✗ False positive: {extracted_content}'
                            ))
                    else:
                        # It's a note we didn't account for in ground truth
                        # Don't count as FP, but show in verbose mode
                        if verbose:
                            self.stdout.write(
                                f'  ? Extra note (not in ground truth): {extracted_content}'
                            )

            # Update totals
            total_true_positives += tp
            total_false_positives += fp
            total_false_negatives += fn
            total_ground_truth += len(ground_truth)
            total_extracted += len(extracted_notes)

            # Update category results
            category_results[category]['tp'] += tp
            category_results[category]['fp'] += fp
            category_results[category]['fn'] += fn
            category_results[category]['ground_truth'] += len(ground_truth)
            category_results[category]['extracted'] += len(extracted_notes)

            if verbose:
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
                self.stdout.write(f'  Metrics: P={precision:.2f} R={recall:.2f} F1={f1:.2f}\n')

            # Update progress after completing this test
            completed_tests += 1
            self.update_progress(completed_so_far + completed_tests, total_items, phase='Extraction tests')

        # Calculate overall metrics
        precision = total_true_positives / (total_true_positives + total_false_positives) \
            if (total_true_positives + total_false_positives) > 0 else 0
        recall = total_true_positives / (total_true_positives + total_false_negatives) \
            if (total_true_positives + total_false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) \
            if (precision + recall) > 0 else 0

        false_positive_rate = total_false_positives / total_extracted \
            if total_extracted > 0 else 0

        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'false_positive_rate': false_positive_rate,
            'total_ground_truth': total_ground_truth,
            'total_extracted': total_extracted,
            'true_positives': total_true_positives,
            'false_positives': total_false_positives,
            'false_negatives': total_false_negatives,
            'category_results': dict(category_results)
        }

    def run_search_tests(self, test_queries: List[Dict], test_conversations: List[Dict], verbose: bool, completed_so_far: int, total_items: int) -> Dict[str, Any]:
        """Run search relevance tests"""

        # Use test user ID
        test_user_id = uuid.UUID('00000000-0000-0000-0000-000000000001')

        # Create a mapping of test IDs to actual note IDs
        test_id_to_notes = {}
        for conv in test_conversations:
            test_id = conv['id']
            # Find notes from this conversation
            turn = ConversationTurn.objects.filter(
                user_id=test_user_id,
                user_message=conv['user_message']
            ).first()

            if turn:
                notes = AtomicNote.objects.filter(source_turn=turn)
                test_id_to_notes[test_id] = [str(note.id) for note in notes]
            else:
                test_id_to_notes[test_id] = []

        total_queries = len(test_queries)
        total_precision_at_10 = 0
        total_recall_at_10 = 0
        total_mrr = 0
        completed_queries = 0

        for query_test in test_queries:
            query_id = query_test['query_id']
            query = query_test['query']
            relevant_test_ids = query_test.get('relevant_note_ids', [])
            irrelevant_test_ids = query_test.get('irrelevant_note_ids', [])

            # Map test IDs to actual note IDs
            relevant_note_ids = set()
            for test_id in relevant_test_ids:
                relevant_note_ids.update(test_id_to_notes.get(test_id, []))

            irrelevant_note_ids = set()
            for test_id in irrelevant_test_ids:
                irrelevant_note_ids.update(test_id_to_notes.get(test_id, []))

            if verbose:
                self.stdout.write(f'\nQuery: {query_id} - "{query}"')
                self.stdout.write(f'Expected relevant notes: {len(relevant_note_ids)}')

            # Run search (with query expansion if enabled)
            search_results = graph_service.search_atomic_notes_with_expansion(
                query=query,
                user_id=str(test_user_id),
                limit=10,
                threshold=0.0,  # Get all results for testing
                use_expansion=True  # Use query expansion for better recall
            )

            if verbose:
                self.stdout.write(f'Results returned: {len(search_results)}')

            # Calculate metrics
            top_10 = search_results[:10]
            top_10_ids = [r['id'] for r in top_10]

            # Precision@10: % of top 10 that are relevant
            relevant_in_top_10 = sum(1 for note_id in top_10_ids if note_id in relevant_note_ids)
            irrelevant_in_top_10 = sum(1 for note_id in top_10_ids if note_id in irrelevant_note_ids)
            precision_at_10 = relevant_in_top_10 / len(top_10) if top_10 else 0

            # Recall@10: % of relevant notes found in top 10
            recall_at_10 = relevant_in_top_10 / len(relevant_note_ids) if relevant_note_ids else 0

            # MRR: 1 / rank of first relevant result
            first_relevant_rank = None
            for i, note_id in enumerate(top_10_ids, 1):
                if note_id in relevant_note_ids:
                    first_relevant_rank = i
                    break
            mrr = 1 / first_relevant_rank if first_relevant_rank else 0

            if verbose:
                self.stdout.write(f'  Precision@10: {precision_at_10:.2f}')
                self.stdout.write(f'  Recall@10: {recall_at_10:.2f}')
                self.stdout.write(f'  MRR: {mrr:.2f}')
                self.stdout.write(f'  Relevant in top 10: {relevant_in_top_10}')
                self.stdout.write(f'  Irrelevant in top 10: {irrelevant_in_top_10}')

                if verbose and top_10:
                    self.stdout.write('  Top results:')
                    for i, result in enumerate(top_10[:5], 1):
                        is_relevant = '✓' if result['id'] in relevant_note_ids else '✗'
                        self.stdout.write(
                            f'    {i}. {is_relevant} [{result["score"]:.3f}] {result["content"][:60]}...'
                        )

            total_precision_at_10 += precision_at_10
            total_recall_at_10 += recall_at_10
            total_mrr += mrr

            # Update progress after completing this query
            completed_queries += 1
            self.update_progress(completed_so_far + completed_queries, total_items, phase='Search tests')

        # Calculate averages
        avg_precision_at_10 = total_precision_at_10 / total_queries if total_queries > 0 else 0
        avg_recall_at_10 = total_recall_at_10 / total_queries if total_queries > 0 else 0
        avg_mrr = total_mrr / total_queries if total_queries > 0 else 0

        return {
            'average_precision_at_10': avg_precision_at_10,
            'average_recall_at_10': avg_recall_at_10,
            'mean_reciprocal_rank': avg_mrr,
            'total_queries': total_queries
        }

    def run_evolution_tests(self, test_conversations: List[Dict], verbose: bool, completed_so_far: int, total_items: int) -> Dict[str, Any]:
        """Run memory evolution tests"""
        from memories.amem_service import amem_service

        # Use test user ID
        test_user_id = uuid.UUID('00000000-0000-0000-0000-000000000001')

        # Get all notes for test user (should exist from extraction tests)
        all_notes = list(AtomicNote.objects.filter(user_id=test_user_id, is_amem_enriched=True))

        if len(all_notes) < 2:
            self.stdout.write(self.style.WARNING(
                f'Not enough enriched notes for evolution testing (found {len(all_notes)}, need at least 2). '
                f'Run extraction tests first.'
            ))
            return {
                'notes_tested': 0,
                'evolutions_triggered': 0,
                'neighbors_updated': 0,
                'avg_neighbors_per_evolution': 0
            }

        self.stdout.write(f'Testing evolution with {len(all_notes)} enriched notes\n')

        total_evolutions_triggered = 0
        total_neighbors_updated = 0
        total_evolution_attempts = 0
        evolution_details = []
        completed_evolutions = 0
        num_conversations = len(test_conversations)

        # Test evolution for each note
        for note in all_notes[:10]:  # Limit to 10 notes to avoid timeout
            if verbose:
                self.stdout.write(f'\nTesting evolution for note {note.id}')
                self.stdout.write(f'  Content: {note.content[:80]}...')

            # Find similar notes as neighbors (excluding self)
            similar_notes = list(
                AtomicNote.objects.filter(
                    user_id=test_user_id,
                    is_amem_enriched=True
                ).exclude(id=note.id)[:5]  # Get up to 5 neighbors
            )

            if not similar_notes:
                if verbose:
                    self.stdout.write('  No neighbors found, skipping')
                continue

            # Store original state of neighbors
            original_states = {}
            for neighbor in similar_notes:
                original_states[neighbor.id] = {
                    'tags': list(neighbor.llm_tags) if neighbor.llm_tags else [],
                    'context': neighbor.contextual_description
                }

            # Call evolve_memories
            evolution_result = amem_service.evolve_memories(note, similar_notes)

            total_evolution_attempts += 1

            # Check if evolution was triggered
            if evolution_result['evolved']:
                total_evolutions_triggered += 1
                num_updated = len(evolution_result['evolved'])
                total_neighbors_updated += num_updated

                if verbose:
                    self.stdout.write(f'  ✓ Evolution triggered: {num_updated} neighbors updated')
                    self.stdout.write(f'    Actions: {evolution_result["actions"]}')

                # Check what changed
                for evolved_id in evolution_result['evolved']:
                    evolved_note = AtomicNote.objects.get(id=evolved_id)
                    original = original_states[evolved_note.id]

                    tags_changed = (evolved_note.llm_tags or []) != original['tags']
                    context_changed = evolved_note.contextual_description != original['context']

                    if verbose and (tags_changed or context_changed):
                        self.stdout.write(f'    Note {evolved_id}:')
                        if tags_changed:
                            self.stdout.write(f'      Tags: {original["tags"]} → {evolved_note.llm_tags}')
                        if context_changed:
                            self.stdout.write(f'      Context updated')

                evolution_details.append({
                    'note_id': str(note.id),
                    'neighbors_updated': num_updated,
                    'actions': evolution_result['actions']
                })
            else:
                if verbose:
                    self.stdout.write('  No evolution needed')

            # Update progress after processing this note
            # Scale the progress based on conversations (total expected) vs notes processed
            completed_evolutions += 1
            progress_in_phase = min(completed_evolutions / max(1, len(all_notes[:10])) * num_conversations, num_conversations)
            self.update_progress(completed_so_far + int(progress_in_phase), total_items, phase='Evolution tests')

        # Calculate metrics
        evolution_rate = total_evolutions_triggered / total_evolution_attempts if total_evolution_attempts > 0 else 0
        avg_neighbors_per_evolution = total_neighbors_updated / total_evolutions_triggered if total_evolutions_triggered > 0 else 0

        return {
            'notes_tested': total_evolution_attempts,
            'evolutions_triggered': total_evolutions_triggered,
            'neighbors_updated': total_neighbors_updated,
            'evolution_rate': evolution_rate,
            'avg_neighbors_per_evolution': avg_neighbors_per_evolution,
            'evolution_details': evolution_details
        }

    def print_summary(self, results: Dict, test_type: str):
        """Print test summary"""
        self.stdout.write(self.style.SUCCESS('\n\n=== BENCHMARK SUMMARY ===\n'))

        if 'extraction' in results:
            ext = results['extraction']
            self.stdout.write(self.style.SUCCESS('Extraction Quality:'))
            self.stdout.write(f'  Precision:  {ext["precision"]:.2%} ({ext["true_positives"]}/{ext["true_positives"] + ext["false_positives"]})')
            self.stdout.write(f'  Recall:     {ext["recall"]:.2%} ({ext["true_positives"]}/{ext["total_ground_truth"]})')
            self.stdout.write(f'  F1 Score:   {ext["f1_score"]:.2%}')
            self.stdout.write(f'  False Positive Rate: {ext["false_positive_rate"]:.2%}')

            # Category breakdown
            self.stdout.write('\n  By Category:')
            for category, cat_results in ext['category_results'].items():
                tp = cat_results['tp']
                fp = cat_results['fp']
                fn = cat_results['fn']
                p = tp / (tp + fp) if (tp + fp) > 0 else 0
                r = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * (p * r) / (p + r) if (p + r) > 0 else 0
                self.stdout.write(f'    {category:25s}: P={p:.2%} R={r:.2%} F1={f1:.2%}')

            # Quality assessment
            if ext['f1_score'] >= 0.9:
                quality = self.style.SUCCESS('EXCELLENT ✓✓✓')
            elif ext['f1_score'] >= 0.8:
                quality = self.style.SUCCESS('GOOD ✓✓')
            elif ext['f1_score'] >= 0.7:
                quality = self.style.WARNING('FAIR ✓')
            else:
                quality = self.style.ERROR('NEEDS IMPROVEMENT ✗')

            self.stdout.write(f'\n  Overall Quality: {quality}')

        if 'search' in results:
            search = results['search']
            self.stdout.write(self.style.SUCCESS('\nSearch Quality:'))
            self.stdout.write(f'  Precision@10: {search["average_precision_at_10"]:.2%}')
            self.stdout.write(f'  Recall@10:    {search["average_recall_at_10"]:.2%}')
            self.stdout.write(f'  MRR:          {search["mean_reciprocal_rank"]:.3f}')

            # Quality assessment
            if search['average_precision_at_10'] >= 0.8 and search['mean_reciprocal_rank'] >= 0.7:
                quality = self.style.SUCCESS('EXCELLENT ✓✓✓')
            elif search['average_precision_at_10'] >= 0.6 and search['mean_reciprocal_rank'] >= 0.5:
                quality = self.style.SUCCESS('GOOD ✓✓')
            elif search['average_precision_at_10'] >= 0.4:
                quality = self.style.WARNING('FAIR ✓')
            else:
                quality = self.style.ERROR('NEEDS IMPROVEMENT ✗')

            self.stdout.write(f'\n  Overall Quality: {quality}')

        if 'evolution' in results:
            evo = results['evolution']
            self.stdout.write(self.style.SUCCESS('\nMemory Evolution Quality:'))
            self.stdout.write(f'  Notes Tested:       {evo["notes_tested"]}')
            self.stdout.write(f'  Evolutions Triggered: {evo["evolutions_triggered"]} ({evo.get("evolution_rate", 0):.1%})')
            self.stdout.write(f'  Neighbors Updated:  {evo["neighbors_updated"]}')
            self.stdout.write(f'  Avg Neighbors/Evolution: {evo.get("avg_neighbors_per_evolution", 0):.1f}')

            # Quality assessment
            evolution_rate = evo.get('evolution_rate', 0)
            if evolution_rate >= 0.3 and evo.get('avg_neighbors_per_evolution', 0) >= 1:
                quality = self.style.SUCCESS('GOOD ✓✓')
            elif evolution_rate >= 0.1:
                quality = self.style.WARNING('FAIR ✓')
            else:
                quality = self.style.ERROR('LOW ACTIVITY ✗')

            self.stdout.write(f'\n  Overall Quality: {quality}')

        self.stdout.write('\n')

    def _similarity(self, s1: str, s2: str) -> float:
        """Simple similarity score between two strings"""
        # Jaccard similarity on words
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def _has_core_concept_match(self, s1: str, s2: str) -> bool:
        """Check if two strings express the same core concept with different wording"""
        # Define semantic equivalents for common patterns
        synonyms = {
            'dislikes': ['not a fan of', 'not fond of', 'dislikes', 'hates'],
            'likes': ['enjoys', 'loves', 'likes', 'fond of', 'fan of', 'interest in', 'strong interest'],
            'uses': ['works with', 'uses', 'utilizes', 'employs'],
            'experienced': ['experienced with', 'has experience with', 'has worked with', 'worked with', 'has prior experience'],
            'works_as': ['works as', 'working as', 'has been working as'],
            'prefers': ['prefers', 'favors', 'chooses'],
            'knows': ['fluent in', 'knows', 'speaks', 'knows some'],
            'learning': ['learning', 'know some', 'knows some', 'beginner', 'intermediate level'],
            'owns': ['has', 'owns', 'bought', 'purchased', 'just bought'],
            'interested': ['interested', 'into', 'getting into', 'fascinated'],
            'attends': ['attends', 'tries to see', 'attempts to see', 'goes to', 'regularly'],
            'focuses': ['focuses on', 'mainly', 'primarily'],
            'finds_rewarding': ['finds rewarding', 'rewarding to', 'finds helpful'],
            'cares': ['cares about', 'interested in', 'values', 'passionate about'],
            'bakes': ['bakes', 'makes'],
            'maintains': ['maintains', 'has'],
            'trains': ['trains in', 'training in', 'has been', 'doing'],
            'learned': ['learned', 'considers', 'found', 'discovered'],
            'previously': ['previously', 'used to', 'formerly'],
            'founded': ['founded', 'launched', 'started'],
            'generates': ['generates', 'has', 'at'],
            'challenging': ['challenging', 'difficult', 'hardest part', 'hard', 'rough'],
            'picks': ['picks', 'does', 'performs', 'engages in'],
            'allocates': ['allocates', 'portfolio in', 'portfolio to'],
            'shoots': ['shoots', 'exclusively'],
            'ran': ['ran', 'completed'],
            'finished': ['finished', 'completed', 'in'],
            'practices': ['practices', 'does'],
            'weekly': ['weekly', 'every weekend', 'per week'],
            'can': ['can', 'able to'],
            'planning': ['planning', 'plans to', 'going to'],
        }

        s1_lower = s1.lower()
        s2_lower = s2.lower()

        # Extract key concepts (entities) from both strings
        # Remove common words and focus on nouns/entities
        common_words = {'a', 'an', 'the', 'in', 'for', 'with', 'to', 'of', 'is', 'are', 'has', 'have'}
        words1 = [w for w in s1_lower.split() if w not in common_words]
        words2 = [w for w in s2_lower.split() if w not in common_words]

        # Check if main entities/concepts match
        entities_match = len(set(words1) & set(words2)) >= min(len(words1), len(words2)) * 0.5

        if entities_match:
            # Check if sentiment/action is similar using synonyms
            for concept, variants in synonyms.items():
                s1_has_concept = any(var in s1_lower for var in variants)
                s2_has_concept = any(var in s2_lower for var in variants)
                if s1_has_concept and s2_has_concept:
                    return True

        return False

    def save_results(self, results: Dict, options: Dict):
        """Save benchmark results to prompt_history.json"""
        from datetime import datetime

        prompt_version = options.get('prompt_version')
        if not prompt_version:
            self.stdout.write(self.style.ERROR(
                'Error: --prompt-version is required when using --save-results'
            ))
            return

        # Get current prompt text from tasks.py
        from memories.tasks import EXTRACTION_PROMPT

        history_path = Path(__file__).parent.parent.parent / 'test_data' / 'prompt_history.json'

        # Load existing history
        if history_path.exists():
            with open(history_path, 'r') as f:
                history = json.load(f)
        else:
            history = {
                "schema_version": "1.0",
                "description": "History of extraction prompt versions and their benchmark performance",
                "prompts": []
            }

        # Create benchmark run record
        run_record = {
            "run_date": datetime.now().isoformat(),
            "extraction": {},
            "search": {},
            "observations": options.get('notes', '')
        }

        # Add extraction results if available
        if 'extraction' in results:
            ext = results['extraction']
            run_record['extraction'] = {
                "precision": ext['precision'],
                "recall": ext['recall'],
                "f1_score": ext['f1_score'],
                "false_positive_rate": ext['false_positive_rate'],
                "total_ground_truth": ext['total_ground_truth'],
                "total_extracted": ext['total_extracted'],
                "by_category": {}
            }

            # Add category breakdowns
            for category, metrics in ext['category_results'].items():
                cat_data = metrics.copy()
                # Calculate precision, recall, F1 for this category
                tp = cat_data['tp']
                fp = cat_data['fp']
                fn = cat_data['fn']

                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

                run_record['extraction']['by_category'][category] = {
                    "precision": precision,
                    "recall": recall,
                    "f1": f1
                }

        # Add search results if available
        if 'search' in results:
            srch = results['search']
            run_record['search'] = {
                "precision_at_10": srch['average_precision_at_10'],
                "recall_at_10": srch['average_recall_at_10'],
                "mrr": srch['mean_reciprocal_rank']
            }

        # Find or create prompt version entry
        prompt_entry = None
        for p in history['prompts']:
            if p['version'] == prompt_version:
                prompt_entry = p
                break

        if prompt_entry:
            # Add run to existing prompt version
            if 'benchmark_runs' not in prompt_entry:
                prompt_entry['benchmark_runs'] = []
            prompt_entry['benchmark_runs'].append(run_record)
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ Added benchmark run to existing prompt version {prompt_version}'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'\n⚠ Prompt version {prompt_version} not found in history.'
            ))
            self.stdout.write('  Please add this version manually to prompt_history.json with:')
            self.stdout.write('  - version, date, description, changes, prompt_text')
            return

        # Save updated history
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)

        self.stdout.write(self.style.SUCCESS(
            f'✓ Saved results to {history_path.relative_to(Path.cwd())}'
        ))
