"""
Workflow Summary Generator - Option 2 Implementation

Generates human-readable Markdown summaries from JSONL workflow logs.
Maintains existing JSONL format while adding accessible documentation.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


def parse_jsonl_log(log_file_path: str) -> List[Dict[str, Any]]:
    """Parse JSONL log file into list of event dictionaries."""
    events = []
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except FileNotFoundError:
        return []
    return events


def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return timestamp_str


def calculate_duration(start_time: str, end_time: str) -> str:
    """Calculate duration between two ISO timestamps."""
    try:
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        duration = (end - start).total_seconds()
        
        if duration < 1:
            return f"{duration*1000:.0f}ms"
        elif duration < 60:
            return f"{duration:.1f}s"
        elif duration < 3600:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            return f"{hours}h {minutes}m"
    except:
        return "N/A"


def extract_user_config(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract user configuration from initial_state event."""
    for event in events:
        if event.get('category') == 'initial_state':
            return event.get('payload', {})
    return None


def extract_research_info(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract research phase information."""
    research_info = {
        'mode': 'standard',
        'sources': [],
        'duration': None,
        'deep_research': {
            'enabled': False,
            'queries': [],
            'web_sources': 0,
            'social_sources': 0,
            'academic_sources': 0,
            'iterations': 0
        }
    }
    
    # Check for deep research mode
    for event in events:
        if 'deep_' in event.get('category', ''):
            research_info['mode'] = 'deep'
            research_info['deep_research']['enabled'] = True
            break
    
    if research_info['mode'] == 'deep':
        # Extract deep research details
        for event in events:
            category = event.get('category', '')
            payload = event.get('payload', {})
            
            if category == 'deep_generate_query_on_chain_end':
                queries = payload.get('output', {}).get('generated_queries', [])
                research_info['deep_research']['queries'] = queries
            
            elif category == 'deep_web_research_on_chain_end':
                research_info['deep_research']['web_sources'] += 1
            
            elif category == 'deep_social_research_on_chain_end':
                research_info['deep_research']['social_sources'] += 1
            
            elif category == 'deep_academic_research_on_chain_end':
                research_info['deep_research']['academic_sources'] += 1
            
            elif category == 'deep_reflection_on_chain_end':
                research_info['deep_research']['iterations'] += 1
            
            elif category == 'deep_finalize_on_chain_end':
                results = payload.get('output', {}).get('deep_research_results', [])
                research_info['sources'] = results
    else:
        # Extract standard research details
        for event in events:
            if event.get('category') == 'researcher_on_chain_end':
                payload = event.get('payload', {})
                research_data = payload.get('output', {}).get('research_data', [])
                research_info['sources'] = research_data
                break
    
    # Fallback: check planner input (research_data is passed to planner)
    if not research_info['sources']:
        for event in events:
            if event.get('category') == 'planner_on_chain_end':
                payload = event.get('payload', {})
                research_data = payload.get('input', {}).get('research_data', [])
                if research_data:
                    research_info['sources'] = research_data
                    break
    
    # Calculate research duration
    start_time = None
    end_time = None
    
    for event in events:
        category = event.get('category', '')
        
        if category in ['researcher_on_chain_start', 'deep_generate_query_on_chain_start']:
            start_time = event.get('timestamp')
        
        if category in ['researcher_on_chain_end', 'deep_finalize_on_chain_end']:
            end_time = event.get('timestamp')
            break
    
    if start_time and end_time:
        research_info['duration'] = calculate_duration(start_time, end_time)
    
    return research_info


def extract_outline_info(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract outline/planning information."""
    for event in events:
        if event.get('category') == 'planner_on_chain_end':
            payload = event.get('payload', {})
            outline = payload.get('output', {}).get('outline', [])
            return {
                'sections': outline,
                'section_count': len(outline)
            }
    
    # Also check interrupt event (contains approved outline)
    for event in events:
        if event.get('category') == 'interrupt':
            payload = event.get('payload', {})
            outline = payload.get('outline', [])
            if outline:
                return {
                    'sections': outline,
                    'section_count': len(outline)
                }
    
    return None


def extract_approval_info(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract human approval workflow info."""
    approval_info = {
        'required': False,
        'interrupt_time': None,
        'resume_time': None,
        'wait_duration': None
    }
    
    interrupt_event = None
    resume_event = None
    
    for event in events:
        if event.get('category') == 'interrupt':
            interrupt_event = event
            approval_info['required'] = True
            approval_info['interrupt_time'] = event.get('timestamp')
        
        elif event.get('category') == 'resume_command':
            resume_event = event
            approval_info['resume_time'] = event.get('timestamp')
    
    if approval_info['interrupt_time'] and approval_info['resume_time']:
        approval_info['wait_duration'] = calculate_duration(
            approval_info['interrupt_time'],
            approval_info['resume_time']
        )
    
    return approval_info


def extract_content_generation_info(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract content generation progress for each section."""
    sections_info = {}
    
    # Track writer/critic/visuals cycles for each section
    for event in events:
        category = event.get('category', '')
        payload = event.get('payload', {})
        
        if category == 'writer_on_chain_start':
            section_idx = payload.get('input', {}).get('current_section_index', 0)
            section_id = f"sec_{section_idx}"
            
            if section_id not in sections_info:
                sections_info[section_id] = {
                    'index': section_idx,
                    'writer_attempts': 0,
                    'critic_passes': 0,
                    'visuals_added': False,
                    'completed': False,
                    'retries': 0
                }
            
            sections_info[section_id]['writer_attempts'] += 1
        
        elif category == 'critic_on_chain_end':
            section_idx = payload.get('input', {}).get('current_section_index', 0)
            section_id = f"sec_{section_idx}"
            
            if section_id in sections_info:
                sections_info[section_id]['critic_passes'] += 1
        
        elif category == 'visuals_on_chain_end':
            section_idx = payload.get('input', {}).get('current_section_index', 0)
            section_id = f"sec_{section_idx}"
            
            if section_id in sections_info:
                sections_info[section_id]['visuals_added'] = True
                sections_info[section_id]['completed'] = True
    
    # Extract retry counts from section_retries
    for event in events:
        category = event.get('category', '')
        if '_on_chain_end' in category or '_on_chain_start' in category:
            payload = event.get('payload', {})
            input_data = payload.get('input', {}) if 'input' in payload else payload.get('output', {})
            section_retries = input_data.get('section_retries', {})
            
            for section_id, retry_count in section_retries.items():
                if section_id in sections_info:
                    sections_info[section_id]['retries'] = retry_count
    
    return sections_info


def extract_final_output_info(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract final output information."""
    for event in reversed(events):
        if event.get('category') == 'workflow_complete':
            payload = event.get('payload', {})
            publisher_data = payload.get('publisher', {})
            final_content = publisher_data.get('final_content', '')
            
            # Calculate word count
            word_count = len(final_content.split()) if final_content else 0
            
            return {
                'completed': True,
                'timestamp': event.get('timestamp'),
                'word_count': word_count,
                'content_length': len(final_content)
            }
    
    return {'completed': False}


def generate_markdown_summary(log_file_path: str) -> str:
    """Generate comprehensive Markdown summary from JSONL log."""
    events = parse_jsonl_log(log_file_path)
    
    if not events:
        return "# Workflow Summary\n\n**Status**: No events found\n"
    
    # Extract all information
    user_config = extract_user_config(events)
    research_info = extract_research_info(events)
    outline_info = extract_outline_info(events)
    approval_info = extract_approval_info(events)
    content_info = extract_content_generation_info(events)
    final_info = extract_final_output_info(events)
    
    # Calculate total workflow duration
    start_time = events[0].get('timestamp') if events else None
    end_time = events[-1].get('timestamp') if events else None
    total_duration = calculate_duration(start_time, end_time) if start_time and end_time else "N/A"
    
    # Build Markdown summary
    md_lines = []
    
    # Header
    md_lines.append("# Workflow Summary\n")
    md_lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md_lines.append(f"**Status**: {'✅ Complete' if final_info.get('completed') else '⚠️ Incomplete'}\n")
    md_lines.append(f"**Total Duration**: {total_duration}\n")
    md_lines.append(f"**Total Events**: {len(events)}\n")
    md_lines.append("\n---\n")
    
    # User Configuration
    if user_config:
        md_lines.append("\n## 📋 User Configuration\n")
        md_lines.append(f"- **Topic**: {user_config.get('topic', 'N/A')}")
        md_lines.append(f"- **Model**: {user_config.get('model_provider', 'N/A')} / {user_config.get('model_name', 'N/A')}")
        md_lines.append(f"- **Blog Size**: {user_config.get('blog_size', 'N/A').upper()} (~{user_config.get('target_word_count', 'N/A')} words)")
        md_lines.append(f"- **Target Domain**: {user_config.get('target_domain', 'N/A')}")
        md_lines.append(f"- **Research Sources**: {', '.join(user_config.get('research_sources', []))}")
        md_lines.append(f"- **Target Audience**: {user_config.get('target_audience', 'N/A')}")
        
        if user_config.get('research_guidelines'):
            md_lines.append(f"\n**Research Guidelines**:")
            for guideline in user_config.get('research_guidelines', []):
                md_lines.append(f"  - {guideline}")
        
        if user_config.get('extra_context'):
            context = user_config['extra_context']
            context_preview = context[:200] + "..." if len(context) > 200 else context
            md_lines.append(f"\n**Extra Context**: {context_preview}")
        
        md_lines.append("\n")
    
    # Research Phase
    md_lines.append("\n## 🔍 Research Phase\n")
    
    if research_info['mode'] == 'deep':
        md_lines.append(f"**Mode**: Deep Research (Multi-source)\n")
        deep = research_info['deep_research']
        md_lines.append(f"- **Queries Generated**: {len(deep['queries'])}")
        if deep['queries']:
            md_lines.append(f"  - {', '.join(f'`{q}`' for q in deep['queries'][:3])}")
        md_lines.append(f"- **Web Sources**: {deep['web_sources']}")
        md_lines.append(f"- **Social Sources**: {deep['social_sources']}")
        md_lines.append(f"- **Academic Sources**: {deep['academic_sources']}")
        md_lines.append(f"- **Research Iterations**: {deep['iterations']}")
    else:
        md_lines.append(f"**Mode**: Standard Research\n")
        md_lines.append(f"- **Sources Found**: {len(research_info['sources'])}")
    
    if research_info['duration']:
        md_lines.append(f"- **Duration**: {research_info['duration']}")
    
    # Show top sources
    if research_info['sources']:
        md_lines.append(f"\n**Top Sources**:")
        for i, source in enumerate(research_info['sources'][:5], 1):
            if isinstance(source, dict):
                url = source.get('url', 'N/A')
                title = source.get('title', 'Untitled')
                md_lines.append(f"{i}. [{title}]({url})")
    
    md_lines.append("\n")
    
    # Planning Phase
    if outline_info:
        md_lines.append("\n## 📝 Planning Phase\n")
        md_lines.append(f"**Sections Planned**: {outline_info['section_count']}\n")
        md_lines.append(f"\n**Outline**:\n")
        
        for i, section in enumerate(outline_info['sections'], 1):
            if isinstance(section, dict):
                title = section.get('title', 'Untitled')
                intent = section.get('intent', '')
                md_lines.append(f"{i}. **{title}**")
                if intent:
                    intent_preview = intent[:100] + "..." if len(intent) > 100 else intent
                    md_lines.append(f"   - *{intent_preview}*")
        
        md_lines.append("\n")
    
    # Human Approval
    if approval_info['required']:
        md_lines.append("\n## ⏸️ Human Approval\n")
        md_lines.append(f"- **Interrupt Time**: {format_timestamp(approval_info['interrupt_time'])}")
        if approval_info['resume_time']:
            md_lines.append(f"- **Resume Time**: {format_timestamp(approval_info['resume_time'])}")
            md_lines.append(f"- **Wait Duration**: {approval_info['wait_duration']}")
        else:
            md_lines.append(f"- **Status**: ⏳ Waiting for approval...")
        md_lines.append("\n")
    
    # Content Generation
    if content_info:
        md_lines.append("\n## ✍️ Content Generation\n")
        md_lines.append(f"**Sections Processed**: {len(content_info)}\n")
        
        md_lines.append("\n| Section | Writer Attempts | Critic Reviews | Visuals | Status |")
        md_lines.append("|---------|----------------|----------------|---------|--------|")
        
        for section_id in sorted(content_info.keys(), key=lambda x: content_info[x]['index']):
            info = content_info[section_id]
            status = "✅ Complete" if info['completed'] else "🔄 In Progress"
            visuals = "✅" if info['visuals_added'] else "⏳"
            
            retry_indicator = f" (🔄 {info['retries']} retries)" if info['retries'] > 0 else ""
            
            md_lines.append(
                f"| {section_id} | {info['writer_attempts']} | {info['critic_passes']} | "
                f"{visuals} | {status}{retry_indicator} |"
            )
        
        md_lines.append("\n")
    
    # Final Output
    md_lines.append("\n## 🚀 Final Output\n")
    
    if final_info.get('completed'):
        md_lines.append(f"- **Status**: ✅ Workflow Complete")
        md_lines.append(f"- **Completion Time**: {format_timestamp(final_info['timestamp'])}")
        md_lines.append(f"- **Final Word Count**: {final_info['word_count']:,} words")
        md_lines.append(f"- **Content Length**: {final_info['content_length']:,} characters")
    else:
        md_lines.append(f"- **Status**: ⚠️ Workflow Incomplete")
        md_lines.append(f"- **Last Event**: {events[-1].get('category', 'N/A')}")
        md_lines.append(f"- **Last Update**: {format_timestamp(events[-1].get('timestamp', ''))}")
    
    md_lines.append("\n")
    
    # Footer
    md_lines.append("\n---\n")
    md_lines.append(f"\n*Generated from: `{os.path.basename(log_file_path)}`*\n")
    md_lines.append(f"*Log file location: `{log_file_path}`*\n")
    
    return "\n".join(md_lines)


def save_summary(log_file_path: str, output_dir: Optional[str] = None) -> str:
    """Generate and save Markdown summary for a workflow log."""
    # Generate summary
    summary_md = generate_markdown_summary(log_file_path)
    
    # Determine output path
    if output_dir is None:
        output_dir = os.path.dirname(log_file_path)
    
    log_basename = os.path.basename(log_file_path)
    thread_id = log_basename.replace('.jsonl', '')
    output_path = os.path.join(output_dir, f"{thread_id}_summary.md")
    
    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(summary_md)
    
    return output_path


def generate_summary_for_thread(thread_id: str, workflow_logs_dir: str = "workflow_logs") -> str:
    """Generate summary for a specific thread ID."""
    log_file_path = os.path.join(workflow_logs_dir, f"{thread_id}.jsonl")
    
    if not os.path.exists(log_file_path):
        raise FileNotFoundError(f"Log file not found: {log_file_path}")
    
    return save_summary(log_file_path)


def batch_generate_summaries(workflow_logs_dir: str = "workflow_logs") -> List[str]:
    """Generate summaries for all workflow logs in directory."""
    generated_summaries = []
    
    if not os.path.exists(workflow_logs_dir):
        return generated_summaries
    
    for log_file in Path(workflow_logs_dir).glob("*.jsonl"):
        try:
            summary_path = save_summary(str(log_file))
            generated_summaries.append(summary_path)
        except Exception as e:
            print(f"Error generating summary for {log_file}: {e}")
    
    return generated_summaries


if __name__ == "__main__":
    # CLI for testing
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python workflow_summary.py <thread_id> [workflow_logs_dir]")
        print("   or: python workflow_summary.py --batch [workflow_logs_dir]")
        sys.exit(1)
    
    if sys.argv[1] == "--batch":
        logs_dir = sys.argv[2] if len(sys.argv) > 2 else "workflow_logs"
        summaries = batch_generate_summaries(logs_dir)
        print(f"Generated {len(summaries)} summaries in {logs_dir}/")
        for summary in summaries:
            print(f"  - {summary}")
    else:
        thread_id = sys.argv[1]
        logs_dir = sys.argv[2] if len(sys.argv) > 2 else "workflow_logs"
        
        try:
            summary_path = generate_summary_for_thread(thread_id, logs_dir)
            print(f"✅ Summary generated: {summary_path}")
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
