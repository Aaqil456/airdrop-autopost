import os
import json
import time
import datetime
import requests
import base64

# === ENV ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
WP_URL = os.getenv("WP_API_URL")
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASS")
CATEGORY_ID = 1401
RESULTS_FILE = "results.json"

# === Load existing posted data
def load_existing_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f).get("data", [])
            except:
                return []
    return []

# === Save updated results
def save_results(data):
    final_result = {
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": data
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print("✅ All tweets processed and saved to results.json")

# === Fetch Tweets ===
def fetch_tweets_rapidapi(username, max_tweets=10):
    url = "https://twttrapi.p.rapidapi.com/user-tweets"
    querystring = {"username": username}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "twttrapi.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        if response.status_code != 200:
            return []

        data = response.json()
        tweets = []

        possible_paths = [
            data.get("user_result", {}).get("result", {}),
            data.get("data", {}).get("user_result", {}).get("result", {})
        ]

        instructions = []
        for path in possible_paths:
            timeline = path.get("timeline_response", {}).get("timeline", {})
            ins = timeline.get("instructions", [])
            if ins:
                instructions = ins
                break

        for instruction in instructions:
            if instruction.get("__typename") == "TimelineAddEntries":
                entries = instruction.get("entries", [])
                for entry in entries:
                    try:
                        tweet_result = entry.get("content", {}) \
                                            .get("content", {}) \
                                            .get("tweetResult", {}) \
                                            .get("result", {})
                        legacy = tweet_result.get("legacy", {})
                        text = legacy.get("full_text", legacy.get("text", ""))
                        tweet_id = tweet_result.get("rest_id", "")
                        screen_name = legacy.get("screen_name", username)

                        media_urls = []
                        media = legacy.get("extended_entities", {}).get("media", []) or \
                                legacy.get("entities", {}).get("media", [])
                        for m in media:
                            if m.get("type") == "photo":
                                media_url = m.get("media_url_https") or m.get("media_url")
                                if media_url:
                                    media_urls.append(media_url)

                        if not text or not tweet_id:
                            continue

                        tweets.append({
                            "id": tweet_id,
                            "text": text,
                            "images": media_urls,
                            "tweet_url": f"https://x.com/{screen_name}/status/{tweet_id}"
                        })

                        if len(tweets) >= max_tweets:
                            return tweets

                    except:
                        continue

        return tweets
    except:
        return []

# === Translate ===
def translate_text_gemini(text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    prompt = (
        f"Translate the following tweet into Malay (Bahasa Melayu) only. "
        f"make it sound like a 3rd person and instructional "
        f"for the word (I) translate it into (kami) in malay "
        f"Do not include English. Return just the translated version:\n\n\"{text}\""
    )
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ]
    }
    try:
        res = requests.post(url, headers=headers, json=body)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return None
    return None

# === WordPress Poster ===
def post_to_wordpress(entry):
    credentials = f"{WP_USER}:{WP_APP_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }

    images = entry.get("images", [])
    image_url = images[0] if images else None

    media_id = None
    uploaded_image_url = ""

    if image_url:
        try:
            img_resp = requests.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
            if img_resp.status_code == 200:
                file_name = image_url.split("/")[-1] or "image.jpg"
                media_headers = {
                    "Authorization": f"Basic {token}",
                    "Content-Disposition": f"attachment; filename={file_name}",
                    "Content-Type": "image/jpeg"
                }
                upload = requests.post(f"{WP_URL}/media", headers=media_headers, data=img_resp.content)
                if upload.status_code == 201:
                    media = upload.json()
                    media_id = media.get("id")
                    uploaded_image_url = media.get("source_url")
        except:
            pass

    content_html = f"<p>{entry['translated']}</p>"
    if uploaded_image_url:
        content_html = f"<img src='{uploaded_image_url}' alt='tweet image' /><br>" + content_html
    if entry.get("tweet_url"):
        content_html += f"<p>📌 Sumber: <a href='{entry['tweet_url']}'>{entry['tweet_url']}</a></p>"

    post_data = {
        "title": entry["translated"][:60],
        "content": content_html,
        "status": "private",
        "categories": [CATEGORY_ID]
    }
    if media_id:
        post_data["featured_media"] = media_id

    response = requests.post(f"{WP_URL}/posts", headers=headers, json=post_data)
    return response.status_code == 201

# === MAIN ===
if __name__ == "__main__":
    usernames = ["flb_xyz"]
    existing = load_existing_results()
    existing_ids = set(e["id"] for e in existing if "id" in e)
    result_data = existing.copy()

    for username in usernames:
        tweets = fetch_tweets_rapidapi(username)

        for tweet in tweets:
            if tweet["id"] in existing_ids:
                print(f"⏭️ Skipped (already posted): {tweet['tweet_url']}")
                continue

            translated = translate_text_gemini(tweet["text"])
            if translated:
                post_entry = {
                    "id": tweet["id"],
                    "original": tweet["text"],
                    "translated": translated,
                    "images": tweet["images"],
                    "tweet_url": tweet["tweet_url"]
                }

                success = post_to_wordpress(post_entry)
                if success:
                    print(f"✅ Posted: {tweet['tweet_url']}")
                    result_data.append(post_entry)
                    existing_ids.add(tweet["id"])
                else:
                    print(f"❌ Failed to post: {tweet['tweet_url']}")

    save_results(result_data)
    print("\n📦 All done.")
    print(json.dumps(result_data, indent=2, ensure_ascii=False))
