from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os, time, json

load_dotenv()
WUZZUF_URL = os.getenv('WUZZUF_URL', '')

# .NET Keywords (same as LinkedIn scraper)
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
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
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

def get_job_skills(driver, job_url, show_details=False):
    """Navigate to job details page and extract skills"""
    try:
        driver.get(job_url)
        time.sleep(3)
        
        # Try to find skills section
        skills_text = ""
        skills_selectors = [
            # Skills as links
            "a[href*='/a/'][class*='css']",  # Generic skill links
            ".css-o171kl",  # Skill links from your HTML
            ".css-5x9pm1",  # Additional skill links
            # Skills in divs
            "div.css-1rhj4yg a",
            # Any link that looks like a skill
            "a[href*='/a/']"
        ]
        
        skills = []
        for selector in skills_selectors:
            try:
                skill_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in skill_elements:
                    skill_text = elem.text.strip()
                    if skill_text and skill_text not in skills:
                        # Filter out non-skill links
                        href = elem.get_attribute('href')
                        if href and '/a/' in href and '-Jobs-in-' in href:
                            skills.append(skill_text)
            except:
                continue
        
        skills_text = " ".join(skills)
        
        if show_details and skills:
            print(f"Skills found: {', '.join(skills[:10])}")
        
        return skills_text
        
    except Exception as e:
        if show_details:
            print(f"Error getting skills: {str(e)}")
        return ""

def parse_wuzzuf_jobs(driver, show_details=False):
    """Parse Wuzzuf job listings"""
    roles = []
    
    # Wait for job listings to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".css-ghe2tq"))
        )
    except:
        print("Timeout waiting for job listings")
        return roles
    
    # Find all job cards
    job_cards = driver.find_elements(By.CSS_SELECTOR, ".css-ghe2tq")
    print(f"Found {len(job_cards)} job cards")
    
    for idx, card in enumerate(job_cards, 1):
        try:
            if show_details:
                print(f"\n--- Job {idx}/{len(job_cards)} ---")
            
            # Get job title and link
            title = None
            link = None
            try:
                title_element = card.find_element(By.CSS_SELECTOR, "h2.css-193uk2c a")
                title = title_element.text.strip()
                link = title_element.get_attribute('href')
            except:
                continue
            
            if not title or not link:
                continue
            
            # Get company name
            company = None
            try:
                company_element = card.find_element(By.CSS_SELECTOR, ".css-ipsyv7")
                company = company_element.text.strip().replace(" -", "")
            except:
                try:
                    # Alternative selector
                    company_element = card.find_element(By.CSS_SELECTOR, "a[href*='/jobs/careers/']")
                    company = company_element.text.strip().replace(" -", "")
                except:
                    company = "Unknown Company"
            
            # Get company logo
            picture = None
            try:
                img_element = card.find_element(By.CSS_SELECTOR, "img")
                picture = img_element.get_attribute('src')
            except:
                # Try SVG placeholder
                picture = "https://via.placeholder.com/100"
            
            if show_details:
                print(f"Title: {title}")
                print(f"Company: {company}")
                print(f"Link: {link}")
            
            # Check if title contains .NET keywords
            title_has_keywords = check_keywords_in_text(title)
            
            if title_has_keywords:
                if show_details:
                    print("✓ Keywords found in TITLE")
                roles.append((company, title, link, picture))
            else:
                if show_details:
                    print("✗ No keywords in title, checking skills...")
                
                # Get job skills from detail page
                skills_text = get_job_skills(driver, link, show_details)
                
                # Check if skills contain keywords
                if check_keywords_in_text(skills_text):
                    if show_details:
                        print("✓ Keywords found in SKILLS")
                    roles.append((company, title, link, picture))
                else:
                    if show_details:
                        print("✗ No keywords found, skipping")
                
                # Navigate back to listings
                driver.back()
                time.sleep(2)
        
        except Exception as e:
            if show_details:
                print(f"Error processing job: {str(e)}")
            continue
    
    return roles

def scrape_wuzzuf(url=None, show_details=False):
    """Scrape Wuzzuf job listings"""
    if not url:
        url = WUZZUF_URL
    
    if not url:
        print("No Wuzzuf URL configured")
        return []
    
    driver = init_driver()
    all_roles = []
    
    try:
        print(f"\n{'='*80}")
        print("Scraping Wuzzuf.net...")
        print(f"{'='*80}\n")
        print(f"URL: {url}\n")
        
        driver.get(url)
        time.sleep(5)
        
        # Scroll to load all jobs
        try:
            for i in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
        except:
            pass
        
        # Parse jobs
        roles = parse_wuzzuf_jobs(driver, show_details)
        all_roles.extend(roles)
        
        print(f"\n{'='*80}")
        print(f"Wuzzuf scraping completed! Total jobs: {len(all_roles)}")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"Error scraping Wuzzuf: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()
    
    return all_roles

def get_wuzzuf_roles(show_details=False):
    """Main function to get Wuzzuf roles"""
    return scrape_wuzzuf(show_details=show_details)

if __name__ == "__main__":
    import sys
    
    show_details = "--details" in sys.argv or "-d" in sys.argv
    
    if show_details:
        print("Detailed mode enabled - will show job descriptions\n")
    
    roles = get_wuzzuf_roles(show_details=show_details)
    
    print("\nFinal Results:")
    print("="*80)
    print(json.dumps(roles, indent=2, ensure_ascii=False))
    
    if not show_details:
        print("\nTip: Run with --details to see more information")
        print("Example: python wuzzuf_scraper.py --details")