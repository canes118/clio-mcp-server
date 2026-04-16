Do a code review of the most recent changes.

Check for:
1. Type hints on all function signatures
2. Pydantic models used for all Clio API responses (no raw dicts)
3. HTTP calls going through client.py, not directly from tools
4. Tool docstrings written for attorney end users, not developers
5. Tests exist for any new tool or client method
6. No secrets, API keys, or .env contents in committed files

Be direct. List issues as file:line with what's wrong and how to fix.
