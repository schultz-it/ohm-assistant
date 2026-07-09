import { useState } from "preact/hooks";
import { Bollette } from "./tabs/Bollette.jsx";
import { Storico } from "./tabs/Storico.jsx";
import { Live } from "./tabs/Live.jsx";
import { Setup } from "./tabs/Setup.jsx";

const TABS = [
  { id: "bollette", label: "Bollette", icon: "🧾" },
  { id: "storico", label: "Storico", icon: "📊" },
  { id: "live", label: "Live", icon: "🌡️" },
  { id: "setup", label: "Setup", icon: "⚙️" },
];

export function App() {
  const [tab, setTab] = useState("bollette");

  return (
    <div class="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100 pb-20">
      <header class="px-4 py-3 flex items-center gap-2 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 sticky top-0 z-10">
        <span class="text-2xl">⚡</span>
        <h1 class="text-lg font-semibold">Ohm Assistant</h1>
      </header>

      <main class="max-w-xl mx-auto p-4">
        {tab === "bollette" && <Bollette />}
        {tab === "storico" && <Storico />}
        {tab === "live" && <Live />}
        {tab === "setup" && <Setup />}
      </main>

      <nav class="fixed bottom-0 inset-x-0 border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex">
        {TABS.map((x) => (
          <button
            key={x.id}
            onClick={() => setTab(x.id)}
            class={`flex-1 py-2 text-center text-xs ${
              tab === x.id
                ? "text-amber-600 dark:text-amber-400 font-semibold"
                : "text-gray-500"
            }`}
          >
            <div class="text-xl leading-6">{x.icon}</div>
            {x.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
