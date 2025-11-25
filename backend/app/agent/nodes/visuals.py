from app.agent.state import AgentState
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing import Optional
import re

class VisualsResult(BaseModel):
    needs_visual: bool = Field(description="Does this section need a diagram?")
    mermaid_code: Optional[str] = Field(description="Mermaid.js code if needed, else None")

def validate_mermaid_syntax(code: str) -> tuple[bool, str]:
    """
    Validate basic Mermaid syntax and return (is_valid, error_message).
    """
    if not code or not code.strip():
        return False, "Empty diagram code"
    
    code = code.strip()
    
    # Check if it starts with a valid diagram type
    valid_types = ['flowchart', 'graph', 'sequenceDiagram']
    if not any(code.startswith(t) for t in valid_types):
        return False, f"Must start with one of: {', '.join(valid_types)}"
    
    # Check for common syntax errors
    lines = code.split('\n')
    
    # Flowchart/Graph specific validation
    if code.startswith('flowchart') or code.startswith('graph'):
        # Check for unmatched brackets in node definitions
        for line in lines[1:]:  # Skip first line (diagram declaration)
            line = line.strip()
            if not line or line.startswith('%%'):  # Skip empty lines and comments
                continue
            
            # Count brackets
            open_brackets = line.count('[') + line.count('(') + line.count('{')
            close_brackets = line.count(']') + line.count(')') + line.count('}')
            
            if open_brackets != close_brackets:
                return False, f"Unmatched brackets in line: {line[:50]}"
            
            # Check for invalid arrow syntax
            if '-->' in line or '--->' in line or '==>' in line:
                parts = re.split(r'-->|---|===|==>', line)
                if len(parts) < 2:
                    return False, f"Invalid arrow syntax: {line[:50]}"
    
    # Check for style definitions (common error source)
    style_lines = [l for l in lines if l.strip().startswith('style ')]
    for style_line in style_lines:
        # Basic check: style nodeId fill:#xxx,stroke:#xxx
        if 'style ' in style_line and not re.search(r'style\s+\w+\s+\w+:', style_line):
            return False, f"Invalid style syntax: {style_line[:50]}"
    
    return True, ""

async def visuals_node(state: AgentState):
    idx = state.get("current_section_index", 0)
    outline = state["outline"]
    
    if idx >= len(outline):
        return Command(goto="publisher")

    section = outline[idx]
    section_id = section["id"]
    draft = state["draft_sections"].get(section_id, "")
    
    prompt = ChatPromptTemplate.from_template(
        """
        Analyze the following blog section.
        
        Content:
        {draft}
        
        Does this section explain a complex process, workflow, or hierarchy that would benefit from a diagram?
        If yes, generate a SIMPLE Mermaid.js flowchart ONLY.
        
        CRITICAL SYNTAX RULES - Follow EXACTLY:
        1. Start with: flowchart TD (Top-Down) or flowchart LR (Left-Right)
        2. Node format: nodeId[Node Text] or nodeId(Node Text)
        3. Connection format: nodeId1 --> nodeId2
        4. Use simple alphanumeric IDs (A, B, C, step1, step2, etc.)
        5. Keep node text short (max 4 words)
        6. NO special characters in node IDs
        7. NO quotes around node text unless absolutely necessary
        
        STYLING RULES for readability:
        - Use ONLY these styles at the end:
          style nodeId fill:#f0f0f0,stroke:#333,stroke-width:2px,color:#000
        - Light backgrounds: #f0f0f0, #e1f5ff, #fff9e6, #e8f5e9
        - Always use color:#000 for text
        
        EXAMPLE (follow this pattern):
        flowchart TD
            A[Start Process] --> B[Analyze Data]
            B --> C[Generate Output]
            C --> D[Review Results]
            style A fill:#e8f5e9,stroke:#333,stroke-width:2px,color:#000
            style B fill:#e1f5ff,stroke:#333,stroke-width:2px,color:#000
        
        If no diagram is needed, return needs_visual=False.
        """
    )
    
    llm = llm_service.get_llm(
        model_provider=state.get("model_provider", "anthropic"),
        model_name=state.get("model_name", "claude-haiku-4-5"),
        use_local=state.get("use_local", False)
    )
    structured_llm = llm.with_structured_output(VisualsResult)
    chain = prompt | structured_llm
    
    result = await chain.ainvoke({
        "draft": draft
    })
    
    updates = {}
    
    if result.needs_visual and result.mermaid_code:
        # Validate the generated Mermaid code
        is_valid, error_msg = validate_mermaid_syntax(result.mermaid_code)
        
        if is_valid:
            # Valid syntax - add the diagram
            final_draft = draft + f"\n\n```mermaid\n{result.mermaid_code}\n```\n"
            draft_sections = state.get("draft_sections", {}).copy()
            draft_sections[section_id] = final_draft
            updates["draft_sections"] = draft_sections
        else:
            # Invalid syntax - skip diagram and log the error
            print(f"⚠️ Skipping invalid Mermaid diagram for section {section_id}: {error_msg}")
            print(f"Generated code:\n{result.mermaid_code[:200]}...")
            # Keep the draft without the diagram (no changes to draft_sections)
        
    next_idx = idx + 1
    updates["current_section_index"] = next_idx
    
    if next_idx < len(outline):
        return Command(
            update=updates,
            goto="writer"
        )
    else:
        return Command(
            update=updates,
            goto="publisher"
        )
