# CRAwDAD: what the code does (read 2026-10-15)

Sources: arXiv 2511.22854 (12 pp, appendix A-D read in full) and github.com/finnvamosi/CRAwDAD at `2fe8d0badea3` (2025-12-06; `run.py`, `generation.py`, `utils.py`). The repo has no licence file, so its code is paraphrased here, not copied. Only the appendix prompts (published with the paper) are quoted. Diagram round numbers R1-R4 are the code's rounds 0-3.

## Protocol as coded

- Models (Ollama tags): `qwen3:32b`, `deepseek-r1:32b`; extractor `granite3.3:2b`. Endpoint `/api/generate` (single prompt string, no chat messages).
- Sampling: temperature 0.6, top_p 0.95. top_k is not set (Ollama default 40). No sampling seed, so runs are not reproducible. The coin uses `random.seed(42)`.
- Context: `num_ctx` 2048 for the first answer, then 2048 x (round + 1): 4096, 6144, 8192. The paper does not state this. For reasoning models 2048 is small. Appendix A reports replies of 40-46 min that repeat the same snippets. That fits Ollama's context shift dropping the prompt, but this is our hypothesis and unproven.
- Coin picks the first speaker. Only the first speaker answers alone (round 0, CausalCoT 7-step prompt, appendix B). The second speaker's first output is already a critique. So the protocol never measures the second model solo; our exclusive-solve check has to be a separate run.
- Debate prompt (appendix C): "You and another LLM are being asked ... I believe two heads are better than one, so I ask that you debate with the other LLM to reach a consensus on the answer." This is followed by the question, the "be confident / no trick questions" line and the history. The 7-step CausalCoT instructions are not repeated in debate rounds.
  - Odd rounds (second speaker, critic; appendix C): "Carefully read the causal query, then scrutinize your opponent's solution. If you identify any flaws in their reasoning or errors in their calculations, you should point them out and suggest corrections. You should make explicit references to your opponent's response."
  - Even rounds (first speaker, defender; code only, not in the paper): consider the opponent's response, then defend the previous answer or be persuaded, with explicit references to the opponent.
  - Every prompt ends: final yes/no answer, no numbers, plus a stated confidence 0.0-1.0.
- History: all previous rounds, not just the last. They are labelled "Your original answer:", "Your response:" or "Opponent's response:" and fenced with `==========`. Each entry is the reply text from `</think>` onward. The thinking trace is withheld, but the visible answer is passed in full, not shortened.
- Extractor: Granite gets the post-`</think>` text and returns JSON `{answer, confidence}` under a schema with thinking off. A missing confidence is taken as 0.6.
- Stop: after each debate round, if the extracted yes/no equals the previous round's, the debate ends. Maximum 4 replies. Confidence is recorded but never used for control.
- Score: the last reply's answer against the CLadder key, credited to the first speaker. Default range: CLadder balanced indices 10000-10111.

## Defects in the code (affect how far the paper's numbers can be trusted, not our design)

1. If a reply has no `</think>`, `find` returns -1 and the slice keeps only the last character. The history and the extractor then see one character. Whether this happened depends on how Ollama returned thinking for these tags; the code cannot tell us.
2. Extraction failures become coin flips. A non-yes/no extraction is replaced with a random yes/no, and a parse error returns `invalid_result()`, also a random answer. The paper reports no count of these.
3. Agreement is computed on the extracted answers, so a coin-flipped extraction can end a debate or extend it.

## What carries over to our code-task version (crawdad-qd-v2, slots in README Models)

- Keep: the coin, max 4 replies, the critic is not forced to find a flaw, the defend-or-be-persuaded prompt, full labelled history, trace withheld, stop on agreement, grade only at the leaf.
- Replace: yes/no with `solution.py` plus a verdict line (`accept` / `reject` of the opponent's code). Agreement = the critic accepts. The extractor is the agent.py code-block parser, with no model. A parse failure is a failed turn, never a random answer.
- Deviate on purpose: context sized to the reasoning budget, not 2048; top_k stated; sampling seeds per reply, as in our runs.
- crawdad-qd-v2 updated 2026-10-15 to Qwen3-32B / R1-Distill-Qwen-32B, with RAG and slot labels; turn times unmeasured. Smoke tg at first load (one cold request, ~1.1k prompt): 11.1 / 11.2 t/s, above the ~6 t/s ceiling estimated from ~117 GB/s (a MoE-fitted figure). One request: spread and tg at depth unmeasured.
