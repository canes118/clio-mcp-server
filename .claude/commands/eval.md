Run the eval harness and summarize results.

Steps:
1. Run `uv run python evals/eval_runner.py`
2. Read the output
3. Summarize: how many scenarios passed, which failed, and why
4. If any failures look like tool description issues (LLM chose wrong
   tool or passed wrong params), suggest specific docstring edits
