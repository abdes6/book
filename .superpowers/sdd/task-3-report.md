# Task 3 Report: Routes

## What was implemented

Created `app/ai_reader/routes.py` with all 8 API endpoints:

| Route | Method | Function | Description |
|-------|--------|----------|-------------|
| `/ai-reader/` | GET | `index` | Render the AI reader page |
| `/ai-reader/books` | GET | `book_list` | JSON list of user's books |
| `/ai-reader/<book_id>/chat` | GET | `get_chat` | Get chat history for a book |
| `/ai-reader/<book_id>/chat` | POST | `send_message` | Send message to AI (CSRF exempt) |
| `/ai-reader/<book_id>/summary` | GET | `get_summary` | AI-generated summary (cached) |
| `/ai-reader/<book_id>/review` | GET | `get_review` | AI-generated review (cached) |
| `/ai-reader/<book_id>/analysis` | GET | `get_analysis` | AI analysis of highlights (cached) |
| `/ai-reader/<book_id>/recommend` | GET | `get_recommendations` | Book recommendations |

## Files changed

1. **Created:** `app/ai_reader/routes.py` — all 8 routes
2. **Modified:** `app/__init__.py:55` — added `url_prefix='/ai-reader'` to blueprint registration (was missing, would cause route conflicts with main blueprint's `/`)

## Self-review findings

- All routes use `frontend_login_required` and extract `user_id` via `current_user.get_id().replace('u_', '')`
- `send_message` route is `@csrf.exempt` (JSON-based POST, no form CSRF token)
- Cache-before-compute pattern for summary/review/analysis via `BookAIContent` query
- `get_analysis` returns 400 if no highlights exist
- Error handling wraps all AI service calls with 500 fallback

## Issues / concerns

- **Template missing:** Route `index()` renders `ai_reader/index.html` which does not yet exist. Expected to be created in Task 4 (frontend).
- The blueprint was missing `url_prefix='/ai-reader'` in `app/__init__.py` — fixed in this task. Without it, routes like `@bp.route('/')` would conflict with the main blueprint's home route.
