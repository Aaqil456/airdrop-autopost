import os
import json
import time
import datetime
import requests

# === ENV ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")  # Simpan dalam .env atau GitHub Secrets

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

        if response.status_code == 200:
            data = response.json()
            tweets_raw = data.get("data", [])[:max_tweets]

            tweets = []
            for tweet in tweets_raw:
                tweets.append({
                    "username": username,
                    "date": tweet.get("created_at", ""),
                    "content": tweet.get("full_text", tweet.get("text", "")),
                    "url": f"https://x.com/{username}/status/{tweet.get('id_str', '')}"
                })
            return tweets
        else:
            print(f"❌ RapidAPI Error: {response.status_code} — {response.text}")
            return []
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
    usernames = [
        "flb_xyz"
        # Tambah username lain jika perlu
    ]

    result_data = []

    for username in usernames:
        tweets = fetch_tweets_rapidapi(username)

        for tweet in tweets:
            translated = translate_text_gemini(tweet["content"])
            if not translated.startswith("❌"):
                result_data.append({
                    "username": tweet["username"],
                    "date": tweet["date"],
                    "original": tweet["content"],
                    "translated": translated,
                    "tweet_url": tweet["url"]
                })

                print(f"\n✅ @{tweet['username']}:\n{translated}\n")

    # Simpan ke results.json
    final_result = {
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": result_data
    }

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)

    print("✅ All tweets processed and saved to results.json")

    # === DEBUG PRINT ===
    print("\n📦 DEBUG OUTPUT (results.json):")
    print(json.dumps(final_result, ensure_ascii=False, indent=2))
