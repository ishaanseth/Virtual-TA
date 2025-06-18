import json
from bs4 import BeautifulSoup 
import time

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

# --- Course Content Scraper START ---
COURSE_BASE_URL = "https://tds.s-anand.net/" 
INITIAL_COURSE_URL = f"{COURSE_BASE_URL}#/2025-01/" # Entry point, typically loads #/README or similar

# get_content_from_page_selenium function remains the same as your last working version.
# Ensure the blockquote fix is in your version:
# elif element.name == 'blockquote':
#     quote_text = element.get_text(separator='\n', strip=True)
#     if quote_text:
#         formatted_quote = f"> {quote_text.replace('\n', '\n> ')}"
#         current_section_content_parts.append(formatted_quote)
def get_content_from_page_selenium(driver, page_url):
    page_course_data = []
    print(f"Selenium navigating to: {page_url}")
    try:
        driver.get(page_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article.markdown-section#main, section.content, aside.sidebar .sidebar-nav a"))
        )
        time.sleep(2) 
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
    except TimeoutException:
        print(f"Timeout waiting for content to load on {page_url}")
        return []
    except Exception as e:
        print(f"Error during Selenium navigation or getting page source for {page_url}: {e}")
        return []

    content_article = soup.find('article', class_='markdown-section', id='main')
    if not content_article:
        content_section = soup.find('section', class_='content')
        if content_section: content_article = content_section
        else:
            content_article = soup.find('main')
            if not content_article:
                if soup.body: content_article = soup.body 
                else:
                    print(f"Selenium: Could not find specific content container for URL: {page_url}")
                    return []
    
    page_h1_tag = content_article.find('h1')
    current_section_title = page_h1_tag.get_text(separator=' ', strip=True) if page_h1_tag else \
                           (soup.title.string if soup.title else page_url.split('#')[-1] or "Page Content")
    current_section_content_parts = []

    for element in content_article.find_all(True, recursive=True): 
        if not hasattr(element, 'name'): continue
        if any(parent.get('class') and 'sidebar' in parent.get('class') for parent in element.parents): continue
        
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
            new_title = element.get_text(separator=' ', strip=True)
            if current_section_content_parts or (element.name != 'h1' and new_title != current_section_title):
                section_text = "\n".join(part for part in current_section_content_parts if part).strip()
                if section_text: page_course_data.append({"title": current_section_title, "content": section_text, "source_url": page_url})
                current_section_content_parts = []
                current_section_title = new_title
            elif element.name == 'h1' and not current_section_content_parts : current_section_title = new_title
        elif element.name == 'p':
            text = element.get_text(separator=' ', strip=True)
            if text and not (element.find('img') and not element.text.strip()): current_section_content_parts.append(text)
        elif element.name == 'ul' or element.name == 'ol':
            list_items = [li.get_text(separator=' ', strip=True) for li in element.find_all('li', recursive=False) if li.get_text(strip=True)]
            if list_items: current_section_content_parts.append("\n".join(f"- {item}" for item in list_items))
        elif element.name == 'pre' or (element.name == 'div' and element.has_attr('class') and 'sourceCode' in element['class']):
            code_text = element.get_text()
            if code_text.strip(): current_section_content_parts.append(f"```\n{code_text.strip()}\n```")
        elif element.name == 'details':
            summary_tag = element.find('summary', recursive=False)
            if summary_tag: current_section_content_parts.append(f"Details Summary: {summary_tag.get_text(separator=' ', strip=True)}")
            for detail_child in element.find_all(['p', 'ul', 'ol', 'div', 'pre'], recursive=False):
                if summary_tag and detail_child == summary_tag: continue
                if detail_child.name == 'p': current_section_content_parts.append(detail_child.get_text(separator=' ', strip=True))
                elif detail_child.name in ['ul', 'ol']:
                    d_list_items = [li.get_text(separator=' ', strip=True) for li in detail_child.find_all('li', recursive=False) if li.get_text(strip=True)]
                    if d_list_items: current_section_content_parts.append("\n".join(f"  - {item}" for item in d_list_items))
                elif detail_child.name == 'pre' or (detail_child.name == 'div' and detail_child.has_attr('class') and 'sourceCode' in detail_child['class']):
                    d_code_text = detail_child.get_text()
                    if d_code_text.strip(): current_section_content_parts.append(f"```\n{d_code_text.strip()}\n```")
        elif element.name == 'blockquote':
            quote_text = element.get_text(separator='\n', strip=True)
            if quote_text:
                formatted_quote = f"> {quote_text.replace('\n', '\n> ')}" # Corrected line
                current_section_content_parts.append(formatted_quote)
        elif element.name == 'table':
            table_representation = ["Table:"]
            for row_idx, row in enumerate(element.find_all('tr')):
                cols = [col.get_text(strip=True) for col in row.find_all(['th', 'td'])]
                if row_idx == 0 and element.find('thead'): 
                    table_representation.append(" | ".join(cols))
                    table_representation.append(" | ".join(["---"] * len(cols)))
                elif cols: table_representation.append(" | ".join(cols))
            if len(table_representation) > 1 : current_section_content_parts.append("\n".join(table_representation))

    if current_section_content_parts:
        section_text = "\n".join(part for part in current_section_content_parts if part).strip()
        if section_text: page_course_data.append({"title": current_section_title, "content": section_text, "source_url": page_url})
    if not page_course_data and content_article:
        all_text = content_article.get_text(separator='\n', strip=True)
        sidebar_check = content_article.find('aside', class_='sidebar')
        if sidebar_check: all_text = all_text.replace(sidebar_check.get_text(separator='\n', strip=True), '').strip()
        if all_text:
            title_tag_text = soup.title.string if soup.title else None
            final_title = title_tag_text or page_url.split('#')[-1] or "Page Content"
            page_course_data.append({"title": final_title, "content": all_text, "source_url": page_url})
    return page_course_data


