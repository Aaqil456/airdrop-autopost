import json
import datetime
import os
import requests
import snscrape.modules.twitter as sntwitter

# STEP 1: Scrape Tweets
def scrape_tweets(usernames, max_tweets=3):
    all_tweets = []
    for username in usernames:
        tweets = sntwitter.TwitterUserScraper(username).get_items()
        for i, tweet in enumerate(tweets):
            if i >= max_tweets:
                break
            all_tweets.append({
                "username": username,
                "date": tweet.date.strftime("%Y-%m-%d %H:%M:%S"),
                "content": tweet.content,
                "url": tweet.url
            })
    return all_tweets

# STEP 2: Translate with Gemini 2.0 Flash (gemini-1.5-flash)
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

# STEP 3: Post to WordPress
def post_to_wordpress(title, content):
    wp_url = os.getenv("WP_API_URL")
    wp_user = os.getenv("WP_USER")
    wp_pass = os.getenv("WP_APP_PASS")

    payload = {
        "title": title,
        "content": content,
        "status": "publish"
    }

    res = requests.post(wp_url, auth=(wp_user, wp_pass), json=payload)
    if res.status_code == 201:
        print("✅ Posted:", title)
    else:
        print("❌ Failed to post:", res.text)

# MAIN
if __name__ == "__main__":
    usernames = ["codeglitch", "flb_xyz"]
    tweets = scrape_tweets(usernames)

    for tweet in tweets:
        translated = translate_text_gemini(tweet["content"])
        if not translated.startswith("❌"):
            title = f"Tweet oleh @{tweet['username']} pada {tweet['date']}"
            content = f"<p>{translated}</p><p><a href='{tweet['url']}'>Lihat tweet asal</a></p>"
            post_to_wordpress(title, content)
