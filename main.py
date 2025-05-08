import os
import json
import time
import datetime
import requests
import base64

# === ENV ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
WP_URL = os.getenv("WP_API_URL")  # example: https://yourdomain.com/wp-json/wp/v2
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASS")
PANDUAN_CATEGORY_ID = 1395

# === STEP 1: Fetch Tweets via RapidAPI ===
def fetch_tweets_rapidapi(username, max_tweets=3):
    url = "https://twttrapi.p.rapidapi.com/user-tweets"
    querystring = {"username": username}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "twttrapi.p.rapidapi.com"
    }

    print(f"📥 Fetching tweets from: @{username}")

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        if response.status_code != 200:
            print(f"❌ RapidAPI Error {response.status_code}: {response.text}")
            return []

        data = response.json()

        with open(f"debug_{username}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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

        print(f"🧪 Found {len(instructions)} instruction blocks")

        for instruction in instructions:
            if instruction.get("__typename") == "TimelineAddEntries":
                entries = instruction.get("entries", [])
                print(f"📦 Processing {len(entries)} entries from timeline")

                for entry in entries:
                    try:
                        tweet_result = entry.get("content", {}) \
                                            .get("content", {}) \
                                            .get("tweetResult", {}) \
                                            .get("result", {})
                        legacy = tweet_result.get("legacy", {})
                        text = legacy.get("full_text", legacy.get("text", ""))
                        tweet_id = tweet_result.get("rest_id", "")
                        username = legacy.get("screen_name", username)

                        # === Extract media ===
                        media = []
                        media_urls = []

                        if "extended_entities" in legacy and "media" in legacy["extended_entities"]:
                            media = legacy["extended_entities"]["media"]
                        elif "entities" in legacy and "media" in legacy["entities"]:
                            media = legacy["entities"]["media"]

                        for m in media:
                            if m.get("type") == "photo":
                                media_url = m.get("media_url_https") or m.get("media_url")
                                if media_url:
                                    media_urls.append(media_url)

                        if not text:
                            print("⚠️ No text found — skipped.")
                            continue

                        print(f"✅ Extracted tweet: {text[:60]}... with {len(media_urls)} images")

                        tweets.append({
                            "text": text,
                            "images": media_urls,
                            "tweet_url": f"https://x.com/{username}/status/{tweet_id}"
                        })

                        if len(tweets) >= max_tweets:
                            return tweets

                    except Exception as parse_error:
                        print(f"⚠️ Skipping entry due to error: {parse_error}")
                        continue

        return tweets

    except Exception as e:
        print(f"❌ Exception while fetching @{username}: {e}")
        return []

# === STEP 2: Translate using Gemini 2.0 Flash ===
def translate_text_gemini(text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    prompt = (
        f"Translate the following tweet into Malay (Bahasa Melayu) only. "
        f"Do not include English. Return just the translated version, "
        f"as a single sentence or paragraph only:\n\n\"{text}\""
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
        else:
            return f"❌ Gemini API Error: {res.status_code} — {res.text}"
    except Exception as e:
        return f"❌ Gemini Exception: {e}"

# === STEP 3: Push to WordPress ===
def post_to_wordpress(entry):
    credentials = f"{WP_USER}:{WP_APP_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }

    image_url = entry.get("images", [None])[0]
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
        except Exception as e:
            print(f"[Image Upload Error] {e}")

    content_html = f"<p>{entry['translated']}</p>"
    if uploaded_image_url:
        content_html = f"<img src='{uploaded_image_url}' alt='tweet image' /><br>" + content_html
    if entry.get("tweet_url"):
        content_html += f"<p>📌 Sumber: <a href='{entry['tweet_url']}'>{entry['tweet_url']}</a></p>"

    post_data = {
        "title": entry["translated"][:60],
        "content": content_html,
        "status": "private",
        "categories": [PANDUAN_CATEGORY_ID]
    }

    if media_id:
        post_data["featured_media"] = media_id

    response = requests.post(f"{WP_URL}/posts", headers=headers, json=post_data)
    print(f"📤 WordPress Post Status: {response.status_code}")
    return response.status_code == 201

# === MAIN EXECUTION ===
if __name__ == "__main__":
    usernames = ["flb_xyz"]
    result_data = []

    for username in usernames:
        tweets = fetch_tweets_rapidapi(username)

        for tweet in tweets:
            translated = translate_text_gemini(tweet["text"])
            if not translated.startswith("❌"):
                post_entry = {
                    "original": tweet["text"],
                    "translated": translated,
                    "images": tweet["images"],
                    "tweet_url": tweet["tweet_url"]
                }
                result_data.append(post_entry)

                print(f"\n✅ Translated:\n{translated}\n")

                # === Push to WordPress ===
                success = post_to_wordpress(post_entry)
                if success:
                    print("✅ Draft posted to WordPress.\n")
                else:
                    print("❌ Failed to post to WordPress.\n")

    # Simpan ke JSON
    final_result = {
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": result_data
    }

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)

    print("✅ All tweets processed and saved to results.json")
    print("\n📦 DEBUG OUTPUT (results.json):")
    print(json.dumps(final_result, ensure_ascii=False, indent=2))
