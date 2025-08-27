"use client";

import { useState } from "react";

export default function Home() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);

  async function handleSearch() {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    setResults(data.results);
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">📄 RAG Chatbot with Images</h1>

      <div className="flex gap-2 mb-4">
        <input
          className="border p-2 flex-1 rounded"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask something from the PDF..."
        />
        <button
          onClick={handleSearch}
          className="bg-blue-500 text-white px-4 py-2 rounded"
        >
          Search
        </button>
      </div>

      <div className="space-y-4">
        {results.map((r, i) => (
          <div key={i} className="border p-3 rounded shadow">
            <p className="mb-2">{r.text}</p>
            {r.images?.map((img: string, j: number) => (
              <img
                key={j}
                src={`/${img.trim()}`}
                alt="PDF illustration"
                className="max-w-full border rounded mb-2"
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
