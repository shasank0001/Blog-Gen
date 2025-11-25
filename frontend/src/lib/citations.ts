/**
 * Citation Processing Utilities
 * 
 * Handles detection and transformation of citation tags in markdown content.
 * Supports formats like [web_3_3], [int_253b_L4_2], [acad_1_1], [social_2_1]
 */

export interface Citation {
  id: string;
  number: number;
  title?: string;
  url?: string;
}

export interface ProcessedContent {
  content: string;
  citations: Citation[];
  referencesSection: string;
}

/**
 * Extract reference section from markdown content
 */
export function extractReferences(markdown: string): { title: string; url?: string; id?: string }[] {
  const references: { title: string; url?: string; id?: string }[] = [];
  
  // Find the References section
  const refMatch = markdown.match(/##\s+References\s*\n([\s\S]*?)(?=\n##|\n#|$)/i);
  if (!refMatch) return references;
  
  const refSection = refMatch[1];
  
  // Parse markdown list items with optional links
  // Formats: - [Title](url) or - Title (Internal Document)
  const lines = refSection.split('\n');
  
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('-')) continue;
    
    // Try to match markdown link: - [Title](url)
    const linkMatch = trimmed.match(/^-\s*\[([^\]]+)\]\(([^)]+)\)/);
    if (linkMatch) {
      references.push({
        title: linkMatch[1],
        url: linkMatch[2]
      });
      continue;
    }
    
    // Try to match plain text: - Title (Internal Document)
    const plainMatch = trimmed.match(/^-\s*(.+?)(?:\s*\(Internal Document\))?$/);
    if (plainMatch) {
      references.push({
        title: plainMatch[1]
      });
    }
  }
  
  return references;
}

/**
 * Find all citation tags in content (e.g., [web_3_3], [int_abc_1])
 */
export function findCitationTags(content: string): string[] {
  // Match citation patterns: [word_something] but not markdown links
  // Exclude patterns that are markdown links: [text](url) or ![alt](url)
  const citations: string[] = [];
  const citationRegex = /\[([a-zA-Z0-9_\-]+)\]/g;
  
  // Remove markdown links and images first to avoid false matches
  const cleanContent = content
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '') // Remove images
    .replace(/\[([^\]]+)\]\([^)]+\)/g, ''); // Remove links
  
  let match;
  while ((match = citationRegex.exec(cleanContent)) !== null) {
    const tag = match[1];
    // Only include if it looks like a source ID (has underscore and numbers)
    if (tag.match(/^(web|int|acad|social|deep)_/i)) {
      citations.push(tag);
    }
  }
  
  return [...new Set(citations)]; // Remove duplicates
}

/**
 * Build citation map from content
 */
export function buildCitationMap(markdown: string): Map<string, Citation> {
  const citationMap = new Map<string, Citation>();
  
  // Extract citations from content
  const citationTags = findCitationTags(markdown);
  
  // Extract references
  const references = extractReferences(markdown);
  
  // Assign numbers to citations in order of appearance
  citationTags.forEach((tag, index) => {
    const citation: Citation = {
      id: tag,
      number: index + 1,
    };
    
    // Try to match with reference if available
    if (references[index]) {
      citation.title = references[index].title;
      citation.url = references[index].url;
    }
    
    citationMap.set(tag, citation);
  });
  
  return citationMap;
}

/**
 * Process markdown content to make citations clickable
 * Converts [source_id] tags to clickable superscript numbers
 */
export function processCitations(markdown: string): ProcessedContent {
  const citationMap = buildCitationMap(markdown);
  
  let processedContent = markdown;
  
  // Replace citation tags with HTML anchor links
  citationMap.forEach((citation, tag) => {
    const regex = new RegExp(`\\[${tag}\\]`, 'g');
    const replacement = `<sup><a href="#ref-${tag}" class="citation-link" title="${citation.title || tag}">[${citation.number}]</a></sup>`;
    processedContent = processedContent.replace(regex, replacement);
  });
  
  // Add IDs to references section for anchor linking
  const refMatch = processedContent.match(/(##\s+References\s*\n)([\s\S]*?)(?=\n##|\n#|$)/i);
  if (refMatch) {
    const refSection = refMatch[2];
    const lines = refSection.split('\n');
    const processedLines: string[] = [];
    
    let refIndex = 0;
    const citationArray = Array.from(citationMap.entries());
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('-') && refIndex < citationArray.length) {
        const [tag, citation] = citationArray[refIndex];
        // Keep the content on same line with proper span wrapping
        const content = line.substring(line.indexOf('-') + 1).trim();
        processedLines.push(`<div id="ref-${tag}" style="margin-bottom: 0.5rem;"><strong>${citation.number}.</strong> ${content}</div>`);
        refIndex++;
      } else if (trimmed) {
        processedLines.push(line);
      }
    }
    
    processedContent = processedContent.replace(
      refMatch[0],
      `${refMatch[1]}${processedLines.join('\n')}\n`
    );
  }
  
  return {
    content: processedContent,
    citations: Array.from(citationMap.values()),
    referencesSection: refMatch ? refMatch[0] : ''
  };
}