def scrape_course_content_static():
    all_site_course_data = []
    
    print("Initializing Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Error initializing Selenium WebDriver: {e}")
        with open("course_content.json", "w", encoding='utf-8') as f: json.dump({"error": f"Selenium init error: {str(e)}", "data": []}, f, indent=2, ensure_ascii=False)
        return "course_content.json"

    initial_page_content = get_content_from_page_selenium(driver, INITIAL_COURSE_URL)
    if initial_page_content:
        all_site_course_data.extend(initial_page_content)
    else:
        print(f"No content extracted via Selenium from initial page: {INITIAL_COURSE_URL}")

    page_urls_to_scrape = set()
    try:
        initial_page_rendered_source = driver.page_source
        initial_soup_rendered = BeautifulSoup(initial_page_rendered_source, 'html.parser')
        sidebar_nav = initial_soup_rendered.select_one('aside.sidebar div.sidebar-nav')

        if sidebar_nav:
            links = sidebar_nav.find_all('a', href=True) 
            for link_tag in links:
                if hasattr(link_tag, 'get'): 
                    href_value = link_tag.get('href')
                    if isinstance(href_value, str) and href_value.startswith('#/'): 
                        # href_value is like "#/../some-page" or "#/some-page"
                        
                        # Normalize the hash part first
                        current_hash_path = href_value[1:] # Remove the leading '#' -> "/../some-page" or "/some-page"
                        
                        if current_hash_path.startswith('/../'):
                            # Change '/../foo' to '/foo'
                            normalized_hash_path = '/' + current_hash_path[len('/../'):]
                        else:
                            normalized_hash_path = current_hash_path
                        
                        # Reconstruct the full URL
                        # COURSE_BASE_URL ends with a slash, normalized_hash_path starts with a slash (after #)
                        # We want: https://tds.s-anand.net/ + # + /foo
                        # So, COURSE_BASE_URL + '#' + normalized_hash_path
                        full_url = COURSE_BASE_URL + '#' + normalized_hash_path
                        
                        page_urls_to_scrape.add(full_url)
            
            # Ensure the initial URL (after potential Docsify default page resolution) is also considered scraped
            # If INITIAL_COURSE_URL led to (e.g.) #/README, and #/README is in sidebar, it's fine.
            # If INITIAL_COURSE_URL itself is what we want, it's already processed.
            # Remove INITIAL_COURSE_URL from the set if it was added, as it's already processed.
            if INITIAL_COURSE_URL in page_urls_to_scrape:
                page_urls_to_scrape.remove(INITIAL_COURSE_URL)

        else:
            print("Could not find sidebar navigation ('aside.sidebar div.sidebar-nav') on the initial page using Selenium.")
    except Exception as e:
        print(f"Error extracting sidebar links after Selenium load: {e}")

    print(f"Found {len(page_urls_to_scrape)} unique page links to scrape from the sidebar (using Selenium).")
    
    for i, page_url in enumerate(list(page_urls_to_scrape)): # page_url is already normalized here
        print(f"Processing linked page ({i+1}/{len(page_urls_to_scrape)}): {page_url}")
        page_content = get_content_from_page_selenium(driver, page_url) # Pass normalized URL
        if page_content:
            all_site_course_data.extend(page_content)
        else:
            print(f"No content extracted from linked page (Selenium): {page_url}")
    
    driver.quit()

    output_filename = "course_content.json"
    if all_site_course_data:
        print(f"\nScraped a total of {len(all_site_course_data)} sections from the entire course site using Selenium.")
    else:
        print("\nNo sections were scraped from the course site using Selenium.")
            
    with open(output_filename, "w", encoding='utf-8') as f:
        json.dump(all_site_course_data, f, indent=2, ensure_ascii=False)
    print(f"Course content saved to: {output_filename}")
    return output_filename
# --- Course Content Scraper END ---

if __name__ == "__main__":
    print("Running Course Content Scraper (Selenium version)...")
    scrape_course_content_static()
    print("Course content scraping complete.")