"""
LLM Call Logger - Logs all prompts, responses, and metadata for debugging
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

class LLMLogger:
    """Logger for tracking all LLM interactions"""
    
    def __init__(self, log_dir: str = "llm_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
    def log_call(
        self,
        thread_id: str,
        node_name: str,
        prompt: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
        model_info: Optional[Dict[str, str]] = None
    ):
        """
        Log a single LLM call with full context
        
        Args:
            thread_id: Unique thread/workflow ID
            node_name: Name of the node making the call (e.g., "planner", "writer", "critic")
            prompt: The full prompt sent to the LLM
            response: The response received from the LLM
            metadata: Additional context (section_id, word_count, etc.)
            model_info: Model provider and name
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Count approximate tokens (rough estimate: 1 token ≈ 4 chars)
        prompt_tokens = len(prompt) // 4
        response_tokens = len(response) // 4
        
        log_entry = {
            "timestamp": timestamp,
            "thread_id": thread_id,
            "node": node_name,
            "model_provider": model_info.get("provider", "unknown") if model_info else "unknown",
            "model_name": model_info.get("name", "unknown") if model_info else "unknown",
            "prompt_tokens_estimate": prompt_tokens,
            "response_tokens_estimate": response_tokens,
            "total_tokens_estimate": prompt_tokens + response_tokens,
            "metadata": metadata or {},
            "prompt": prompt,
            "response": response
        }
        
        # Log to thread-specific file
        log_file = self.log_dir / f"{thread_id}_llm_calls.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        # Also log to console for real-time debugging
        print(f"\n{'='*80}")
        print(f"🤖 LLM CALL: {node_name}")
        print(f"   Thread: {thread_id}")
        print(f"   Model: {model_info.get('provider', 'unknown')}/{model_info.get('name', 'unknown') if model_info else 'unknown'}")
        print(f"   Tokens: ~{prompt_tokens} prompt + ~{response_tokens} response = ~{prompt_tokens + response_tokens} total")
        if metadata:
            print(f"   Metadata: {json.dumps(metadata, indent=2)}")
        print(f"{'='*80}\n")
        
    def log_structured_call(
        self,
        thread_id: str,
        node_name: str,
        prompt_template: str,
        prompt_variables: Dict[str, Any],
        response_obj: Any,
        metadata: Optional[Dict[str, Any]] = None,
        model_info: Optional[Dict[str, str]] = None
    ):
        """
        Log a structured LLM call (with Pydantic output)
        
        Args:
            thread_id: Unique thread/workflow ID
            node_name: Name of the node
            prompt_template: The template string
            prompt_variables: Variables passed to template
            response_obj: Pydantic model or dict response
            metadata: Additional context
            model_info: Model provider and name
        """
        # Format the full prompt
        try:
            full_prompt = prompt_template.format(**prompt_variables)
        except:
            full_prompt = f"Template:\n{prompt_template}\n\nVariables:\n{json.dumps(prompt_variables, indent=2, default=str)}"
        
        # Serialize response
        if hasattr(response_obj, "model_dump"):
            response_str = json.dumps(response_obj.model_dump(), indent=2)
        elif hasattr(response_obj, "dict"):
            response_str = json.dumps(response_obj.dict(), indent=2)
        else:
            response_str = str(response_obj)
        
        self.log_call(
            thread_id=thread_id,
            node_name=node_name,
            prompt=full_prompt,
            response=response_str,
            metadata=metadata,
            model_info=model_info
        )
    
    def get_thread_logs(self, thread_id: str) -> list:
        """Retrieve all logs for a specific thread"""
        log_file = self.log_dir / f"{thread_id}_llm_calls.jsonl"
        if not log_file.exists():
            return []
        
        logs = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                logs.append(json.loads(line))
        return logs
    
    def analyze_thread(self, thread_id: str) -> Dict[str, Any]:
        """Analyze all LLM calls for a thread and provide statistics"""
        logs = self.get_thread_logs(thread_id)
        
        if not logs:
            return {"error": "No logs found"}
        
        total_tokens = sum(log["total_tokens_estimate"] for log in logs)
        total_calls = len(logs)
        
        calls_by_node = {}
        for log in logs:
            node = log["node"]
            if node not in calls_by_node:
                calls_by_node[node] = 0
            calls_by_node[node] += 1
        
        return {
            "thread_id": thread_id,
            "total_llm_calls": total_calls,
            "total_tokens_estimate": total_tokens,
            "calls_by_node": calls_by_node,
            "logs": logs
        }


# Global logger instance
llm_logger = LLMLogger(log_dir="llm_logs")
