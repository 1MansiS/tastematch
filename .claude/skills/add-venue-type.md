# Skill: Add a New Venue Type

Invoke when adding support for a new venue category
(e.g. "add beer bars", "add ice cream shops", "add bakeries").

This should require zero changes to the core agent loop.
All venue-type logic is contained in the detector, profile, and matcher only.

## Steps

1. **Add detection rule** in `agent/venue_detector.py`
   - Add the new venue type to the VenueType enum
   - Add keyword/category detection logic for the new type
   - Add Google Places category mappings if applicable

2. **Add profile section** to `profile.json` and `models/profile.py`
   - Design the profile schema for this venue type
   - Add to the Pydantic `TasteProfile` model as an optional section
   - Add example values to the default `profile.json`

3. **Add matcher logic** in `agent/matcher.py`
   - Add a matching function for the new venue type
   - Load `profile.your_venue` and match against parsed items
   - Return a typed verdict consistent with existing venue types

4. **Write tests**
   - `tests/test_venue_detector.py` — detects new type correctly, doesn't
     misclassify existing types
   - `tests/test_matcher.py` — matches and scores correctly for new type

5. **Update README**
   - Move venue type from "Future Venue Types" to the roadmap/supported list
   - Update profile.json example if schema changed

6. **Verify no agent code changed**
   - `retrieval.py`, `parser.py`, `router.py` should be untouched
   - If they were touched, reconsider the design

7. **Trigger commit reminder**
