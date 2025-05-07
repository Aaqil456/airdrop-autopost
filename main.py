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
        tweets = []

        instructions = data.get("user_result", {}).get("result", {}) \
                           .get("timeline_response", {}).get("timeline", {}) \
                           .get("instructions", [])

        print(f"🧪 Found {len(instructions)} instruction blocks")

        for instruction in instructions:
            if instruction.get("__typename") == "TimelineAddEntries":
                entries = instruction.get("entries", [])
                print(f"📦 Processing {len(entries)} entries from timeline")

                for entry in entries:
                    try:
                        content = entry.get("content", {})
                        item_content = content.get("itemContent", {})
                        tweet_result = item_content.get("tweet_results", {}).get("result", {})

                        legacy = tweet_result.get("legacy", {})
                        text = legacy.get("full_text", legacy.get("text", ""))

                        if not text:
                            print("⚠️ No text found — skipped.")
                            continue

                        print(f"✅ Extracted tweet: {text[:60]}...")

                        tweets.append(text)

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
    prompt = f"Translate the following tweet into Malay (Bahasa Melayu) with a casual, local tone. Keep all crypto terms (like wallet, futures, mining) in English:\n\n\"{text}\""

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
    usernames = ["flb_xyz","elonmusk"]  # Tambah username lain jika perlu
    result_data = []

    for username in usernames:
        tweets = fetch_tweets_rapidapi(username)

        for text in tweets:
            translated = translate_text_gemini(text)
            if not translated.startswith("❌"):
                result_data.append({
                    "original": text,
                    "translated": translated
                })

                print(f"\n✅ Translated:\n{translated}\n")

    # Simpan ke JSON (simple version)
    final_result = {
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": result_data
    }

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)

    print("✅ All tweets processed and saved to results.json")
    print("\n📦 DEBUG OUTPUT (results.json):")
    print(json.dumps(final_result, ensure_ascii=False, indent=2))
