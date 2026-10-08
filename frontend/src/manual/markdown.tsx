import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { parseMarkdown, slug } from "./parse";

const INLINE = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;

/** Renders inline code, bold and links; only in-app links (starting with "/") become clickable. */
export function Inline({ text }: { text: string }) {
  const parts = text.split(INLINE);
  return (
    <>
      {parts.map((part, idx) => {
        if (part.startsWith("`") && part.endsWith("`") && part.length > 1)
          return (
            <code key={idx} className="rounded bg-slate-100 px-1 py-0.5 text-[0.9em]">
              {part.slice(1, -1)}
            </code>
          );
        if (part.startsWith("**") && part.endsWith("**") && part.length > 3)
          return <strong key={idx}>{part.slice(2, -2)}</strong>;
        const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
        if (link) {
          const [, label = "", href = ""] = link;
          return href.startsWith("/") ? (
            <Link key={idx} to={href} className="text-blue-700 underline">
              {label}
            </Link>
          ) : (
            <Fragment key={idx}>{label}</Fragment>
          );
        }
        return <Fragment key={idx}>{part}</Fragment>;
      })}
    </>
  );
}

export function Markdown({ source }: { source: string }) {
  const blocks = parseMarkdown(source);
  const out: ReactNode[] = blocks.map((b, idx) => {
    switch (b.kind) {
      case "heading": {
        const cls = ["", "mb-4 text-2xl font-bold", "mb-2 mt-8 text-lg font-semibold", "mb-1 mt-5 font-semibold"][
          b.level
        ];
        const Tag = `h${b.level}` as "h1" | "h2" | "h3";
        return (
          <Tag key={idx} id={slug(b.text)} className={cls}>
            <Inline text={b.text} />
          </Tag>
        );
      }
      case "paragraph":
        return (
          <p key={idx} className="my-2 leading-7">
            <Inline text={b.text} />
          </p>
        );
      case "list": {
        const Tag = b.ordered ? "ol" : "ul";
        return (
          <Tag key={idx} className={`my-2 ml-6 leading-7 ${b.ordered ? "list-decimal" : "list-disc"}`}>
            {b.items.map((it, j) => (
              <li key={j}>
                <Inline text={it} />
              </li>
            ))}
          </Tag>
        );
      }
      case "code":
        return (
          <pre key={idx} className="my-3 overflow-x-auto rounded bg-slate-900 p-3 text-sm text-slate-100">
            <code>{b.text}</code>
          </pre>
        );
      case "note":
        return (
          <div key={idx} className="my-3 rounded border-l-4 border-blue-400 bg-blue-50 px-3 py-2 text-sm leading-6">
            <Inline text={b.text} />
          </div>
        );
      case "table":
        return (
          <div key={idx} className="my-3 overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  {b.header.map((c, j) => (
                    <th key={j}>
                      <Inline text={c} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {b.rows.map((r, j) => (
                  <tr key={j}>
                    {r.map((c, k) => (
                      <td key={k}>
                        <Inline text={c} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
    }
  });
  return <article className="max-w-3xl text-sm text-slate-800">{out}</article>;
}
