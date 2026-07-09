/** App shell placeholder for build-order step 6. Step 7 replaces this with the
 * two-pane layout (chat left, data panel right, stacking below `md` — §4, R30).
 */

import type { ReactElement } from "react";

export default function App(): ReactElement {
  return (
    <main className="min-h-screen bg-background p-lg">
      <h1 className="text-h1 font-semibold text-primary">Arrived Investment Agent</h1>
      <p className="mt-sm text-body text-secondary">
        Chat and the data explorer arrive in the next build phase.
      </p>
    </main>
  );
}
