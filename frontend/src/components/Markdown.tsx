/** Renders assistant markdown (bold, italics, lists, headings, code, links,
 *  tables) as React elements styled with DESIGN.md tokens. react-markdown emits
 *  a React tree — no raw-HTML injection, so no XSS surface (R23-adjacent).
 *  Shared by the chat transcript and the AI plan narrative.
 */

import type { ReactElement } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Inline-code chip keeps sub-token micro-padding: DESIGN.md's smallest spacing
// token (sm = 8px) is too coarse for an inline element without breaking line rhythm.
const CODE = "rounded-sm bg-primary/5 px-1 py-0.5 font-mono text-label text-primary";
const SUBHEAD = "text-body font-semibold text-secondary";

const COMPONENTS: Components = {
  p: ({ children }) => <p className="text-body leading-relaxed">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-primary">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer"
       className="text-accent underline underline-offset-2 hover:opacity-80">
      {children}
    </a>
  ),
  ul: ({ children }) => <ul className="list-disc space-y-sm pl-lg text-body">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal space-y-sm pl-lg text-body">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }) => <h3 className="text-h2 font-semibold text-primary">{children}</h3>,
  h2: ({ children }) => <h4 className="text-body font-semibold text-primary">{children}</h4>,
  h3: ({ children }) => <h5 className={SUBHEAD}>{children}</h5>,
  h4: ({ children }) => <h6 className={SUBHEAD}>{children}</h6>,
  h5: ({ children }) => <h6 className={SUBHEAD}>{children}</h6>,
  h6: ({ children }) => <h6 className={SUBHEAD}>{children}</h6>,
  code: ({ children }) => <code className={CODE}>{children}</code>,
  pre: ({ children }) => (
    <pre className="overflow-x-auto rounded-md bg-primary/5 p-md font-mono text-label
                    [&>code]:bg-transparent [&>code]:p-0">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-secondary/30 pl-md text-secondary">{children}</blockquote>
  ),
  hr: () => <hr className="border-secondary/20" />,
  table: ({ children }) => (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-label">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-secondary/20 px-sm py-sm text-left font-semibold text-primary">{children}</th>
  ),
  td: ({ children }) => <td className="border border-secondary/20 px-sm py-sm">{children}</td>,
};

export default function Markdown({ text }: { text: string }): ReactElement {
  return (
    <div className="space-y-sm break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
