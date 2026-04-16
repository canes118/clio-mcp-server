Run through the pre-publish checklist for this MCP server.

1. Run `uv run pytest` — report pass/fail
2. Run `uv run python evals/eval_runner.py` — report pass/fail
3. Check that README.md has: installation instructions, tool
   descriptions, example usage, and architecture diagram reference
4. Check that .env.example lists all required env vars
5. Check that pyproject.toml has correct metadata (name, version,
   description, author, license)
6. Check that .gitignore includes .env, evals/results/, __pycache__
7. List anything missing or broken
