import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import Markdown from "./Markdown";

describe("Markdown", () => {
  it("renders **bold** as <strong>, not literal asterisks", () => {
    const html = renderToStaticMarkup(<Markdown text="Invest **wisely** today" />);
    expect(html).toContain("<strong");
    expect(html).toContain("wisely");
    expect(html).not.toContain("**");
  });

  it("renders a bullet list with one <li> per item", () => {
    const html = renderToStaticMarkup(<Markdown text={"Options:\n\n- one\n- two\n- three"} />);
    expect(html).toContain("<ul");
    expect(html.match(/<li/g)?.length).toBe(3);
  });

  it("styles every heading level (h1–h6), so none flatten to body text", () => {
    const html = renderToStaticMarkup(
      <Markdown text={"# a\n\n## b\n\n### c\n\n#### d\n\n##### e\n\n###### f"} />,
    );
    // Every rendered heading carries a className — no unstyled h4/h5/h6.
    expect(html.match(/<h[1-6][^>]*class=/g)?.length).toBe(6);
  });

  it("renders inline code and links", () => {
    const html = renderToStaticMarkup(
      <Markdown text={"Call `build_investment_plan` — see [docs](https://example.com)"} />,
    );
    expect(html).toContain("<code");
    expect(html).toContain('href="https://example.com"');
  });
});
