import requests
import json
from datetime import datetime, timezone
from bs4 import BeautifulSoup 
import time

# --- Discourse Scraper START (Robust Pagination for Topics & Posts) ---
BASE_DISCOURSE_URL = "https://discourse.onlinedegree.iitm.ac.in"
# Template for fetching pages of topic summaries, sorted by creation date (newest first)
CATEGORY_TOPICS_URL_TEMPLATE = f"{BASE_DISCOURSE_URL}/c/courses/tds-kb/34.json?order=created&ascending=false&page="
# Template for fetching pages of posts within a specific topic
TOPIC_POSTS_URL_TEMPLATE = f"{BASE_DISCOURSE_URL}/t/{{topic_id}}.json?page={{page_num_posts}}"

START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2025, 4, 14, 23, 59, 59, tzinfo=timezone.utc)
REQUEST_DELAY = 0.75 # Be a bit more gentle with nested loops

# Max pages to fetch for the TOPIC LIST (as per your observation, 0-7 covers it)
MAX_TOPIC_LIST_PAGES = 7 

def parse_discourse_date(date_str):
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None

def get_plain_text_bs(html_content):
    if not html_content: return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    for blockquote in soup.find_all('blockquote'): blockquote.decompose()
    return soup.get_text(separator='\n', strip=True)

