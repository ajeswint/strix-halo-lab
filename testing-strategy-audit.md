# Testing strategy audit

2026-10-07. Why the keep/drop tests are shaped this way, and when that shape is the wrong test.

You test this way because the decision is a keep or a drop of one change on a fixed machine, and the only score you trust is an executable check the model cannot author, against a bar written down before the GPU run. That is the wrong test when the question stops being "did this code pass an oracle the author wrote."

## What the strategy is

Three gates, each an exit code or a count:

- **Machine.** `bench/bench.sh` under Framework's fixed conditions (pp2048 / tg128, `-ngl 999 -fa on -lm none`, `-r 3`, HIP then Vulkan). A new condition is a new label. `scripts/preflight.sh` before every load. No watchdogs: a setting is applied once at boot or resume.
- **Loop.** `bench/loop/run.py` and `bench/loop/agent.py` grade only by unit tests in bwrap (no network, read-only `/usr`, 4 GiB, 60 s). The model submits `solution.py`. It never sees the test file in the prompt. Failures come back as the last 600 characters of stderr. `solved` means the passing code also passes after the single `random.seed(N)` line is swapped to `104729`, a seed no turn saw.
- **Decision.** The measure skill: one question, one variable, a threshold committed before preflight, inconclusive means drop. Tests outrank any judge. v0 through v3 follow that shape: best-of-4 kept (+13.75 points, bar ≥ 10), Laguna as a second sampler dropped (union +0, bar ≥ 3 tasks), the feedback loop kept on v1 and confirmed on v2 (+6 tasks at 55.7% of the tokens), Laguna as a fixer dropped (1/5 vs Qwen's 3/5).

The self-check on the exam is thin on purpose. `run.py --selftest` requires every reference to pass and every empty solution to fail. `agent.py --selftest` replays a fake model through the brakes (repeat code, repeat error, budget, fix-from). It does not check that a wrong-but-plausible solution fails.

## Why each piece is there

The thing being decided is not "is the repo correct." The box is already installed. The failure mode on record is believing a claim: a fan curve, a backend, a second model, a retry loop. So a result is a delta against a baseline taken under the same build, file, flags, and sampling.

The critic is the tests because a model judge shares the failure mode you are trying to measure. Roadmap item 2 says the compiler and the tests are the critic, and the model cannot write them. bwrap is what makes that physical. `_banned()` is there because several tasks are one stdlib call (`json`, `re`, `datetime`); without the deny-list the score measures whether the model imported the answer.

The fresh seed is there because feedback leaks cases. The stderr the model sees contains the failing inputs. A later turn can hard-code those inputs. Swapping the seed and requiring that grade is the check that the program still works on inputs the conversation never contained. The oracle lives in the test file, and the reference is only a witness that some program passes. v0's tie-break tasks got a separate brute-force cross-check (0 mismatches in 1,200 draws) for the same reason: the reference must not be the definition of truth.

Held-out sets exist because a prompt iterated on the same 20 tasks measures the author. v0 hit best-of-4 = 100%, so it could no longer separate methods. v2 was written so the loop was scored on tasks it was not designed on. v3 was written because v2 left one unsolved task, and a +2 bar cannot be met on a set with one miss. The rule on v3 is that the run tunes nothing: no prompt, K, E, budget, or task edits from those numbers.

Tokens are in the bar because a retry loop and independent sampling are different searches. Solved-count alone keeps whichever side spends more draws. v1's first comparison still mixed early-stop with feedback; the writeup split them, and v2's baseline became early-stop best-of-16 so the next keep was about the feedback itself.

One variable, and sampling copied across models (Laguna got Qwen's temperature 0.6 / top_p 0.95 / top_k 20), is what makes the delta point at the change. The pre-run commit is what stops the bar moving after the number is known. loop-v0 committed the bar with the results; the skill now forbids that, because the history then cannot show the order.

## Reverse

**The exam is the author.** Spec, oracle, reference, and the next task set are the same person. v3 is explicitly shaped like the seven v2 tasks early-stop best-of-16 missed. That keeps headroom, and it also grades the next arm on this model's residue. An arm that is better on the last distribution and worse on these five shapes loses. Selftest accepts any oracle the reference agrees with. A shared bug in spec, oracle, and reference is a pass. The fresh seed rerolls the same generator; it does not introduce a second implementation. This protocol is the wrong one when you need the score to survive the author being wrong twice.

**The file the model is forbidden to see is on disk beside the solution.** `grade` writes `solution.py` and `test_solution.py` into one directory and bind-mounts it read-write at `/w`. The test process does `from solution import *`, so the solution body runs with the oracle source in the working directory. `open("test_solution.py")` is stdlib, and `_banned()` does not forbid it. A solution that reads the oracle and delegates to it passes the visible grade and the fresh-seed grade, because the swapped seed is already in that file. The prompt says not to include tests. The grader does not enforce that. This protocol is the wrong one as soon as a sample is willing to read the cwd, which is the reward hack item 3 would train.

**One fresh seed is one draw.** It catches a solution that special-cases the leaked tuples. It does not catch a solution that is wrong on a region the generator rarely hits, or a bug shared with the oracle. Tasks with no single `random.seed(N)` line are `no_fresh` and scored on the cases the model may have seen. add_duration was in that class; the 3,000-draw check was a separate script after the keep, not the harness rule.

**The sandbox is part of the task and is scored as if it were the spec.** A correct program that exceeds 4 GiB or 60 s is a fail. v0 counted a MemoryError on csv_split as a model error. Performance limits and correctness limits are one bit. A method that wins by staying small beats a method that is right and heavier.

**The written n and the practiced n disagree.** The measure skill wants enough repetitions that the delta clears run-to-run spread. The evaluator agent says one run is not a result. The keeps are one run. Seeds are not paired: with 4 slots, llama.cpp sampling is not reproducible per seed, and on v2 the same task, seed, and prompt size disagreed 5 times out of 44 (~11%). The +2 bar is a substitute for a variance estimate. It is large enough that v2's +6 survived a recount that gave feedback credit only for turn > 0. It is small enough that the next arm on v3, where +2 means 27/30 and the opening-draw flip is unmeasured on that set, can be kept or dropped by noise. The protocol is the wrong one when reversing the keep is expensive and you still have one draw.

**The control is more of the incumbent, and the bar sits on top of that.** The Laguna fixer had to beat a second Qwen pass on the same stored failures by ≥ 2 tasks and clear 3 of 5. Qwen recovered 3 of 5. DeepSeek's pre-run then requires 5 of 5 to confirm. That is the right bar if a second resident model is pure cost. It is the wrong bar if you wanted to know whether the other model is as good as more Qwen, because equality is defined as a drop.

**The score matches a deployment that has hidden tests and one action.** pass@1, best-of-N, and the loop all assume the critic runs. best-of-N is oracle selection: the tests pick the winner. That is the right number for "how often is there a good sample if we can run the tests." It does not transfer to a job with no oracle, more than one action, or a repo. Item 1, the orchestrator, is never graded by this harness. Item 3 would train on these outputs. The measure skill already flags collapse when outputs flow back into training; the task-writing rule (harder sets from whatever the last run missed) builds that training distribution out of the current model's failures.

**Set-and-forget is right while reverts are obvious.** Preflight, the fan unit, and the power profile are checked when you are about to measure or boot. Drift between repo copies and live files is the one silent divergence you do check (`scripts/drift-check.sh`), because it has already happened as two copies of the same file. A GTT, fan-duty, or profile change that sticks with no bench running is invisible until the next labeled run. That is acceptable on a single-user box whose hourly reviewer is still held. It is the wrong policy once something starts on a timer and a number can move with no label change.

## Reverse-logic summary

The strategy answers one question: under fixed weights, sampling, and hardware, does this one change raise the count of author-written tasks that pass an author-written oracle, at a token cost you named beforehand, by a margin larger than the last comparison's noise. Every rule is a way to keep that delta pointed at the change. The fresh seed, the ban list, the sandbox, the held-out set, and the pre-run commit are there so the model, the prompt, and hindsight cannot move the score.

Run the same rules backwards and the strategy fails open in four places. The oracle and the exam are the same author, and the next exam is carved from the last misses, so the score can ratify a shared mistake and can only see progress on this model's residue. The grader puts the oracle in the solution's working directory, so the "hidden" test is hidden in the prompt and present on disk. The keep is a single unreplicated draw on a sampler that already flipped 5 of 44 matched samples, with a bar that treats "more of Qwen" as the control and anything short of beating that control as a drop. And the tasks are one Python file graded by hidden tests, so a keep says nothing about the orchestrator, a tool-using loop, or a training set built from these passes.
