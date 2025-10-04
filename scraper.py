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

load_dotenv()
LINKEDIN_URL = os.getenv('LINKEDIN_URL')
LINKEDIN_KEYWORD_URLS = os.getenv('LINKEDIN_KEYWORD_URLS', '')
SELENIUM_USER_DATA_DIR = os.getenv('SELENIUM_USER_DATA_DIR')

# .NET Keywords
DOTNET_KEYWORDS = [
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

def init_driver():
    """Initialize Chrome driver with options"""
    options = Options()
    options.add_argument(f"user-data-dir={SELENIUM_USER_DATA_DIR}")
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    return webdriver.Chrome(options=options, service=ChromeService(executable_path=ChromeDriverManager().install()))

def check_keywords_in_text(text, return_details=False):
    """Check if any of the .NET keywords exist in the text"""
    if not text:
        if return_details:
            return False, [], {}
        return False
    
    text_lower = text.lower()
    matched_keywords = []
    search_locations = {}
    
    for keyword in DOTNET_KEYWORDS:
        keyword_lower = keyword.lower()
        if keyword_lower in text_lower:
            matched_keywords.append(keyword)
            index = text_lower.find(keyword_lower)
            context_start = max(0, index - 40)
            context_end = min(len(text), index + len(keyword) + 40)
            search_locations[keyword] = text[context_start:context_end]
    
    found = len(matched_keywords) > 0
    
    if return_details:
        return found, matched_keywords, search_locations
    return found

def get_job_description(driver, job_url, job_title, company_name, show_details=False):
    """Get job description from job details page"""
    try:
        if show_details:
            print(f"\nChecking: {job_title} at {company_name}")
            print(f"Link: {job_url}")
        
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
                    driver.execute_script("arguments[0].scrollIntoView();", show_more_btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", show_more_btn)
                    time.sleep(1)
                    break
                except:
                    continue
        except:
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
            return ""
        
        # Check keywords
        found, matched_keywords, locations = check_keywords_in_text(
            f"{job_title} {description_text}", 
            return_details=True
        )
        
        if show_details:
            if found:
                print(f"FOUND keywords: {', '.join(matched_keywords[:5])}")
                print(f"\nFirst 500 chars of description:")
                print("-" * 70)
                print(description_text[:500])
                print("-" * 70)
            else:
                print(f"NO keywords found")
                print(f"\nFirst 300 chars (for review):")
                print("-" * 70)
                print(description_text[:300])
                print("-" * 70)
        
        return description_text
        
    except Exception as e:
        if show_details:
            print(f"Error: {str(e)}")
        return ""

def parse_job_listings(driver, positions, check_keywords=False, show_details=False):
    """Parse job listings and return roles"""
    roles = []
    skipped_promoted = 0
    skipped_no_keywords = 0
    
    for position in positions:
        try:
            # Check if promoted
            promoted = False
            try:
                footer_items = position.find_elements(By.CSS_SELECTOR, ".job-card-container__footer-item")
                for item in footer_items:
                    if "promoted" in item.text.lower():
                        promoted = True
                        break
            except:
                pass
            
            if promoted:
                skipped_promoted += 1
                continue

            # Get company name
            company = None
            company_selectors = [
                ".IDYXRdYkvwPmKlSknVlDfSjxIGwKrqEPWozBQIVw",
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
                continue

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
                continue

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
                continue

            # Check keywords if needed
            if check_keywords:
                description = get_job_description(driver, link, title, company, show_details)
                
                title_and_description = f"{title} {description}"
                found = check_keywords_in_text(title_and_description)
                
                if not found:
                    skipped_no_keywords += 1
                    continue

            # Get company picture
            picture = None
            try:
                img_element = position.find_element(By.CSS_SELECTOR, "img")
                picture = img_element.get_attribute('src')
            except:
                picture = "https://via.placeholder.com/100"

            roles.append((company, title, link, picture))
            
        except Exception as e:
            continue
    
    print(f"Processed: {len(positions)} jobs | Promoted: {skipped_promoted} | No keywords: {skipped_no_keywords} | Added: {len(roles)}")
    
    return roles

def click_next_page(driver):
    """This function is no longer used - kept for compatibility"""
    return False

def scrape_url(url, check_keywords=False, show_details=False):
    """Scrape a single LinkedIn URL with pagination"""
    driver = init_driver()
    all_roles = []
    
    try:
        # Parse the base URL
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        print(f"Opening URL: {url}")
        
        # Check if logged in by visiting first
        driver.get(url)
        time.sleep(10)
        
        if "login" in driver.current_url.lower() or "authwall" in driver.current_url.lower():
            print("ERROR: Not logged in! Run: python log_in_to_linkedin.py")
            driver.quit()
            return []

        page_number = 1
        jobs_per_page = 25  # LinkedIn shows 25 jobs per page
        max_pages = 10  # Safety limit
        
        while page_number <= max_pages:
            print(f"\n--- Page {page_number} ---")
            
            # Build URL for current page
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            # Add or update start parameter
            if page_number > 1:
                query_params['start'] = [(page_number - 1) * jobs_per_page]
            elif 'start' in query_params:
                del query_params['start']
            
            # Rebuild URL
            new_query = urlencode(query_params, doseq=True)
            page_url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                new_query,
                parsed_url.fragment
            ))
            
            # Navigate to page (skip if first page, already loaded)
            if page_number > 1:
                driver.get(page_url)
                time.sleep(5)
            
            # Find job listings
            positions = []
            selectors = [
                "li.scaffold-layout__list-item",
                "li[data-occludable-job-id]"
            ]
            
            for selector in selectors:
                positions = driver.find_elements(By.CSS_SELECTOR, selector)
                if positions:
                    print(f"Found {len(positions)} job listings")
                    break
            
            if not positions:
                print("No jobs found on this page")
                break

            # Scroll to load all jobs on current page
            try:
                scroll_container = driver.find_element(By.CSS_SELECTOR, ".jobs-search-results-list")
                for i in range(3):
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
                    time.sleep(1)
                positions = driver.find_elements(By.CSS_SELECTOR, selector)
            except:
                pass

            # Parse job listings
            roles = parse_job_listings(driver, positions, check_keywords, show_details)
            all_roles.extend(roles)
            
            # Check if there are more pages by looking at results count
            if len(positions) < jobs_per_page:
                print(f"Last page reached (only {len(positions)} jobs found)")
                break
            
            page_number += 1
        
        print(f"Total jobs from all pages: {len(all_roles)}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()
    
    return all_roles

def get_recent_roles(show_details=False):
    """Get roles from all configured URLs"""
    all_roles = []
    
    print("\n" + "="*80)
    print("Starting job search...")
    print("="*80 + "\n")
    
    # Scrape main URL (always without keyword filtering)
    if LINKEDIN_URL:
        print(">>> Main URL (no keyword filtering)")
        roles = scrape_url(LINKEDIN_URL, check_keywords=False, show_details=False)
        all_roles.extend(roles)
        print(f"Total from main URL: {len(roles)} jobs\n")
    
    # Scrape additional URLs (optional, with keyword filtering)
    if LINKEDIN_KEYWORD_URLS and LINKEDIN_KEYWORD_URLS.strip():
        keyword_urls = [url.strip() for url in LINKEDIN_KEYWORD_URLS.split(',') if url.strip()]
        
        if keyword_urls:
            for i, url in enumerate(keyword_urls, 1):
                print(f"\n>>> Keyword URL {i}/{len(keyword_urls)} (with .NET filtering)")
                roles = scrape_url(url, check_keywords=True, show_details=show_details)
                all_roles.extend(roles)
                print(f"Total from URL {i}: {len(roles)} .NET jobs")
                
                if i < len(keyword_urls):
                    print("Waiting 5 seconds...")
                    time.sleep(5)
    
    print("\n" + "="*80)
    print(f"Search completed! Total jobs: {len(all_roles)}")
    print("="*80 + "\n")
    
    return all_roles

if __name__ == "__main__":
    import sys
    
    show_details = "--details" in sys.argv or "-d" in sys.argv
    
    if show_details:
        print("Detailed mode enabled - will show job descriptions\n")
    
    roles = get_recent_roles(show_details=show_details)
    
    print("\nFinal Results:")
    print("="*80)
    print(json.dumps(roles, indent=2, ensure_ascii=False))
    
    if not show_details:
        print("\nTip: Run with --details to see job descriptions")
        print("Example: python scraper.py --details")