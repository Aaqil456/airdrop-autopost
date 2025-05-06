import os
import json
import time
import datetime
import requests

# === ENV ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")

# === STEP 1: Fetch Tweets via Apify Actor ===
def fetch_tweets_apify(usernames, max_tweets=3):
    url = "https://api.apify.com/v2/acts/pratikdani~twitter-profile-scraper/run-sync-get-dataset-items"
    all_tweets = []

    for username in usernames:
        print(f"📥 Fetching tweets for @{username} from Apify...")
        payload = {
            "usernames": [username],
            "tweetsLimit": max_tweets
        }

        try:
            response = requests.post(
                f"{url}?token={APIFY_TOKEN}",
                json=payload,
                timeout=120
            )

            if response.status_code == 201:
                tweets = response.json()
                for tweet in tweets:
                    all_tweets.append({
                        "username": username,
                        "date": tweet.get("dateTime", ""),
                        "content": tweet.get("text", ""),
                        "url": tweet.get("url", "")
                    })
            else:
                print(f"❌ Failed to fetch from Apify for @{username} — {response.status_code}: {response.text}")
        except Exception as e:
            print(f"❌ Exception while fetching @{username}: {e}")

        time.sleep(2)  # To avoid hitting API too fast

    return all_tweets


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


# === MAIN ===
if __name__ == "__main__":
    usernames = ["codeglitch", "flb_xyz"]
    tweets = fetch_tweets_apify(usernames)

    result_data = []
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

    # Save to JSON
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": result_data
        }, f, ensure_ascii=False, indent=2)

    print("✅ All tweets processed and saved to results.json")
