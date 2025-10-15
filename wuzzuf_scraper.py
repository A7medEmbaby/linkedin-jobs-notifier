from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os, time, json
import logging

# Suppress logs
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('WDM').setLevel(logging.WARNING)

load_dotenv()
WUZZUF_URLS_UNFILTERED = os.getenv('WUZZUF_URLS_UNFILTERED', '')
WUZZUF_URLS_FILTERED = os.getenv('WUZZUF_URLS_FILTERED', '')

def load_keywords_from_env(env_var_name):
    """Loads keywords from a multi-line .env variable."""
    keywords_str = os.getenv(env_var_name, '')
    if not keywords_str:
        return []
    # Split by newline, strip whitespace, and filter out empty lines
    return [line.strip() for line in keywords_str.strip().splitlines() if line.strip()]

JOB_KEYWORDS = load_keywords_from_env('JOB_KEYWORDS')
EXCLUDED_KEYWORDS = load_keywords_from_env('EXCLUDED_KEYWORDS')


def parse_multiline_urls(url_string):
    """Parses a multi-line string of URLs, ignoring comments and empty lines."""
    parsed_urls = []
    if not url_string or not url_string.strip():
        return parsed_urls

    lines = url_string.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split('#', 1)
        url = parts[0].strip()
        note = parts[1].strip() if len(parts) > 1 else None
        
        if url:
            parsed_urls.append((url, note))
            
    return parsed_urls

def init_wuzzuf_driver():
    """Initialize Chrome driver for Wuzzuf"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    service = ChromeService(executable_path=ChromeDriverManager().install())
    service.log_path = os.devnull
    
    return webdriver.Chrome(options=options, service=service)

def check_keywords_in_text(text):
    """
    Check if text contains any JOB_KEYWORDS and none of the EXCLUDED_KEYWORDS.
    """
    if not text:
        return False

    text_lower = text.lower()
    
    has_required_keyword = any(keyword.lower() in text_lower for keyword in JOB_KEYWORDS)
    if not has_required_keyword:
        return False

    has_excluded_keyword = any(keyword.lower() in text_lower for keyword in EXCLUDED_KEYWORDS)
    if has_excluded_keyword:
        return False
            
    return True

def scrape_wuzzuf(url, check_keywords=False, show_details=False):
    """Scrape a single Wuzzuf URL."""
    driver = init_wuzzuf_driver()
    driver.set_page_load_timeout(60)
    all_roles = []

    try:
        driver.get(url)
        time.sleep(5)
        
        # Updated selector for Wuzzuf job cards to match the new site structure
        job_cards = driver.find_elements(By.CSS_SELECTOR, "div.css-pkv5jc")
        
        if show_details:
            print(f"  - Found {len(job_cards)} potential job cards.")

        for card in job_cards:
            try:
                # Updated selectors for title, company, etc. based on new HTML
                title_element = card.find_element(By.CSS_SELECTOR, "h2.css-193uk2c a")
                title = title_element.text.strip()
                link = title_element.get_attribute('href').split('?')[0]

                company_element = card.find_element(By.CSS_SELECTOR, "a.css-ipsyv7")
                company = company_element.text.strip()

            
                posted_time = "N/A" # Default value
                try:
                    # First, try the most common selector for the time
                    posted_time_element = card.find_element(By.CSS_SELECTOR, "div.css-1jldrig")
                    posted_time = posted_time_element.text.strip()
                except:
                    # If the first one fails, try the other selector as a fallback
                    try:
                        posted_time_element = card.find_element(By.CSS_SELECTOR, "div.css-eg55jf")
                        posted_time = posted_time_element.text.strip()
                    except:
                        # If both fail, it will remain "N/A"
                        pass
                                
                picture = None
                try:
                    img_element = card.find_element(By.CSS_SELECTOR, "a img.css-1in28d3")
                    picture = img_element.get_attribute('src')
                except:
                    picture = "https://wuzzuf.net/images/wuzzuf-logo-square.png"
                
                if check_keywords:
                    if not check_keywords_in_text(title):
                        if show_details:
                            print(f"    - SKIPPING (keyword filter): {title}")
                        continue
                
                all_roles.append((company, title, link, picture, posted_time))
                if show_details:
                    print(f"    - ADDED: {title} at {company}")

            except Exception as e:
                if show_details:
                    print(f"  - Could not parse a job card: {e}")
                continue
        
        if show_details:
             print(f"  - Successfully parsed {len(all_roles)} jobs.")
        else:
            print(f"  ✓ Total: {len(all_roles)} jobs found on this URL")

    except Exception as e:
        print(f"  ✗ Wuzzuf Error: An error occurred during scraping: {str(e)}")
    finally:
        driver.quit()

    return all_roles

def get_wuzzuf_roles(show_details=False):
    """Main function to get Wuzzuf roles from all configured URLs"""
    all_roles = []
    log_mode = "(Detailed Log Mode)" if show_details else ""
    print("\n" + "="*60)
    print(f"Wuzzuf Job Search {log_mode}")
    print("="*60)

    # Scrape unfiltered URLs
    unfiltered_urls = parse_multiline_urls(WUZZUF_URLS_UNFILTERED)
    if unfiltered_urls:
        for i, (url, note) in enumerate(unfiltered_urls, 1):
            print(f"\n📋 Unfiltered Search {i}/{len(unfiltered_urls)}: {note or 'General'}")
            roles = scrape_wuzzuf(url, check_keywords=False, show_details=show_details)
            all_roles.extend(roles)
            if i < len(unfiltered_urls):
                time.sleep(5)

    # Scrape filtered URLs
    filtered_urls = parse_multiline_urls(WUZZUF_URLS_FILTERED)
    if filtered_urls:
        for i, (url, note) in enumerate(filtered_urls, 1):
            print(f"\n🔍 Filtered Search {i}/{len(filtered_urls)}: {note or 'Marketing Keywords'}")
            roles = scrape_wuzzuf(url, check_keywords=True, show_details=show_details)
            all_roles.extend(roles)
            if i < len(filtered_urls):
                time.sleep(5)

    print("\n" + "="*60)
    print(f"✓ Search Complete: {len(all_roles)} total jobs found")
    print("="*60 + "\n")
    return all_roles

if __name__ == '__main__':
    show_details_arg = os.getenv('SHOW_DETAILED_LOGS', 'False').lower() == 'true'
    get_wuzzuf_roles(show_details=show_details_arg)

