#!/usr/bin/env python3
"""
LLM Log Analyzer - Analyze LLM calls to debug blog size issues

Usage:
    python analyze_llm_logs.py <thread_id>
    
Example:
    python analyze_llm_logs.py cfdf8f70-07b5-4a3d-b97f-b020e65d8acd
"""
import sys
import json
from pathlib import Path
from typing import Dict, List

def analyze_logs(thread_id: str):
    """Analyze all LLM calls for a thread"""
    log_file = Path("llm_logs") / f"{thread_id}_llm_calls.jsonl"
    
    if not log_file.exists():
        print(f"❌ No logs found for thread {thread_id}")
        print(f"   Expected file: {log_file}")
        return
    
    logs = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            logs.append(json.loads(line))
    
    print(f"\n{'='*100}")
    print(f"📊 LLM Call Analysis for Thread: {thread_id}")
    print(f"{'='*100}\n")
    
    # Summary statistics
    total_calls = len(logs)
    total_tokens = sum(log["total_tokens_estimate"] for log in logs)
    
    print(f"Total LLM Calls: {total_calls}")
    print(f"Estimated Total Tokens: {total_tokens:,}\n")
    
    # Group by node
    calls_by_node = {}
    for log in logs:
        node = log["node"]
        if node not in calls_by_node:
            calls_by_node[node] = []
        calls_by_node[node].append(log)
    
    print(f"Calls by Node:")
    for node, node_logs in calls_by_node.items():
        node_tokens = sum(l["total_tokens_estimate"] for l in node_logs)
        print(f"  • {node}: {len(node_logs)} calls, ~{node_tokens:,} tokens")
    
    print(f"\n{'='*100}")
    print(f"📝 DETAILED CALL LOG")
    print(f"{'='*100}\n")
    
    # Detailed analysis
    for i, log in enumerate(logs, 1):
        print(f"\n{'─'*100}")
        print(f"Call #{i}: {log['node']}")
        print(f"{'─'*100}")
        print(f"Timestamp: {log['timestamp']}")
        print(f"Model: {log['model_provider']}/{log['model_name']}")
        print(f"Tokens: ~{log['prompt_tokens_estimate']:,} prompt + ~{log['response_tokens_estimate']:,} response")
        
        if log.get("metadata"):
            print(f"\nMetadata:")
            for key, value in log["metadata"].items():
                print(f"  • {key}: {value}")
        
        print(f"\n📥 PROMPT:")
        print(f"{'-'*100}")
        # Truncate very long prompts
        prompt = log['prompt']
        if len(prompt) > 2000:
            print(prompt[:1000])
            print(f"\n... [truncated {len(prompt) - 2000} characters] ...\n")
            print(prompt[-1000:])
        else:
            print(prompt)
        
        print(f"\n📤 RESPONSE:")
        print(f"{'-'*100}")
        response = log['response']
        if len(response) > 2000:
            print(response[:1000])
            print(f"\n... [truncated {len(response) - 2000} characters] ...\n")
            print(response[-1000:])
        else:
            print(response)
        
    print(f"\n{'='*100}")
    print(f"🔍 WORD COUNT ANALYSIS (Writer & Critic Nodes)")
    print(f"{'='*100}\n")
    
    # Analyze word count compliance
    writer_logs = [l for l in logs if l['node'].startswith('writer_section')]
    
    if writer_logs:
        print(f"Writer Sections Analysis:\n")
        for log in writer_logs:
            meta = log.get('metadata', {})
            if 'target_words' in meta and 'actual_words' in meta:
                target = meta['target_words']
                actual = meta['actual_words']
                diff = meta.get('word_diff', actual - target)
                diff_pct = meta.get('word_diff_percentage', (diff / target * 100) if target > 0 else 0)
                
                status = "✅" if abs(diff_pct) <= 10 else "⚠️" if abs(diff_pct) <= 25 else "❌"
                
                print(f"{status} {meta.get('section_title', 'Unknown')}:")
                print(f"   Target: {target} words | Actual: {actual} words | Diff: {diff:+} ({diff_pct:+.1f}%)")
                
                if meta.get('is_retry'):
                    print(f"   🔄 Retry #{meta.get('retry_count', 1)} after critic feedback")
                print()
    
    # Analyze critic feedback
    critic_logs = [l for l in logs if l['node'].startswith('critic_section')]
    
    if critic_logs:
        print(f"\nCritic Feedback Analysis:\n")
        for log in critic_logs:
            meta = log.get('metadata', {})
            if 'draft_word_count' in meta:
                draft_words = meta['draft_word_count']
                target_words = meta.get('target_words', 0)
                word_diff = meta.get('word_diff', 0)
                
                status = "✅" if abs(word_diff) <= target_words * 0.1 else "⚠️" if abs(word_diff) <= target_words * 0.25 else "❌"
                
                print(f"{status} {meta.get('section_title', 'Unknown')}:")
                print(f"   Draft: {draft_words} words | Target: {target_words} words | Diff: {word_diff:+}")
                
                # Show feedback snippet
                try:
                    feedback = json.loads(log['response'])
                    feedback_text = feedback.get('feedback', '')
                    print(f"   Feedback: {feedback_text[:200]}{'...' if len(feedback_text) > 200 else ''}")
                except:
                    pass
                print()
    
    print(f"\n{'='*100}")
    print(f"✅ Analysis Complete")
    print(f"{'='*100}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_llm_logs.py <thread_id>")
        print("\nExample: python analyze_llm_logs.py cfdf8f70-07b5-4a3d-b97f-b020e65d8acd")
        sys.exit(1)
    
    thread_id = sys.argv[1]
    analyze_logs(thread_id)
