from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os, time, json, re
import logging

# Suppress Selenium and WebDriver Manager logs
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('WDM').setLevel(logging.WARNING)

load_dotenv()
LINKEDIN_URLS_UNFILTERED = os.getenv('LINKEDIN_URLS_UNFILTERED', '')
LINKEDIN_URLS_FILTERED = os.getenv('LINKEDIN_URLS_FILTERED', '')
SELENIUM_USER_DATA_DIR = os.getenv('SELENIUM_USER_DATA_DIR')

# Keywords for desired job roles
JOB_KEYWORDS = [
    ".net", "dotnet", "dot net", ". net",
    ".net core", "dotnet core", "dot net core",
    ".net framework", "dotnet framework",
    ".net 6", ".net 7", ".net 8", ".net 9",
    "dotnet6", "dotnet7", "dotnet8",
    "asp.net", "asp dotnet", "aspdotnet", "asp net",
    "asp.net core", "asp.net core", "aspnetcore",
    "asp.net mvc", "asp.net web api",
    "c#", "c sharp", "csharp", "c #",
    "entity framework", "ef core",
    "blazor", "razor", "wcf", "wpf", "xamarin", "maui",
    "visual studio", "nuget"
]

# Keywords to exclude irrelevant jobs
EXCLUDED_KEYWORDS = [
]

def parse_multiline_urls(url_string):
    """Parses a multi-line string of URLs, ignoring comments and empty lines."""
    parsed_urls = []
    if not url_string or not url_string.strip():
        return parsed_urls

    # Split the string into individual lines
    lines = url_string.strip().splitlines()
    for line in lines:
        line = line.strip()
        # Ignore empty lines or lines that are only comments
        if not line or line.startswith('#'):
            continue
        
        # Split the line into URL and comment at the '#'
        parts = line.split('#', 1)
        url = parts[0].strip()
        note = parts[1].strip() if len(parts) > 1 else None
        
        if url:
            parsed_urls.append((url, note))
            
    return parsed_urls

def init_driver():
    """Initialize Chrome driver with options"""
    options = Options()
    options.add_argument(f"user-data-dir={SELENIUM_USER_DATA_DIR}")
    options.add_argument("--headless=new") 
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")  # Suppress console logs
    options.add_experimental_option('excludeSwitches', ['enable-logging'])  # Disable DevTools logs
    
    service = ChromeService(executable_path=ChromeDriverManager().install())
    service.log_path = os.devnull  # Suppress service logs
    
    return webdriver.Chrome(options=options, service=service)

def check_keywords_in_text(text, return_details=False):
    """
    Check if text contains any JOB_KEYWORDS and none of the EXCLUDED_KEYWORDS.
    """
    if not text:
        return (False, [], {}) if return_details else False

    text_lower = text.lower()
    matched_keywords = []
    
    # Step 1: Check for required keywords
    has_required_keyword = False
    for keyword in JOB_KEYWORDS:
        if keyword.lower() in text_lower:
            has_required_keyword = True
            matched_keywords.append(keyword)

    if not has_required_keyword:
        return (False, [], {}) if return_details else False

    # Step 2: Check for excluded keywords
    for keyword in EXCLUDED_KEYWORDS:
        if keyword.lower() in text_lower:
            # If an excluded word is found, reject the job
            return (False, [], {}) if return_details else False
            
    # If we passed both checks, the job is a good match
    if return_details:
        # For simplicity, we won't return search locations in this new logic
        return True, matched_keywords, {}
        
    return True

