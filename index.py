import os
import requests
from flask import Flask, request, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from snapchat_dl.snapchat_dl import SnapchatDL
from snapchat_dl.utils import UserNotFoundError

# Configuration for caching
config = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
}

# Initialize the Flask app
app = Flask(__name__)
app.config.from_mapping(config)

# Initialize caching
cache = Cache(app)

# Initialize Snapchat downloader
dl = SnapchatDL()

# Rate limiting configuration
limiter = Limiter(
    key_func=get_remote_address, 
    default_limits=["5000 per day", "500 per hour"]
)
limiter.init_app(app)  # Initialize limiter with the Flask app instance

def batched(items, page, limit):
    start = (page - 1) * limit
    if start >= len(items):
        return []
    last = min(start + limit, len(items))
    return items[start:last:1]

# Removed referrer validation
def validate_snap_storyclone_request():
    # You can log the request referrer for debugging purposes, if needed
    referrer = request.referrer
    print(f"Referrer: {referrer}")
    # Removed the check for "snap.storyclone.com"

# Snapchat API route to get user stories
@app.route("/get/<username>")
@cache.cached(timeout=500, query_string=True)
def slow(username):
    # Call the validation function (which now does nothing)
    validate_snap_storyclone_request()

    print(f"Getting info for username: {username}")

    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 400))

    page = 1 if page <= 0 else page
    limit = 400 if limit <= 0 else limit

    try:
        stories, user, spotlightHighlights, curatedHighlights = dl._web_fetch_story(username)
        return {
            "stories": batched(stories, page, limit),
            "user": user,
            "spotlightHighlights": batched(spotlightHighlights, page, limit),
            "curatedHighlights": batched(curatedHighlights, page, limit),
        }
    except UserNotFoundError:
        return {"message": f"Username <{username}> not found"}, 404

# Route to resolve URLs
@app.route("/resolve", methods=["GET"])
@cache.cached(timeout=500)
def resolve():
    # Call the validation function (which now does nothing)
    validate_snap_storyclone_request()

    url = request.args.get("url")
    if not url:
        abort(400, description="URL parameter is required")

    print(f"Resolving URL: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    }

    try:
        r = requests.head(url, headers=headers)
        r.raise_for_status()  # Raise an error for 4xx or 5xx responses
        
        location = r.headers.get("location")
        if location:
            return {"url": location}
        else:
            return {"message": "Location header not found"}, 400
    except requests.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        return {"message": str(e)}, 500
    except requests.RequestException as e:
        print(f"Error resolving URL: {e}")
        return {"message": str(e)}, 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5077))
    app.run(host="0.0.0.0", port=port)
