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
    options.add_argument("--log-level=3")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    service = ChromeService(executable_path=ChromeDriverManager().install())
    service.log_path = os.devnull
    
    return webdriver.Chrome(options=options, service=service)

def check_keywords_in_text(text, return_details=False):
    """Check if text contains any JOB_KEYWORDS and none of the EXCLUDED_KEYWORDS."""
    if not text:
        return (False, [], {}) if return_details else False

    text_lower = text.lower()
    matched_keywords = []
    
    # Check for required keywords
    has_required_keyword = False
    for keyword in JOB_KEYWORDS:
        if keyword.lower() in text_lower:
            has_required_keyword = True
            matched_keywords.append(keyword)

    if not has_required_keyword:
        return (False, [], {}) if return_details else False

    # Check for excluded keywords
    for keyword in EXCLUDED_KEYWORDS:
        if keyword.lower() in text_lower:
            return (False, [], {}) if return_details else False
            
    if return_details:
        return True, matched_keywords, {}
        
    return True

def get_job_description_optimized(driver, show_details=False):
    """
    Get job description from the currently displayed job details panel.
    This avoids navigating away from the search results page.
    """
    try:
        # Wait for job details to load
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-search__job-details"))
        )
        time.sleep(1)  # Small delay for content to fully render
        
        # Try to click "Show more" button to expand description
        try:
            show_more_selectors = [
                "button.show-more-less-html__button--more",
                "button.show-more-less-html__button",
                ".jobs-description__footer-button"
            ]
            
            for selector in show_more_selectors:
                try:
                    show_more_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if show_more_btn.is_displayed():
                        driver.execute_script("arguments[0].click();", show_more_btn)
                        time.sleep(0.5)
                        if show_details:
                            print("      - Clicked 'Show more' button.")
                        break
                except:
                    continue
        except:
            pass  # Show more button not found or not needed
        
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
        
        return description_text
        
    except Exception as e:
        if show_details:
            print(f"      - ✗ Error getting description: {e}")
        return ""

def parse_job_listings(driver, check_keywords=False, show_details=False):
    """
    Parse job listings with optimized keyword checking.
    For filtered searches, we click each job card and read the description
    from the side panel without navigating away.
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

    # Iterate by index
    for i in range(num_positions):
        if show_details:
            print(f"\n  --- Processing Card {i+1}/{num_positions} ---")
        
        try:
            # Re-find elements on each iteration
            positions = driver.find_elements(By.CSS_SELECTOR, master_selector)
            if i >= len(positions):
                if show_details:
                    print(f"    - ✗ Card index {i+1} is out of bounds. Ending page parse.")
                break
            
            position = positions[i]

            # Scroll card into view
            driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", position)
            time.sleep(0.3)

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
                    if show_details: 
                        print("    - ✗ Company name not found.")
            if show_details: 
                print(f"    - Company: {company}")

            # Get job link
            link = ""
            try:
                link_element = position.find_element(By.CSS_SELECTOR, "a[href*='/jobs/view/']")
                link = link_element.get_attribute('href').split('?')[0]
            except Exception as e:
                if show_details: 
                    print(f"    - ✗ Job link not found. Error: {e}")
                continue
            if show_details: 
                print(f"    - Link: {link}")
                
            # Get job title
            title = "N/A"
            try:
                title = position.find_element(By.CSS_SELECTOR, "a.job-card-container__link strong").text.strip()
            except:
                if show_details: 
                    print("    - ✗ Job title not found.")
            if show_details: 
                print(f"    - Title: {title}")

            # Get posted time
            posted_time = "N/A"
            try:
                posted_time = position.find_element(By.CSS_SELECTOR, "time").text.strip()
            except:
                pass
            if show_details: 
                print(f"    - Posted: {posted_time}")

            # Check keywords if needed - OPTIMIZED APPROACH
            if check_keywords:
                # Click the job card to load details in the side panel
                try:
                    link_element = position.find_element(By.CSS_SELECTOR, "a.job-card-container__link")
                    driver.execute_script("arguments[0].click();", link_element)
                    time.sleep(1.5)  # Wait for side panel to load
                    
                    # Get description from side panel (no navigation needed!)
                    description = get_job_description_optimized(driver, show_details)
                    
                    title_and_description = f"{title} {description}"
                    found, matched_keywords, _ = check_keywords_in_text(title_and_description, return_details=True)
                    
                    if show_details:
                        if found:
                            print(f"      - ✓ Keywords matched: {', '.join(matched_keywords[:5])}")
                        else:
                            print("      - ✗ No relevant keywords matched.")
                    
                    if not found:
                        skipped_no_keywords += 1
                        if show_details:
                            print("    - Result: SKIPPED (keyword filter)")
                        continue
                        
                except Exception as e:
                    if show_details:
                        print(f"      - ✗ Error checking keywords: {e}")
                    # If we can't check keywords, skip this job to be safe
                    skipped_no_keywords += 1
                    continue

            # Get company picture
            picture = "https://via.placeholder.com/100"
            try:
                img_element = position.find_element(By.CSS_SELECTOR, "img")
                picture = img_element.get_attribute('src')
            except:
                pass

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
        max_pages = 10
        
        while page_number <= max_pages:
            if show_details:
                print(f"\n  --- Page {page_number} ---")
            else:
                print(f"  Page {page_number}...", end=" ")

            # Navigate to the page
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
            
            # Scroll to load all jobs
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

            # Get the actual number of job cards on this page
            positions = driver.find_elements(By.CSS_SELECTOR, "li.occludable-update")
            actual_jobs_on_page = len(positions)
            
            if show_details:
                print(f"  - Found {actual_jobs_on_page} job cards on this page")
            
            # Parse the jobs
            roles_on_page = parse_job_listings(driver, check_keywords, show_details)
            all_roles.extend(roles_on_page)
            
            if not show_details:
                promoted_count = sum(1 for pos in positions if 'promoted' in pos.text.lower())
                print(f"  Found {len(roles_on_page)} jobs ({promoted_count} promoted)")

            # FIXED: Check if there are fewer job cards than expected (reached end)
            # Don't rely on roles_on_page length when filtering is enabled
            if actual_jobs_on_page < jobs_per_page:
                if show_details:
                    print(f"\n  - Reached the last page (only {actual_jobs_on_page} jobs found, expected {jobs_per_page}).")
                break
            
            # Check if next page button exists and is enabled
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, "button.jobs-search-pagination__button--next")
                if "disabled" in next_button.get_attribute("class") or not next_button.is_enabled():
                    if show_details:
                        print("\n  - Next button is disabled. Reached the last page.")
                    break
            except:
                if show_details:
                    print("\n  - Next button not found. Might be the last page.")
                # Continue anyway, the page navigation will fail naturally if there's no next page
            
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