# Clickable Citations Feature

## Overview
The citation system automatically converts source ID tags (like `[web_3_3]`, `[int_253b_L4_2]`) in generated blog posts into clickable, numbered citations that scroll smoothly to the references section.

## Features

✅ **Backward Compatible**: Works with all existing blog posts already in your database
✅ **Automatic Detection**: Recognizes citation patterns from all sources (web, internal, academic, social)
✅ **Numbered Citations**: Converts `[web_3_3]` → `¹` (superscript numbers)
✅ **Clickable Links**: Click citation → smooth scroll to reference
✅ **Hover Tooltips**: Shows source title when hovering over citation
✅ **Visual Feedback**: Highlights referenced source briefly when clicked
✅ **Mermaid Support**: Maintains compatibility with diagram rendering

## How It Works

### 1. Citation Detection
```markdown
Input:  "AI is revolutionizing healthcare [web_3_3] and diagnosis [acad_1_1]."
Output: "AI is revolutionizing healthcare¹ and diagnosis²."
```

### 2. Reference Linking
The system:
- Extracts all `[source_id]` tags from content
- Extracts the References section
- Matches citations with references
- Assigns sequential numbers
- Creates clickable anchor links

### 3. User Experience
- **Click citation** → Smoothly scrolls to reference
- **Hover citation** → Shows source title in tooltip
- **Click reference** → Can jump back to citation (optional future feature)

## Supported Citation Formats

The system recognizes these patterns:
- `[web_N_M]` - Web sources
- `[int_XXXX_LN_M]` - Internal documents
- `[acad_N_M]` - Academic papers (Arxiv)
- `[social_N_M]` - Social media (Reddit/Twitter)
- `[deep_summary_N]` - Deep research summaries
- `[deep_cit_N_M]` - Deep research citations

## Implementation Files

### Core Logic
- **`frontend/src/lib/citations.ts`**: Citation processing utilities
  - `findCitationTags()`: Detects citation patterns
  - `extractReferences()`: Parses References section
  - `buildCitationMap()`: Maps citations to numbers
  - `processCitations()`: Main processing function

### React Component
- **`frontend/src/components/custom/MarkdownWithCitations.tsx`**: 
  - Wraps ReactMarkdown with citation processing
  - Handles smooth scrolling
  - Adds visual feedback
  - Maintains Mermaid diagram support

### Integration Points
- **`frontend/src/pages/GenerationWizard.tsx`**: Final article display
- **`frontend/src/pages/History.tsx`**: Historical blog post viewing

## Example Output

### Before (Raw Markdown)
```markdown
Recent AI advancements [web_1_1] show promise in medical imaging [acad_2_1].

## References
- [AI in Healthcare 2024](https://example.com)
- [Deep Learning for Medical Diagnosis](https://arxiv.org/...)
```

### After (Rendered HTML)
```
Recent AI advancements¹ show promise in medical imaging².

References:
1. AI in Healthcare 2024 (clickable)
2. Deep Learning for Medical Diagnosis (clickable)
```

## Styling

Citations are styled with:
- Blue color (#3B82F6 light, #60A5FA dark)
- Superscript positioning
- Hover underline
- Smooth transitions
- Reference highlighting on click (2-second fade)

## Future Enhancements

Potential improvements:
1. **Back-links**: Click reference → return to citation location
2. **Multi-citation support**: `[1,2,3]` format
3. **Citation preview popup**: Hover → show full reference in tooltip
4. **Export support**: Maintain citations in downloaded markdown
5. **Citation analytics**: Track which sources are cited most

## Testing

To test the feature:
1. Generate a new blog post with citations
2. View an existing blog post from History
3. Click on citation numbers
4. Verify smooth scrolling to references
5. Check hover tooltips
6. Test with different source types

## Backward Compatibility

The feature is fully backward compatible:
- ✅ Works with blogs generated before this feature
- ✅ No database migration required
- ✅ No backend changes needed
- ✅ Falls back gracefully if references section is missing

## Performance

- **Processing**: Happens once on component mount (memoized)
- **Re-renders**: Only when content changes
- **Bundle size**: ~3KB added for citation utilities
- **No external dependencies**: Uses existing ReactMarkdown
