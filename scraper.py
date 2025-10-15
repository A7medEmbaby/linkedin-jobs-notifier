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
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    
                    try:
                        overlay = driver.find_element(By.CSS_SELECTOR, ".show-more-less-html__fade-overlay")
                        driver.execute_script("arguments[0].remove();", overlay)
                        if show_details:
                            print("      - Removed description overlay.")
                        time.sleep(0.5)
                    except:
                        pass
                    
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

def parse_job_listings(driver, check_keywords=False, show_details=False):
    """
    Parse job listings, handling potential stale elements by re-finding them
    after page navigations.
    """
    roles = []
    skipped_no_keywords = 0
    promoted_included = 0
    
    master_selector = "li.occludable-update"
    
    # Get initial count of job cards
    positions = driver.find_elements(By.CSS_SELECTOR, master_selector)
    num_positions = len(positions)

    if show_details:
        print(f"  - Found {num_positions} potential job cards in the HTML.")

    # Iterate by index to handle stale elements
    for i in range(num_positions):
        if show_details:
            print(f"\n  --- Processing Card {i+1}/{num_positions} ---")
        
        try:
            # Re-find elements on each iteration to get a fresh reference
            positions = driver.find_elements(By.CSS_SELECTOR, master_selector)
            if i >= len(positions):
                if show_details:
                    print(f"    - ✗ Card index {i+1} is out of bounds after navigation. Ending page parse.")
                break
            
            position = positions[i]

            # Scroll each job card into view before parsing
            driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", position)
            time.sleep(0.5)

            # Check if promoted
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
            company = "N/A"
            try:
                company = position.find_element(By.CSS_SELECTOR, ".artdeco-entity-lockup__subtitle").text.strip()
            except:
                try:
                    company = position.find_element(By.CSS_SELECTOR, ".job-card-container__primary-description").text.strip()
                except:
                    if show_details: print("    - ✗ Company name not found.")
            if show_details: print(f"    - Company: {company}")

            # Get job link
            link = ""
            try:
                link_element = position.find_element(By.CSS_SELECTOR, "a[href*='/jobs/view/']")
                link = link_element.get_attribute('href').split('?')[0]
            except Exception as e:
                if show_details: print(f"    - ✗ Job link not found. Error: {e}")
                continue # Skip this card if link is not found
            if show_details: print(f"    - Link: {link}")
                
            # Get job title
            title = "N/A"
            try:
                title = position.find_element(By.CSS_SELECTOR, "a.job-card-container__link strong").text.strip()
            except:
                if show_details: print("    - ✗ Job title not found.")
            if show_details: print(f"    - Title: {title}")

            # Get posted time
            posted_time = "N/A"
            try:
                posted_time = position.find_element(By.CSS_SELECTOR, "time").text.strip()
            except:
                pass # Not critical if not found
            if show_details: print(f"    - Posted: {posted_time}")


            # Check keywords if needed
            if check_keywords:
                original_url = driver.current_url
                description = get_job_description(driver, link, title, company, show_details)
                
                # Navigate back to the search results page
                driver.get(original_url)
                
                # Wait for the job list to be present again to avoid stale elements
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, master_selector))
                )
                time.sleep(1.5) # Extra buffer for dynamic content to settle

                title_and_description = f"{title} {description}"
                found = check_keywords_in_text(title_and_description)
                
                if not found:
                    skipped_no_keywords += 1
                    if show_details:
                        print("    - Result: SKIPPED (keyword filter)")
                    continue

            # Get company picture
            picture = "https://via.placeholder.com/100"
            try:
                img_element = position.find_element(By.CSS_SELECTOR, "img")
                picture = img_element.get_attribute('src')
            except:
                pass # Not critical if not found

            roles.append((company, title, link, picture, posted_time))
            if show_details:
                print("    - Result: ADDED to list")
            
        except Exception as e:
            if show_details:
                print(f"    - ✗ UNEXPECTED ERROR parsing card {i+1}: {e}")
            continue
    
    if show_details:
        print("\n  --- Parsing Summary ---")
        summary = f"  Found {len(roles)} jobs from {num_positions} cards"
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
            if show_details:
                print(f"\n  --- Page {page_number} ---")
            else:
                print(f"  Page {page_number}...", end=" ")

            
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
            
            if show_details:
                print("  - Scrolling to load all jobs on the page...")
            else:
                print("Scrolling...", end=" ")

            try:
                scroll_container = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".scaffold-layout__list"))
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
                
                if show_details:
                    print("  - Scrolling complete.")
                else:
                    print("Done.", end="")

            except Exception as e:
                if show_details:
                    print(f"    ✗ Could not find scroll container or scroll failed: {e}")
                else:
                    print("Scroll failed.", end=" ")

            roles_on_page = parse_job_listings(driver, check_keywords, show_details)
            all_roles.extend(roles_on_page)
            
            if not show_details:
                # Count promoted from the original list as parsing re-finds elements
                positions = driver.find_elements(By.CSS_SELECTOR, "li.occludable-update")
                promoted_count = sum(1 for pos in positions if 'promoted' in pos.text.lower())
                print(f"  Found {len(roles_on_page)} jobs ({promoted_count} promoted)")

            if len(roles_on_page) < jobs_per_page:
                if show_details:
                    print("\n  - Reached the last page of results.")
                break
            
            page_number += 1
        
        print(f"\n  ✓ Total from this URL: {len(all_roles)} jobs")
        
    except Exception as e:
        print(f"  ✗ An error occurred during scraping: {e}")
    finally:
        driver.quit()
    
    return all_roles

def get_recent_roles(show_details=False):
    """Get roles from all configured URLs"""
    all_roles = []
    log_mode = "(Detailed Log Mode)" if show_details else ""
    print("\n" + "="*60)
    print(f"LinkedIn Job Search {log_mode}")
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
    show_details_arg = os.getenv('SHOW_DETAILED_LOGS', 'False').lower() == 'true'
    get_recent_roles(show_details=show_details_arg)

