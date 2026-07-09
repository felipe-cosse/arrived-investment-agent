/** Responsive two-pane shell (§4, R30): fixed-width chat on the left and a
 * fluid data panel on the right at `md` and up; below `md` the panes stack
 * vertically with the data panel reachable beneath the chat. On desktop each
 * pane scrolls internally; on mobile the page scrolls naturally.
 */

import type { ReactElement, ReactNode } from "react";

interface TwoPaneProps {
  chat: ReactNode;
  data: ReactNode;
}

export default function TwoPane({ chat, data }: TwoPaneProps): ReactElement {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-lg p-lg md:flex-row">
      <section aria-label="Chat" className="flex min-h-0 flex-col md:w-96 md:shrink-0">
        {chat}
      </section>
      <section aria-label="Data panel" className="min-h-0 min-w-0 flex-1 md:overflow-y-auto">
        {data}
      </section>
    </div>
  );
}
