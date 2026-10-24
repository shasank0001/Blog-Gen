import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { processCitations } from '@/lib/citations';
import { Mermaid } from './Mermaid';

interface MarkdownWithCitationsProps {
  content: string;
  className?: string;
}

/**
 * Renders markdown content with clickable citations
 * Automatically processes citation tags like [web_3_3] into numbered superscripts
 */
export default function MarkdownWithCitations({ content, className = '' }: MarkdownWithCitationsProps) {
  // Process citations once when content changes
  const processed = useMemo(() => {
    if (!content) return { content: '', citations: [], referencesSection: '' };
    return processCitations(content);
  }, [content]);

  return (
    <div className={className}>
      <style>{`
        .citation-link {
          text-decoration: none;
          color: rgb(59 130 246);
          font-weight: 500;
          transition: color 0.2s;
        }
        .citation-link:hover {
          color: rgb(37 99 235);
          text-decoration: underline;
        }
        .dark .citation-link {
          color: rgb(96 165 250);
        }
        .dark .citation-link:hover {
          color: rgb(147 197 253);
        }
        sup {
          line-height: 0;
        }
      `}</style>
      
      <ReactMarkdown
        rehypePlugins={[rehypeRaw, [rehypeSanitize, { ...defaultSchema, attributes: { ...defaultSchema.attributes, a: [...(defaultSchema.attributes?.a || []), ['className', 'citation-link']] } }]]}
        components={{
          code({ className, children }) {
            const match = /language-(\w+)/.exec(className || '');
            if (match && match[1] === 'mermaid') {
              return <Mermaid chart={String(children).replace(/\n$/, '')} />;
            }
            return (
              <code className={className}>
                {children}
              </code>
            );
          },
          a({ href, children, className, title }) {
            // Smooth scroll for citation links
            if (href?.startsWith('#ref-')) {
              return (
                <a
                  href={href}
                  onClick={(e) => {
                    e.preventDefault();
                    const target = document.getElementById(`user-content-${href.substring(1)}`);
                    if (target) {
                      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                      // Highlight the reference briefly
                      target.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
                      setTimeout(() => {
                        target.style.backgroundColor = '';
                      }, 2000);
                    }
                  }}
                  className={className}
                  title={title}
                >
                  {children}
                </a>
              );
            }
            return <a href={href} className={className} title={title}>{children}</a>;
          }
        }}
      >
        {processed.content}
      </ReactMarkdown>
    </div>
  );
}
