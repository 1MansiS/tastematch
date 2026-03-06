# Skill: Add a New Menu Input Type

Invoke when adding support for a new input source (e.g. "add YouTube", "add Instagram", "add Yelp").

## Steps

1. **Create** `tools/your_source.py`
   - Implement `async fetch(input: str) -> RawMenuContent`
   - Return a `RawMenuContent` Pydantic model with:
     - `text: str` — extracted text content
     - `source: str` — where it came from
     - `confidence: float` — 0.0 to 1.0 reflecting completeness/reliability
     - `format: str` — "html" | "pdf" | "image" | "text"

2. **Register** in `agent/router.py`
   - Add detection logic (URL pattern, file extension, etc.)
   - Route to the new tool

3. **Place** in retrieval fallback chain in `agent/retrieval.py`
   - Where does this source fit in the strategy order?
   - What happens if it fails?

4. **Write tests** in `tests/test_retrieval.py`
   - Mock the external source
   - Test successful extraction
   - Test failure + fallback behavior
   - Test confidence score reflects content quality

5. **Update README**
   - Add row to Supported Input Types table
   - Note any caveats (rate limits, ToS notes, setup required)

6. **Trigger commit reminder**