def scrape_discourse_api():
    all_posts_data = []
    relevant_topic_summaries = []
    
    session = requests.Session()
    # !!! IMPORTANT: Paste your copied cookie string here !!!
    copied_cookie_string = "_ga_XDDWGSY1RE=GS1.1.1735319349.1.1.1735319575.0.0.0; _ga_MGSL57J8T3=GS1.1.1740652502.2.1.1740652547.0.0.0; _ga_8L0MCJC2XX=GS1.1.1744283296.1.0.1744283360.60.0.1907214739; _ga_FE0EJC6NK8=GS1.1.1744336701.3.0.1744336701.0.0.0; _ga_QHXRKWW9HH=GS1.3.1745680461.22.0.1745680461.0.0.0; _ga=GA1.1.735334308.1690304957; _ga_MXPR4XHYG9=GS1.1.1745820417.1.1.1745820431.0.0.0; _bypass_cache=true; _gcl_au=1.1.277248169.1749857140; _ga_5HTJMW67XK=GS2.1.s1749857144$o32$g0$t1749857154$j50$l0$h0; _ga_08NPRH5L4M=GS2.1.s1749857140$o75$g1$t1749857208$j60$l0$h0; _t=xe3znqZKCIanxfqge32wwW4rZ4dbhNk3rCW0QGDCfizPfkNT%2F3tsg%2FmIHHFFiy7d8tkjNDUVGARobcXuknKzL3algRg8dKWGQ93PVWFgpcUCwpjbnnASrbtJli%2BF3ReHG19nLnJcqcN0Kh4sunemCPaVpb9w8nkUPrhK7AlDF4OixqoD9wDh4UATOZVuf04ZOWRrr12cvzfZ2%2BSgE1D%2F4TwW1apcOwcm4p2%2FWwsWAQcGIoIZYjm6V6GDApT0FMM6ZaGWrETEfoLeem%2BF8uO4NinmFu91ajUHjvGP2baUWkEl0N4jqjBsgMWIBS4%3D--qUgbxHQl6wppj4nG--jC8mvrA34Z25umQMC%2F0Aug%3D%3D; _forum_session=EQE7ZODC4MZjjY0iRn%2BFlOfmQQQam41e65F4eXD9CLKqkZYHHJidWZM41VnLSUgZ9CvoAA04r4wTBAyoo%2FmJN5hYBCRwBvaf05bjoAiXl7osPCehtzLpm4dJGKLdNd6jjnQ%2FFV4hgdzU2BW6fXVNVxfL75%2Bytou6dwH7DavHk1kqs1RdNJ0Ui3R4jWbokki5ZAiFGa%2Bkaa0yMk%2FlBiPax5a23B%2Bivhq1gzcVVbVfYe%2BH4r0RFMuiBYlY1CbU4pAtciTGGuUnQb3SPWyHXmigK%2BTTHkBReHKFsCBllS6iXhnjIgm3XVPntscGuj6a2uIQv%2FFUJ2OM5LIy7pAahDr8qNCxjrE3iRyGwBQ0r0GclxA62bOGEQY66nBgaCV3mpdwN4lMzp6GREUseZuAooaRTL6vXJS62ZbsN1AV2Wc4ppgOQuBCLhOfZSMV6sHRh6b9BqAIA0QC5ydFguDWUvDrZPDpD7glQoGBVYhdPmWY3G%2BUqyMN%2BOYS%2F%2BOPQeu1XL3uPBqTpYq8KfaMGpvMO%2BXeDwLi13W3VHlx%2Fo9AbIVl%2BH5pesXEJafneGIL3i3XSucyvPQ9Q%2FEKn%2BCG5KSdX2zVslXezWd0oKA9zAzs7hxIWo4tUdX36iuHwf9WV0J5VcKwsOitn5kFOjuJhg%3D%3D--pRP6aDbFK1MPeter--V%2BAXxozu7LlFHjgSDahpjw%3D%3D"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 OPR/119.0.0.0',
        'Accept': 'application/json, text/plain, */*',
        'Cookie': copied_cookie_string,
        'X-Requested-With': 'XMLHttpRequest',
    }
    session.headers.update(headers)

    print("Fetching topic summaries from Discourse category (paginated, sorted)...")
    for page_num_topics in range(MAX_TOPIC_LIST_PAGES + 1): # 0 to MAX_TOPIC_LIST_PAGES inclusive
        category_url = f"{CATEGORY_TOPICS_URL_TEMPLATE}{page_num_topics}"
        print(f"Fetching topic list page: {category_url}")
        try:
            response = session.get(category_url)
            response.raise_for_status()
            category_page_data = response.json()
        except Exception as e:
            print(f"Error fetching topic list page {page_num_topics}: {e}")
            break 

        topics_on_page = category_page_data.get('topic_list', {}).get('topics', [])
        if not topics_on_page:
            print(f"No more topics found on topic list page {page_num_topics}.")
            break
        
        for topic_summary in topics_on_page:
            created_at_str = topic_summary.get('created_at')
            last_posted_at_str = topic_summary.get('last_posted_at')
            
            topic_created_dt = parse_discourse_date(created_at_str) if created_at_str else None
            topic_last_posted_dt = parse_discourse_date(last_posted_at_str) if last_posted_at_str else None

            if topic_created_dt and topic_last_posted_dt:
                if topic_created_dt <= END_DATE and topic_last_posted_dt >= START_DATE:
                    relevant_topic_summaries.append(topic_summary)
            elif topic_created_dt and topic_created_dt <= END_DATE and topic_created_dt >= START_DATE: # If last_posted_at is missing, check created_at
                 relevant_topic_summaries.append(topic_summary)


        print(f"Collected {len(topics_on_page)} topics from list page {page_num_topics}. Total relevant topics so far: {len(relevant_topic_summaries)}")
        # Optional: Check if created_at of last topic on page is older than START_DATE to break early
        # if topics_on_page and parse_discourse_date(topics_on_page[-1].get('created_at')) < START_DATE:
        #     print("Topics on current page are older than START_DATE, stopping topic list fetching.")
        #     break
        time.sleep(REQUEST_DELAY)

    print(f"\nFinished collecting topic summaries. Total relevant topics to process: {len(relevant_topic_summaries)}")
    print("Now fetching all posts for relevant topics and filtering by date...")

    unique_post_urls_added = set() # To avoid duplicate posts if a topic is somehow processed twice

    for i, topic_summary in enumerate(relevant_topic_summaries):
        topic_id = topic_summary.get('id')
        topic_title = topic_summary.get('title')
        topic_slug = topic_summary.get('slug')
        
        if not topic_id or not topic_slug: continue

        print(f"\nProcessing Topic {i+1}/{len(relevant_topic_summaries)}: '{topic_title}' (ID: {topic_id})")
        
        page_num_posts = 0
        while True: # Loop for paginating posts within this topic
            topic_posts_url = TOPIC_POSTS_URL_TEMPLATE.format(topic_id=topic_id, page_num_posts=page_num_posts)
            print(f"  Fetching posts page: {topic_posts_url}")
            try:
                time.sleep(REQUEST_DELAY)
                topic_response = session.get(topic_posts_url)
                if topic_response.status_code == 404:
                    print(f"  Reached end of posts (404) for topic {topic_id} at page {page_num_posts}.")
                    break 
                topic_response.raise_for_status()
                topic_page_data = topic_response.json()
            except Exception as e:
                print(f"  Error fetching posts for topic ID {topic_id}, page {page_num_posts}: {e}")
                break 

            posts_on_page = topic_page_data.get('post_stream', {}).get('posts', [])
            if not posts_on_page and page_num_posts > 0 : # If not the first page and no posts, assume end
                 print(f"  No more posts found for topic {topic_id} at page {page_num_posts}.")
                 break
            if not posts_on_page and page_num_posts == 0 and 'errors' in topic_page_data: # Handle cases where first page itself is an error
                 print(f"  Error on first page of posts for topic {topic_id}: {topic_page_data.get('errors')}")
                 break


            for post in posts_on_page:
                post_created_at_str = post.get('created_at')
                if not post_created_at_str: continue
                
                post_date = parse_discourse_date(post_created_at_str)
                if not post_date: continue

                if START_DATE <= post_date <= END_DATE:
                    post_number = post.get('post_number')
                    post_permalink = f"{BASE_DISCOURSE_URL}/t/{topic_slug}/{topic_id}/{post_number}"
                    
                    if post_permalink not in unique_post_urls_added:
                        post_content_html = post.get('cooked', '')
                        post_content_text = get_plain_text_bs(post_content_html)
                        username = post.get('username')
                        
                        all_posts_data.append({
                            "url": post_permalink, "topic_title": topic_title, "topic_id": topic_id,
                            "post_number": post_number, "author": username, "date_utc": post_date.isoformat(),
                            "content": post_content_text
                        })
                        unique_post_urls_added.add(post_permalink)
            
            if not posts_on_page and page_num_posts == 0 : # If first page had no posts (e.g. topic deleted or empty)
                print(f"  No posts found on the very first page for topic {topic_id}. Likely empty or issue.")
                break

            page_num_posts += 1
            # Safety break if a topic somehow has an absurd number of pages (e.g., > 50 for typical topics)
            if page_num_posts > 50 : # Adjust as needed, 50 pages * ~20 posts/page = ~1000 posts
                print(f"  Reached safety limit of 50 pages for posts in topic {topic_id}. Moving to next topic.")
                break
    
    output_filename = "discourse_posts_v2.json" # New filename
    print(f"\nFound {len(all_posts_data)} posts in the specified date range from Discourse after robust scraping.")
    with open(output_filename, "w", encoding='utf-8') as f:
        json.dump(all_posts_data, f, indent=2, ensure_ascii=False)
    print(f"Discourse posts saved to: {output_filename}")
    return output_filename
# --- Discourse Scraper END ---

if __name__ == "__main__":
    print("Running Robust Discourse Scraper...")
    scrape_discourse_api()
    print("Discourse scraping complete.")