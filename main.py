import json
import datetime
import os
import requests
from bs4 import BeautifulSoup
import time

# STEP 1: Scrape Tweets from Nitter
import requests
from bs4 import BeautifulSoup

# ✅ Senarai semua mirror fallback (boleh tambah lagi kalau perlu)
NITTER_MIRRORS = [
    "https://nitter.cz",
    "https://nitter.net",
    "https://nitter.kavin.rocks",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net"
]

def scrape_tweets(usernames, max_tweets=3):
    all_tweets = []

    for username in usernames:
        success = False

        for mirror in NITTER_MIRRORS:
            try:
                url = f"{mirror}/{username}"
                print(f"\n🌐 Fetching: {url}")
                res = requests.get(url, timeout=10)
                print(f"🔄 Status code: {res.status_code}")

                if res.status_code != 200:
                    print(f"❌ Failed to fetch from {url} — Status {res.status_code}")
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                timeline_items = soup.select("div.timeline-item")

                print(f"🧪 Found {len(timeline_items)} tweet blocks from {mirror} for @{username}")

                if not timeline_items:
                    continue

                for item in timeline_items[:max_tweets]:
                    content_elem = item.select_one("div.tweet-content.media-body")
                    link_elem = item.select_one("a.tweet-link")
                    image_elem = item.select_one("div.attachment.image img")

                    if not content_elem or not link_elem:
                        continue

                    tweet_text = content_elem.get_text(strip=True)
                    tweet_url = mirror + link_elem["href"]
                    tweet_image = mirror + image_elem["src"] if image_elem else None

                    all_tweets.append({
                        "username": username,
                        "content": tweet_text,
                        "url": tweet_url,
                        "image": tweet_image
                    })

                success = True
                break  # ✅ Berjaya, tak perlu cuba mirror lain

            except Exception as e:
                print(f"❌ Exception from {mirror} for @{username}: {e}")
                continue

        if not success:
            print(f"🚫 Failed to scrape any tweets for @{username} from all mirrors.")

    return all_tweets




# STEP 2: Translate with Gemini 2.0 Flash
def translate_text_gemini(text):
    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

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

    res = requests.post(url, headers=headers, json=body)
    if res.status_code == 200:
        try:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"❌ Failed to parse Gemini response: {str(e)}"
    return f"❌ Gemini API Error: {res.status_code} — {res.text}"

# STEP 3: (Optional) Post to WordPress
# def post_to_wordpress(title, content):
#     wp_url = os.getenv("WP_API_URL")
#     wp_user = os.getenv("WP_USER")
#     wp_pass = os.getenv("WP_APP_PASS")
# 
#     payload = {
#         "title": title,
#         "content": content,
#         "status": "publish"
#     }
# 
#     res = requests.post(wp_url, auth=(wp_user, wp_pass), json=payload)
#     if res.status_code == 201:
#         print("✅ Posted:", title)
#     else:
#         print("❌ Failed to post:", res.text)

# MAIN
if __name__ == "__main__":
    usernames = ["codeglitch", "flb_xyz"]
    tweets = scrape_tweets(usernames)

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

            # WordPress posting is currently disabled
            # title = f"Tweet oleh @{tweet['username']} pada {tweet['date']}"
            # content = f"<p>{translated}</p><p><a href='{tweet['url']}'>Lihat tweet asal</a></p>"
            # post_to_wordpress(title, content)

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": result_data
        }, f, ensure_ascii=False, indent=2)

    print("✅ All tweets processed and saved to results.json")
