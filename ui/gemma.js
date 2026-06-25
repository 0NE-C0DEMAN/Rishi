/* ==========================================================================
   gemma.js — Google Gemini / Gemma client (client-side, Gemini API only).
   Generates the Zone-4 explainable-AI root-cause narrative on demand.

   Mirrors the ParkerJones Gemini path: a plain fetch to
   generativelanguage.googleapis.com, with chain-of-thought stripped at the
   PART level (drop response parts flagged `thought: true`). Per ParkerJones'
   findings, config-level suppression (thinkingConfig) does NOT work for Gemma,
   so we omit it and rely on part filtering + the prompt instruction.
   ========================================================================== */
(() => {
  "use strict";

  const MODEL = "gemma-4-26b-a4b-it";
  const ENDPOINT = (model, key) =>
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(key)}`;

  const SYSTEM = `You are the explainable-AI (XAI) module of an enterprise project-governance platform.
Given the current simulated risk telemetry, write a root-cause diagnostic of 2-4 sentences, then one concrete recommended governance action on a new line beginning with "Recommended action:".
Be specific and technical; name the dominant risk driver and the affected phase. Use ONLY the numbers provided — never invent metrics.
Output plain prose only: no markdown, no headings, no bullet points, no preamble, and no chain-of-thought.`;

  // Gemma returns chain-of-thought as SEPARATE parts flagged thought:true.
  // Keep only the answer parts.
  function stripThought(parts) {
    return (parts || [])
      .filter((p) => !p.thought)
      .map((p) => p.text || "")
      .join("")
      .trim();
  }

  async function generateDiagnostic(state) {
    const key = window.__GOV_KEY__;
    if (!key) throw new Error("No Gemini key configured (set gemini_api_key in secrets).");

    const prompt = [
      `Composite governance risk: ${state.composite}% (action threshold ${state.threshold}%).`,
      `Overall status: ${state.level}.`,
      `Dominant risk driver: ${state.driver}.`,
      `Most affected phase: ${state.phase}.`,
      `Control inputs — latency factor ${state.lf}x, ingestion load ${state.ld}x, risk sensitivity ${state.sn}x.`,
    ].join("\n");

    const body = {
      systemInstruction: { parts: [{ text: SYSTEM }] },
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      // Gemma: no thinkingConfig / responseMimeType (the API rejects them).
      // Budget must be generous: Gemma spends output tokens THINKING first, then
      // answers — too small a cap (e.g. 400) is consumed entirely by the thought
      // part, leaving nothing after the strip. 2048 leaves room for both.
      generationConfig: { temperature: 0.5, maxOutputTokens: 2048 },
    };

    const res = await fetch(ENDPOINT(MODEL, key), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let msg = `Gemini API ${res.status}`;
      try { msg = (await res.json())?.error?.message || msg; } catch (e) { /* ignore */ }
      throw new Error(msg);
    }
    const data = await res.json();
    const cand = data && data.candidates && data.candidates[0];
    if (cand && (cand.finishReason === "SAFETY" || cand.finishReason === "RECITATION")) {
      throw new Error(`Gemma blocked the response (${cand.finishReason}).`);
    }
    const text = stripThought(cand && cand.content && cand.content.parts);
    if (!text) throw new Error("Empty response from Gemma.");
    return text;
  }

  window.GovAI = { generateDiagnostic, MODEL };
})();