def get_job_description(driver, job_url, job_title, company_name, show_details=False):
    """Get job description from job details page"""
    try:
        if show_details:
            print(f"    - Checking description for: {job_title} at {company_name}")
        
        driver.get(job_url)
        time.sleep(4)
        
        # Try to click "Show more" button
        try:
            show_more_selectors = [
                "button.show-more-less-html__button--more",
                "button.show-more-less-html__button",
                ".jobs-description__footer-button"
            ]
            
            for selector in show_more_selectors:
                try:
                    show_more_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    driver.execute_script("arguments[0].click();", show_more_btn)
                    time.sleep(1)
                    if show_details:
                        print("      - Clicked 'Show more' button.")
                    break
                except:
                    continue
        except Exception as e:
            if show_details:
                 print(f"      - Note: Could not click 'Show more' button ({e}).")
            pass
        
        # Get job description
        description_text = ""
        description_selectors = [
            ".jobs-description__content",
            ".jobs-description-content__text",
            ".jobs-box__html-content",
            ".description__text",
            ".jobs-description",
            "div.jobs-box__html-content",
            "article.jobs-description__container"
        ]
        
        for selector in description_selectors:
            try:
                description_element = driver.find_element(By.CSS_SELECTOR, selector)
                description_text = description_element.text
                if description_text and len(description_text) > 50:
                    break
            except:
                continue
        
        if not description_text:
            if show_details:
                print("      - ✗ Description not found.")
            return ""
        
        # Check keywords
        found, matched_keywords, _ = check_keywords_in_text(
            f"{job_title} {description_text}", 
            return_details=True
        )
        
        if show_details:
            if found:
                print(f"      - ✓ Keywords matched: {', '.join(matched_keywords[:5])}")
            else:
                print("      - ✗ No relevant keywords matched in description.")

        return description_text
        
    except Exception as e:
        if show_details:
            print(f"      - ✗ Error getting description: {e}")
        return ""

def parse_job_listings(driver, positions, check_keywords=False, show_details=False):
    """Parse job listings and return roles"""
    roles = []
    skipped_no_keywords = 0
    promoted_included = 0
    
    for i, position in enumerate(positions):
        if show_details:
            print(f"\n  --- Processing Card {i+1}/{len(positions)} ---")
        
        try:
            # Scroll each job card into view before parsing to trigger lazy loading of its content
            driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", position)
            time.sleep(0.5)

            # Check if promoted (but don't skip - just track for statistics)
            promoted = False
            try:
                footer_items = position.find_elements(By.CSS_SELECTOR, ".job-card-container__footer-item")
                for item in footer_items:
                    if "promoted" in item.text.lower():
                        promoted = True
                        promoted_included += 1
                        if show_details:
                            print("    - Status: Promoted")
                        break
            except:
                pass

            # Get company name
            company = None
            company_selectors = [
                ".artdeco-entity-lockup__subtitle",
                ".job-card-container__primary-description"
            ]
            
            for comp_sel in company_selectors:
                try:
                    company = position.find_element(By.CSS_SELECTOR, comp_sel).text.strip()
                    if company:
                        break
                except:
                    continue
            
            if not company:
                if show_details:
                    print("    - ✗ Company name not found. Skipping card.")
                continue
            if show_details:
                print(f"    - Company: {company}")

            # Get job link
            link = None
            link_selectors = [
                "a.job-card-container__link",
                "a[href*='/jobs/view/']"
            ]
            
            for link_sel in link_selectors:
                try:
                    link_element = position.find_element(By.CSS_SELECTOR, link_sel)
                    link = link_element.get_attribute('href').split('?')[0]
                    if link:
                        break
                except:
                    continue
            
            if not link:
                if show_details:
                    print("    - ✗ Job link not found. Skipping card.")
                continue
            if show_details:
                print(f"    - Link: {link}")

            # Get job title
            title = None
            title_selectors = [
                "a.job-card-container__link strong",
                ".job-card-container__link",
                ".artdeco-entity-lockup__title a"
            ]
            
            for title_sel in title_selectors:
                try:
                    title_element = position.find_element(By.CSS_SELECTOR, title_sel)
                    title = title_element.text.strip()
                    if title:
                        break
                except:
                    continue
            
            if not title:
                if show_details:
                    print("    - ✗ Job title not found. Skipping card.")
                continue
            if show_details:
                print(f"    - Title: {title}")

            # Get posted time
            posted_time = "N/A"
            try:
                time_element = position.find_element(By.CSS_SELECTOR, "time")
                posted_time = time_element.text.strip()
            except:
                pass
            if show_details:
                print(f"    - Posted: {posted_time}")


            # Check keywords if needed
            if check_keywords:
                description = get_job_description(driver, link, title, company, show_details)
                
                title_and_description = f"{title} {description}"
                found = check_keywords_in_text(title_and_description)
                
                if not found:
                    skipped_no_keywords += 1
                    if show_details:
                        print("    - Result: SKIPPED (keyword filter)")
                    continue

            # Get company picture
            picture = None
            try:
                img_element = position.find_element(By.CSS_SELECTOR, "img")
                picture = img_element.get_attribute('src')
            except:
                picture = "https://via.placeholder.com/100"

            roles.append((company, title, link, picture, posted_time))
            if show_details:
                print("    - Result: ADDED to list")
            
        except Exception as e:
            if show_details:
                print(f"    - ✗ UNEXPECTED ERROR parsing this card: {e}")
                print("      - HTML of failing card:")
                print(position.get_attribute('outerHTML'))
            continue
    
    print("\n  --- Parsing Summary ---")
    summary = f"  Found {len(roles)} jobs from {len(positions)} cards"
    if promoted_included > 0:
        summary += f" ({promoted_included} promoted)"
    if skipped_no_keywords > 0:
        summary += f", skipped {skipped_no_keywords} on keyword filter"
    print(summary)
    
    return roles

