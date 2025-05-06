import json
import datetime
import os
import requests
from bs4 import BeautifulSoup

# STEP 1: Scrape Tweets from Nitter
def scrape_tweets(usernames, max_tweets=3):
    all_tweets = []
    for username in usernames:
        try:
            url = f"https://nitter.net/{username}"
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                print(f"❌ Failed to fetch @{username} from Nitter — Status code: {res.status_code}")
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            tweets = soup.select("div.timeline-item")[:max_tweets]

            for tweet in tweets:
                content_elem = tweet.select_one(".tweet-content")
                date_elem = tweet.select_one("span.tweet-date a")
                if content_elem and date_elem:
                    content = content_elem.text.strip()
                    date = date_elem["title"]
                    link = "https://nitter.net" + date_elem["href"]

                    all_tweets.append({
                        "username": username,
                        "date": date,
                        "content": content,
                        "url": link
                    })
        except Exception as e:
            print(f"❌ Error scraping @{username} — {str(e)}")
            continue

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
