/** Join references by stable source ID, never by citation appearance order. */
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
interface Reference { title: string; url?: string; id?: string }
const referencesPattern = /##\s+References\s*\n([\s\S]*?)(?=\n##|\n#|$)/i;
const sourcePattern = /^(?:web|int|acad|social|deep)_|^user_context$/i;
const unescapeMarkdown = (value: string) => value.replace(/\\([\\[\]])/g, '$1');

export function extractReferences(markdown: string): Reference[] {
  const section = markdown.match(referencesPattern)?.[1];
  if (!section) return [];
  return section.split('\n').filter(line => line.trim().startsWith('-')).map(line => {
    let text = line.trim().replace(/^-\s*/, '');
    const idMatch = text.match(/^\[([\w-]+)\]\s+/);
    const id = idMatch && sourcePattern.test(idMatch[1]) ? idMatch[1] : undefined;
    if (id) text = text.slice(idMatch![0].length);
    const link = text.match(/^\[((?:\\.|[^\]])+)\]\((?:<([^>]+)>|(.+))\)$/);
    return link
      ? { id, title: unescapeMarkdown(link[1]), url: link[2] || link[3] }
      : { id, title: unescapeMarkdown(text.replace(/\s*\(Internal Document\)$/, '')) };
  });
}

export function findCitationTags(content: string): string[] {
  // References and code examples are not in-text citations.
  const prose = content.replace(referencesPattern, '')
    .replace(/```[\s\S]*?```|`[^`]*`/g, '')
    .replace(/!?\[[^\]]*\]\([^)]+\)/g, '');
  return [...new Set([...prose.matchAll(/\[([\w-]+)\]/g)]
    .map(match => match[1]).filter(tag => sourcePattern.test(tag)))];
}

export function buildCitationMap(markdown: string): Map<string, Citation> {
  const tags = findCitationTags(markdown);
  const references = extractReferences(markdown);
  const byId = new Map(references.filter(ref => ref.id).map(ref => [ref.id!, ref]));
  // Old publisher output had no IDs but always sorted references by source ID.
  // Only infer that historical mapping when the counts match exactly.
  if (references.length === tags.length && references.every(ref => !ref.id)) {
    [...tags].sort().forEach((tag, index) => byId.set(tag, references[index]));
  }
  const result = new Map<string, Citation>();
  for (const tag of tags) {
    const reference = byId.get(tag);
    if (reference) result.set(tag, { id: tag, number: result.size + 1,
      title: reference.title, url: reference.url });
  }
  return result;
}

const escapeHtml = (value: string) => value.replace(/[&<>"']/g,
  char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]!);
const publicLink = (value?: string) => value && /^https?:\/\//i.test(value) ? value : undefined;

export function processCitations(markdown: string): ProcessedContent {
  const citationMap = buildCitationMap(markdown);
  const match = markdown.match(referencesPattern);
  const section = match?.[0] || '';
  let prose = markdown.replace(referencesPattern, '');
  // Keep code and existing Markdown links intact, even if their labels look like IDs.
  prose = prose.replace(/(```[\s\S]*?```|`[^`]*`|!?\[[^\]]*\]\([^)]+\))|\[([\w-]+)\]/g,
    (whole, protectedText: string | undefined, tag: string | undefined) => {
      if (protectedText || !tag) return whole;
      const citation = citationMap.get(tag);
      return citation ? `<sup><a href="#ref-${tag}" class="citation-link" title="${escapeHtml(citation.title || tag)}">[${citation.number}]</a></sup>` : whole;
    });
  if (match && citationMap.size) {
    const references = [...citationMap.values()].map(citation => {
      const title = escapeHtml(citation.title || citation.id);
      const url = publicLink(citation.url);
      const label = url ? `<a href="${escapeHtml(url)}">${title}</a>` : title;
      return `<div id="ref-${citation.id}"><strong>${citation.number}.</strong> ${label}</div>`;
    });
    prose += `## References\n\n${references.join('\n')}\n`;
  } else {
    prose += section;
  }
  return { content: prose, citations: [...citationMap.values()], referencesSection: section };
}
