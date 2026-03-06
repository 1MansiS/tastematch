# Skill: Add a New LLM Provider

Invoke when asked to add a new LLM provider (e.g. "add Groq", "add Cohere", "add Mistral API").

## Steps

1. **Create** `llm/yourprovider.py`
   - Inherit from `BaseLLMProvider` in `llm/base.py`
   - Implement `async complete(prompt: str) -> str`
   - Implement `async vision(prompt: str, image: bytes) -> str`
   - If provider has no vision support, raise `NotImplementedError` with a clear message

2. **Register** in `llm/factory.py`
   - Add new case to the provider switch
   - Return the new provider instance

3. **Update** `config.json`
   - Add provider as a valid option with its default model names

4. **Write tests** in `tests/test_llm_factory.py`
   - Mock the provider API call
   - Test `complete()` happy path
   - Test `vision()` happy path or `NotImplementedError` if unsupported
   - Test factory correctly instantiates the new provider from config

5. **Update README**
   - Add row to the Supported Providers table
   - Include: provider name, text model, vision model, cost, setup link

6. **Trigger commit reminder**
