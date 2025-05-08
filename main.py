import os
import json
import time
import datetime
import requests

# === ENV ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

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

        # 🔍 Save raw JSON for inspection
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

                        # === FIXED MEDIA EXTRACTION ===
                        media = []
                        media_urls = []

                        if "extended_entities" in legacy and "media" in legacy["extended_entities"]:
                            media = legacy["extended_entities"]["media"]
                        elif "entities" in legacy and "media" in legacy["entities"]:
                            media = legacy["entities"]["media"]

                        for m in media:
                            if m.get("type") == "photo":  # Only include images
                                media_url = m.get("media_url_https") or m.get("media_url")
                                if media_url:
                                    media_urls.append(media_url)

                        if not text:
                            print("⚠️ No text found — skipped.")
                            continue

                        print(f"✅ Extracted tweet: {text[:60]}... with {len(media_urls)} images")

                        tweets.append({
                            "text": text,
                            "images": media_urls
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

# === STEP 2: Translate using Gemini 2.0 Flash (Only Malay Response) ===
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

# === MAIN EXECUTION ===
if __name__ == "__main__":
    usernames = ["flb_xyz"]
    result_data = []

    for username in usernames:
        tweets = fetch_tweets_rapidapi(username)

        for tweet in tweets:
            translated = translate_text_gemini(tweet["text"])
            if not translated.startswith("❌"):
                result_data.append({
                    "original": tweet["text"],
                    "translated": translated,
                    "images": tweet["images"]
                })

                print(f"\n✅ Translated:\n{translated}\n")

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