def scrape_url(url, check_keywords=False, show_details=False):
    """Scrape a single LinkedIn URL with pagination and lazy loading."""
    driver = init_driver()
    driver.set_page_load_timeout(300)
    all_roles = []
    
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        driver.get(url)
        time.sleep(10)
        
        if "login" in driver.current_url.lower() or "authwall" in driver.current_url.lower():
            print("  ✗ Not logged in! Please run: python log_in_to_linkedin.py")
            driver.quit()
            return []

        page_number = 1
        jobs_per_page = 25
        max_pages = 10 # Safety limit
        
        while page_number <= max_pages:
            print(f"\n  --- Page {page_number} ---")
            
            if page_number > 1:
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                query_params['start'] = [(page_number - 1) * jobs_per_page]
                new_query = urlencode(query_params, doseq=True)
                page_url = urlunparse((
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    parsed_url.params,
                    new_query,
                    parsed_url.fragment
                ))
                driver.get(page_url)
                time.sleep(5)
            
            print("  - Scrolling to load all jobs on the page...")
            try:
                scroll_container = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".scaffold-layout__list-container"))
                )
                
                last_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
                scroll_attempts = 0
                max_scroll_attempts = 20

                while scroll_attempts < max_scroll_attempts:
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
                    time.sleep(2.5)
                    new_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
                    
                    if new_height == last_height:
                        break
                    last_height = new_height
                    scroll_attempts += 1
                
                print("  - Scrolling complete.")

            except Exception as e:
                print(f"    ✗ Could not find scroll container or scroll failed: {e}")

            master_selector = "li.occludable-update"
            positions = driver.find_elements(By.CSS_SELECTOR, master_selector)
            
            print(f"  - Found {len(positions)} potential job cards in the HTML.")
            
            if not positions:
                print("  - No more jobs found on this page.")
                break

            roles = parse_job_listings(driver, positions, check_keywords, True) # Force show_details for logging
            all_roles.extend(roles)
            
            if len(positions) < jobs_per_page:
                print("\n  - Reached the last page of results.")
                break
            
            page_number += 1
        
        print(f"\n  ✓ Total from this URL: {len(all_roles)} jobs")
        
    except Exception as e:
        print(f"  ✗ An error occurred during scraping: {e}")
    finally:
        driver.quit()
    
    return all_roles

def get_recent_roles(show_details=True): # Changed default to True for logging
    """Get roles from all configured URLs"""
    all_roles = []
    print("\n" + "="*60)
    print("LinkedIn Job Search (Detailed Log Mode)")
    print("="*60)

    # Scrape unfiltered URLs
    unfiltered_urls = parse_multiline_urls(LINKEDIN_URLS_UNFILTERED)
    if unfiltered_urls:
        for i, (url, note) in enumerate(unfiltered_urls, 1):
            print(f"\n📋 Unfiltered Search {i}/{len(unfiltered_urls)}: {note or 'General'}")
            roles = scrape_url(url, check_keywords=False, show_details=show_details)
            all_roles.extend(roles)
            if i < len(unfiltered_urls):
                time.sleep(5)

    # Scrape filtered URLs
    filtered_urls = parse_multiline_urls(LINKEDIN_URLS_FILTERED)
    if filtered_urls:
        for i, (url, note) in enumerate(filtered_urls, 1):
            print(f"\n🔍 Filtered Search {i}/{len(filtered_urls)}: {note or 'Marketing Keywords'}")
            roles = scrape_url(url, check_keywords=True, show_details=show_details)
            all_roles.extend(roles)
            if i < len(filtered_urls):
                time.sleep(5)

    print("\n" + "="*60)
    print(f"✓ Search Complete: {len(all_roles)} total jobs found")
    print("="*60 + "\n")
    return all_roles

if __name__ == '__main__':
    get_recent_roles(show_details=True)

