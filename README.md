# LinkedIn & Wuzzuf Jobs Notifier
Job scraper with Discord bot integration - monitors LinkedIn and Wuzzuf for .NET developer positions

![LinkedIn Jobs Notifier Preview](https://github.com/hotsno/linkedin-jobs-notifier/assets/71658949/231d1819-56fb-459b-9658-ebd5b33e29cd)

## Features
- 🔔 Sends new job postings from LinkedIn and Wuzzuf to Discord
- 🎯 Smart keyword filtering for .NET positions
- 📄 Multi-page LinkedIn scraping with pagination support
- ⏱️ Filters out duplicate and sponsored postings
- 🚫 Company blacklist functionality
- 🔗 Provides links to Google and [Levels.fyi](https://levels.fyi) searches
- 🔄 Automatically checks for new jobs every 20 minutes
- 🛡️ Includes promoted jobs in results (tracked separately)
- 🌐 Dual-source scraping: LinkedIn + Wuzzuf

## Requirements
- Python ≥3.10
- Git
- Chrome (or Chromium) browser
- A Discord account with permissions to create a bot
- A LinkedIn account

## Step-by-Step Installation Guide

### Step 1: Clone the Repository
```bash
git clone https://github.com/A7medEmbaby/linkedin-jobs-notifier.git
cd linkedin-jobs-notifier
```

### Step 2: Install Required Dependencies
```bash
pip install -r requirements.txt
```
> **Note:** If the command doesn't work, try `pip3 install -r requirements.txt` instead

**What gets installed:**
- `discord.py` - For Discord bot functionality
- `selenium` - For web scraping LinkedIn and Wuzzuf
- `webdriver-manager` - Automatically manages Chrome driver
- `python-dotenv` - For managing environment variables

### Step 3: Create Your Discord Bot

1. **Go to Discord Developer Portal**
   - Visit: https://discord.com/developers/applications
   - Log in with your Discord account

2. **Create a New Application**
   - Click the **"New Application"** button (top right)
   - Give it a name (e.g., "LinkedIn Jobs Bot")
   - Click **"Create"**

3. **Create the Bot**
   - In the left sidebar, click **"Bot"**
   - Click **"Add Bot"** and confirm
   - Under the Token section, click **"Reset Token"** and then **"Copy"**
   - **⚠️ Save this token securely** - you'll need it for the `.env` file

4. **Enable Required Intents**
   - Scroll down to **"Privileged Gateway Intents"**
   - Enable these two intents:
     - ✅ **Server Members Intent**
     - ✅ **Message Content Intent**
   - Click **"Save Changes"**

5. **Generate Invite Link**
   - In the left sidebar, click **"OAuth2"** → **"URL Generator"**
   - Under **"Scopes"**, select: `bot`
   - Under **"Bot Permissions"**, select:
     - ✅ Send Messages
     - ✅ Embed Links
     - ✅ Read Messages/View Channels
     - ✅ Read Message History
   - Copy the **Generated URL** at the bottom
   - Open the URL in your browser to invite the bot to your server

### Step 4: Set Up Discord Channels

Create three text channels in your Discord server:

1. **#new-jobs** - For new job postings (embeds with job details)
2. **#debug** - For bot status messages and error logs
3. **#companies** - For company lists and blacklist confirmations

**To get each channel ID:**
1. Enable Developer Mode in Discord:
   - User Settings → Advanced → Enable **Developer Mode**
2. Right-click on each channel
3. Click **"Copy Channel ID"**
4. Save these IDs - you'll need them for the `.env` file

### Step 5: Log In to LinkedIn

This step saves your LinkedIn session so the bot can access job listings.

```bash
python log_in_to_linkedin.py
```

**What happens:**
1. A Chrome window will open automatically
2. Navigate to the LinkedIn login page
3. **Log in with your LinkedIn credentials**
4. Make sure you're fully logged in (see your feed/profile)
5. Return to the terminal and **press Enter**
6. The window will close

> **Important:** Your session is saved locally in the directory specified by `SELENIUM_USER_DATA_DIR`. Don't delete this folder!

### Step 6: Configure Environment Variables

1. **Rename the example file:**
   ```bash
   # On Windows (PowerShell)
   Rename-Item .env.example .env
   
   # On Linux/Mac
   mv .env.example .env
   ```

2. **Edit the `.env` file** with your favorite text editor (Notepad, VS Code, etc.)

3. **Fill in all the values** (⚠️ **DO NOT use quotation marks**):

```env
# Your Discord bot token from Step 3
BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# Your main LinkedIn job search URL (no keyword filtering)
LINKEDIN_URL=YOUR_LINKEDIN_SEARCH_URL

# Additional LinkedIn URLs with .NET keyword filtering (comma-separated)
LINKEDIN_KEYWORD_URLS=URL1,URL2,URL3

# Wuzzuf job search URL (optional, with .NET keyword filtering)
WUZZUF_URL=YOUR_WUZZUF_SEARCH_URL

# Directory to store browser session (can be any path)
# Example: C:/Users/YourName/linkedin-bot-data
SELENIUM_USER_DATA_DIR=YOUR_PATH_HERE

# Discord channel IDs from Step 4
NEW_POSTINGS_CHANNEL_ID=123456789012345678
DEBUG_CHANNEL_ID=123456789012345678
COMPANIES_CHANNEL_ID=123456789012345678
```

#### Understanding the URL Configuration:

**`LINKEDIN_URL`** - Main search (no filtering)
- All jobs from this URL are posted without keyword filtering
- Use this for your primary job search

**`LINKEDIN_KEYWORD_URLS`** - Filtered searches (comma-separated)
- Jobs from these URLs are filtered for .NET keywords
- Each job's title and description is checked for .NET-related terms
- Separate multiple URLs with commas
- Example: `URL1,URL2,URL3`

**`WUZZUF_URL`** - Wuzzuf search (optional, with filtering)
- Filters jobs by checking title and skills for .NET keywords
- Leave empty if you don't want to scrape Wuzzuf

#### How to Get Your LinkedIn Search URL:

1. Go to [LinkedIn Jobs](https://www.linkedin.com/jobs/)
2. Search for the jobs you want (e.g., "Software Engineer")
3. Apply any filters (location, experience level, date posted, etc.)
4. Copy the **entire URL** from your browser's address bar
5. Paste it as the appropriate value in `.env`

**Example Configuration:**
```env
# Get ALL software engineering jobs in Egypt
LINKEDIN_URL=https://www.linkedin.com/jobs/search/?keywords=software%20engineer&location=Egypt&f_TPR=r86400

# Check these searches for .NET keywords specifically
LINKEDIN_KEYWORD_URLS=https://www.linkedin.com/jobs/search/?keywords=developer&location=Egypt,https://www.linkedin.com/jobs/search/?keywords=backend&location=MENA

# Check Wuzzuf for .NET jobs
WUZZUF_URL=https://wuzzuf.net/search/jobs/?q=developer&a=hpb
```

**Pro Tips:**
- Use `f_TPR=r86400` in the URL to filter jobs posted in the last 24 hours
- Use `f_WT=2` for remote jobs only
- Use `f_E=1,2` for entry-level jobs
- The bot automatically scrolls through multiple pages on LinkedIn (up to 10 pages)

#### .NET Keyword Detection:

The bot searches for these keywords in job titles and descriptions:
- `.net`, `dotnet`, `dot net`, `.net core`, `.net framework`
- `.net 6`, `.net 7`, `.net 8`, `.net 9`
- `asp.net`, `asp.net core`, `asp.net mvc`, `asp.net web api`
- `c#`, `c sharp`, `csharp`
- `entity framework`, `ef core`
- `blazor`, `razor`, `wcf`, `wpf`, `xamarin`, `maui`
- `visual studio`, `nuget`

> **💡 Tip:** You can customize these keywords to match your job requirements! See the [Adding More Keywords](#adding-more-keywords) section below to learn how to add Python, Java, or any other technology keywords.

### Step 7: Run the Bot

```bash
python bot.py
```

**You should see:**
```
Starting LinkedIn Jobs Notifier Bot...
============================================================
✓ Bot logged in as YourBotName#1234
------------------------------------------------------------
```

**In your Discord #debug channel, you'll see:**
```
🔍 Starting job search cycle at HH:MM:SS
⏳ Scraping LinkedIn...
⏳ Scraping Wuzzuf...
✅ Posted X new jobs from Y companies
⏱️ Scraping took Xm Ys
😴 Waiting 20 minutes before next check...
⏰ Next check at: HH:MM:SS
```

**In your #new-jobs channel, you'll see:**
- Job posting embeds with company logo, title, source (LinkedIn or Wuzzuf), and links

🎉 **Congratulations! Your bot is now running!**

## Using the Bot

### Blacklisting Companies

If you want to ignore jobs from certain companies, use the blacklist feature:

**In any Discord channel where the bot can read messages:**

```
!blacklist
Company Name 1
Company Name 2
Company Name 3
```

**Example:**
```
!blacklist
Acme Corp
TechCorp Inc
Another Company
```

The bot will confirm in the **#companies** channel:
```
Added Acme Corp, TechCorp Inc, Another Company to the blacklist!
```

### Removing Companies from Blacklist

```
!unblacklist
Company Name 1
Company Name 2
```

The bot will confirm the removal in the **#companies** channel.

## How It Works

### Automatic Job Checking
- The bot checks LinkedIn and Wuzzuf every **20 minutes**
- **LinkedIn scraping:**
  - Automatically scrolls through up to 10 pages per search URL
  - Main URL: Posts all jobs without filtering
  - Keyword URLs: Filters jobs by .NET keywords in title and description
  - Tracks promoted jobs separately
- **Wuzzuf scraping:**
  - Checks job titles first for .NET keywords
  - If title doesn't match, navigates to job details page to check skills section
  - Only posts jobs with .NET-related skills
- Compares against previously posted jobs (stored in `config.json`)
- Posts only **new, unique jobs** to avoid spam
- Handles Discord connection issues gracefully with automatic reconnection

### Job Posting Format
Each job is posted as a Discord embed containing:
- **Company name** (clickable - links to Google search)
- **Job title** (clickable - links to job posting)
- **Source** (LinkedIn or Wuzzuf)
- **Company logo** (thumbnail image)
- **Levels.fyi link** (for salary research)
- **Timestamp** (when the bot found the job)

### Data Storage
The bot maintains a `config.json` file with:
- `posted`: Array of all jobs already sent (format: "Company - Job Title")
- `blacklist`: Array of blacklisted company names

**Example `config.json`:**
```json
{
  "blacklist": [
    "Acme Corp",
    "Spam Company Inc"
  ],
  "posted": [
    "Google - Software Engineer",
    "Microsoft - .NET Developer",
    "Amazon - Backend Engineer"
  ]
}
```

## Troubleshooting

### Bot Not Finding Jobs

**Problem:** Bot shows 0 jobs found or "No new roles"

**Solutions:**
1. **Re-login to LinkedIn:**
   ```bash
   python log_in_to_linkedin.py
   ```
   Make sure you fully log in before pressing Enter

2. **Check your LinkedIn URLs:**
   - Make sure they're valid job search URLs
   - Test the URLs in your browser first
   - Verify you see job listings when you open them

3. **Run scrapers individually:**
   ```bash
   # Test LinkedIn scraper
   python scraper.py
   
   # Test with detailed output
   python scraper.py --details
   
   # Test Wuzzuf scraper
   python wuzzuf_scraper.py
   
   # Test with detailed output
   python wuzzuf_scraper.py --details
   ```

### Selenium Errors

**Problem:** "Unable to locate element" or "Element not found"

**Solutions:**
- LinkedIn/Wuzzuf may have changed their HTML structure
- The bot includes multiple CSS selector fallbacks
- Make sure Chrome is up to date
- Check if you're actually logged in to LinkedIn
- Wait times are configured in the scrapers (10 seconds for LinkedIn, 3-5 seconds for Wuzzuf)

### Bot Crashes or Stops

**Problem:** Bot stops after some time

**Solutions:**
1. **Check the #debug channel** for error messages
2. **LinkedIn session expired** - Re-run `log_in_to_linkedin.py`
3. **Rate limiting** - LinkedIn might be blocking requests. Wait a few hours and try again
4. **Discord connection issues** - The bot now handles reconnections automatically
5. **Run in background** (for 24/7 operation):
   ```bash
   # Using screen (Linux)
   screen -S linkedin-bot
   python bot.py
   # Press Ctrl+A, then D to detach
   
   # Using nohup (Linux/Mac)
   nohup python bot.py &
   ```

### Commands Not Working

**Problem:** `python` or `pip` commands not recognized

**Solutions:**
- Try `python3` and `pip3` instead
- Verify Python is installed: `python --version`
- Add Python to PATH: [Instructions](https://realpython.com/add-python-to-path/)

### Discord Bot Offline

**Problem:** Bot shows as offline in Discord

**Solutions:**
1. Check if `bot.py` is still running in the terminal
2. Verify your bot token in `.env` is correct
3. Check bot intents are enabled in Discord Developer Portal
4. Make sure the bot has permissions in your server
5. The bot now automatically reconnects if disconnected

### Rate Limiting / Blocked by LinkedIn

**Problem:** Bot gets blocked or can't access LinkedIn

**Solutions:**
- Don't run the bot too frequently (20 minutes is recommended)
- Use a residential IP (not VPN or data center)
- Make sure your LinkedIn account is in good standing
- The bot uses headless mode to reduce detection

### Keyword Filtering Issues

**Problem:** Not finding .NET jobs or finding too many irrelevant jobs

**Solutions:**
1. **Check which URLs have filtering:**
   - `LINKEDIN_URL` = No filtering (all jobs posted)
   - `LINKEDIN_KEYWORD_URLS` = .NET keyword filtering
   - `WUZZUF_URL` = .NET keyword filtering

2. **Adjust your search terms:**
   - Use broader search terms in `LINKEDIN_KEYWORD_URLS`
   - Let the keyword filter handle the specificity

3. **Test the keyword detection:**
   - Run `python scraper.py --details` to see which keywords are found
   - Check the console output for matched keywords

## File Structure

```
linkedin-jobs-notifier/
├── bot.py                    # Main Discord bot logic with dual-source scraping
├── scraper.py                # LinkedIn scraping with pagination and keyword filtering
├── wuzzuf_scraper.py         # Wuzzuf scraping with keyword filtering
├── log_in_to_linkedin.py     # Script to save LinkedIn session
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── .env                      # Your actual config (not tracked by git)
├── config.json              # Stores posted jobs and blacklist
├── .gitignore               # Git ignore rules
└── README.md                # This file
```

## Advanced Configuration

### Changing Check Interval

Edit `bot.py` around line 300:
```python
await asyncio.sleep(60 * 20)  # Change 20 to desired minutes
```

### Changing Maximum Pages

Edit `scraper.py` around line 190:
```python
max_pages = 10  # Change to desired number of pages
```

### Adding More Keywords

**You can customize the keywords to search for any technology stack you want!**

Edit the `DOTNET_KEYWORDS` list in both `scraper.py` and `wuzzuf_scraper.py`:

```python
# Example: Adding Python keywords
DOTNET_KEYWORDS = [
    # Python keywords
    "python", "django", "flask", "fastapi",
    "python 3", "python3", "py3",
    "pandas", "numpy", "scipy",
    "pytorch", "tensorflow", "keras",
    "jupyter", "anaconda",
    
    # Or Java keywords
    "java", "spring", "spring boot", "springboot",
    "java 8", "java 11", "java 17",
    "hibernate", "maven", "gradle",
    "jsp", "servlet", "jdbc",
    
    # Or keep original .NET keywords
    ".net", "dotnet", "c#", "asp.net",
    # ... rest of keywords
]
```

**Steps to customize:**
1. Open `scraper.py` in a text editor
2. Find the `DOTNET_KEYWORDS` list (around line 22)
3. Replace or add your desired keywords
4. Save the file
5. Open `wuzzuf_scraper.py` and repeat steps 2-4
6. Restart the bot

**Examples for different tech stacks:**

<details>
<summary>🐍 Python Developer Keywords</summary>

```python
DOTNET_KEYWORDS = [
    "python", "django", "flask", "fastapi", "pyramid",
    "python 3", "python3", "py3", "python 2.7",
    "pandas", "numpy", "scipy", "matplotlib",
    "pytorch", "tensorflow", "keras", "scikit-learn",
    "jupyter", "anaconda", "pip", "virtualenv",
    "celery", "redis", "postgresql", "mongodb",
    "rest api", "graphql", "websocket",
    "docker", "kubernetes", "aws python"
]
```
</details>

<details>
<summary>☕ Java Developer Keywords</summary>

```python
DOTNET_KEYWORDS = [
    "java", "spring", "spring boot", "springboot",
    "java 8", "java 11", "java 17", "java 21",
    "hibernate", "jpa", "maven", "gradle",
    "jsp", "servlet", "jdbc", "jax-rs",
    "microservices", "rest api", "soap",
    "junit", "mockito", "jenkins",
    "tomcat", "wildfly", "weblogic"
]
```
</details>

<details>
<summary>⚛️ React Developer Keywords</summary>

```python
DOTNET_KEYWORDS = [
    "react", "reactjs", "react.js", "react js",
    "react native", "next.js", "nextjs",
    "redux", "redux toolkit", "mobx",
    "typescript", "javascript", "es6",
    "jsx", "hooks", "context api",
    "material-ui", "tailwind", "styled-components",
    "webpack", "vite", "babel"
]
```
</details>

<details>
<summary>🚀 Node.js Developer Keywords</summary>

```python
DOTNET_KEYWORDS = [
    "node.js", "nodejs", "node js",
    "express", "express.js", "nestjs",
    "javascript", "typescript",
    "mongodb", "mongoose", "postgresql",
    "rest api", "graphql", "websocket",
    "npm", "yarn", "pnpm",
    "jest", "mocha", "chai"
]
```
</details>

<details>
<summary>📱 Mobile Developer Keywords</summary>

```python
DOTNET_KEYWORDS = [
    "android", "kotlin", "java android",
    "ios", "swift", "objective-c",
    "flutter", "dart", "react native",
    "xamarin", "maui", "cordova",
    "mobile development", "mobile app"
]
```
</details>

> **Note:** After changing keywords, the bot will start filtering for your new tech stack. All previously posted jobs will remain in `config.json`, so you won't see duplicates.

### Custom Embed Colors

Edit `bot.py` around line 220:
```python
color=discord.Color.from_str("#378CCF")  # Change hex color
```

### Disabling Wuzzuf Scraping

Simply leave `WUZZUF_URL` empty in your `.env` file:
```env
WUZZUF_URL=
```

## Performance Notes

- **LinkedIn scraping:** Takes 2-5 minutes per search URL (depending on number of pages)
- **Wuzzuf scraping:** Takes 3-7 minutes (checks job details for keyword matching)
- **Total cycle time:** Usually 5-15 minutes depending on configuration
- **Memory usage:** ~150-300 MB (Chrome driver + Selenium)
- **Network usage:** ~50-100 MB per scraping cycle

## Contributing

Contributions are welcome! Feel free to:
- Open issues for bugs or feature requests
- Submit pull requests with improvements
- Share your customizations

## License

This project is open source and available under the MIT License.

## Disclaimer

This bot is for personal use only. Please respect LinkedIn's and Wuzzuf's Terms of Service and use responsibly. Don't spam or abuse the platforms.

## Credits

- Original project by [hotsno](https://github.com/hotsno/linkedin-jobs-notifier)
- Updated with Wuzzuf integration and keyword filtering by [A7medEmbaby](https://github.com/A7medEmbaby)
- Maintained by the community

## Support

If you encounter issues:
1. Check this README's Troubleshooting section
2. Run scrapers with `--details` flag to diagnose problems:
   ```bash
   python scraper.py --details
   python wuzzuf_scraper.py --details
   ```
3. Open an issue on GitHub with:
   - Error messages from console
   - Steps to reproduce
   - Your Python version (`python --version`)
   - Which URLs are configured in your `.env`

## Changelog

### Latest Updates
- ✨ Added Wuzzuf job scraping with keyword filtering
- ✨ Added LinkedIn pagination support (up to 10 pages per URL)
- ✨ Added multi-URL support with keyword filtering
- ✨ Added .NET keyword detection system
- ✨ Improved Discord connection handling with automatic reconnection
- ✨ Added detailed logging and progress tracking
- ✨ Improved error handling and retry logic
- 🐛 Fixed sponsored job filtering
- 🐛 Fixed duplicate job detection
- 📝 Enhanced console output with cycle tracking

---

**Happy job hunting! 🚀**
