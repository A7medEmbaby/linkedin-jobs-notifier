# LinkedIn Jobs Notifier
LinkedIn Jobs scraper with a Discord bot "front end" written in Python

![LinkedIn Jobs Notifier Preview](https://github.com/hotsno/linkedin-jobs-notifier/assets/71658949/231d1819-56fb-459b-9658-ebd5b33e29cd)

## Features
- 🔔 Sends new postings on LinkedIn Jobs for a given search query to a Discord channel
- ⏱️ Saves users time from repeat and sponsored postings
- 🚫 Allows users to blacklist companies
- 🔗 Provides links to a Google and [Levels.fyi](https://levels.fyi) search of the company
- 🔄 Automatically checks for new jobs every 20 minutes
- 🛡️ Filters out promoted/sponsored job listings

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
- `selenium` - For web scraping LinkedIn
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

# Your LinkedIn job search URL (see examples below)
LINKEDIN_URL=YOUR_LINKEDIN_SEARCH_URL

# Directory to store browser session (can be any path)
# Example: C:/Users/YourName/linkedin-bot-data
SELENIUM_USER_DATA_DIR=YOUR_PATH_HERE

# Discord channel IDs from Step 4
NEW_POSTINGS_CHANNEL_ID=123456789012345678
DEBUG_CHANNEL_ID=123456789012345678
COMPANIES_CHANNEL_ID=123456789012345678
```

#### How to Get Your LinkedIn Search URL:

1. Go to [LinkedIn Jobs](https://www.linkedin.com/jobs/)
2. Search for the jobs you want (e.g., "Software Engineer")
3. Apply any filters (location, experience level, date posted, etc.)
4. Copy the **entire URL** from your browser's address bar
5. Paste it as the `LINKEDIN_URL` value

**Example URLs:**
```
# Software Engineer in MENA region, posted in last 24 hours
https://www.linkedin.com/jobs/search/?keywords=software%20engineer&location=MENA&f_TPR=r86400

# .NET Developer internships in Egypt
https://www.linkedin.com/jobs/search/?keywords=.net%20developer&location=Egypt&f_E=1

# Remote Python jobs
https://www.linkedin.com/jobs/search/?keywords=python&f_WT=2
```

**Pro Tips:**
- Use `f_TPR=r86400` in the URL to filter jobs posted in the last 24 hours
- Use `f_WT=2` for remote jobs only
- Use `f_E=1,2` for entry-level jobs

### Step 7: Run the Bot

```bash
python bot.py
```

**You should see:**
```
Logged in as YourBotName#1234 (ID: xxxxxxxxx)
------
```

**In your Discord #debug channel, you'll see:**
```
Trying to get new roles...
Number of non-sponsored roles: X
Succeeded. Waiting 20 minutes.
```

**In your #new-jobs channel, you'll see:**
- Job posting embeds with company logo, title, and links

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
- The bot checks LinkedIn every **20 minutes**
- It scrolls through the job listings page to load all results
- Filters out **sponsored/promoted** jobs automatically
- Compares against previously posted jobs (stored in `config.json`)
- Posts only **new, unique jobs** to avoid spam

### Job Posting Format
Each job is posted as a Discord embed containing:
- **Company name** (clickable - links to Google search)
- **Job title** (clickable - links to LinkedIn job posting)
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

2. **Check your LinkedIn URL:**
   - Make sure it's a valid job search URL
   - Test the URL in your browser first
   - Verify you see job listings when you open it

3. **Run the debug script:**
   ```bash
   python debug_linkedin.py
   ```
   This will show you what selectors work and save the page HTML

### Selenium Errors

**Problem:** "Unable to locate element" or "Element not found"

**Solutions:**
- LinkedIn may have changed their HTML structure
- Try increasing wait time in `scraper.py` (change `time.sleep(10)` to `time.sleep(15)`)
- Make sure Chrome is up to date
- Check if you're actually logged in

### Bot Crashes or Stops

**Problem:** Bot stops after some time

**Solutions:**
1. **Check the #debug channel** for error messages
2. **LinkedIn session expired** - Re-run `log_in_to_linkedin.py`
3. **Rate limiting** - LinkedIn might be blocking requests. Wait a few hours and try again
4. **Run in background** (for 24/7 operation):
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

### Rate Limiting / Blocked by LinkedIn

**Problem:** Bot gets blocked or can't access LinkedIn

**Solutions:**
- Don't run the bot too frequently (20 minutes is recommended)
- Use a residential IP (not VPN or data center)
- Make sure your LinkedIn account is in good standing
- Consider using LinkedIn's official API if available

## File Structure

```
linkedin-jobs-notifier/
├── bot.py                    # Main Discord bot logic
├── scraper.py                # LinkedIn scraping functionality
├── log_in_to_linkedin.py     # Script to save LinkedIn session
├── debug_linkedin.py         # Diagnostic tool (optional)
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── .env                      # Your actual config (not tracked by git)
├── config.json              # Stores posted jobs and blacklist
├── .gitignore               # Git ignore rules
└── README.md                # This file
```

## Advanced Configuration

### Changing Check Interval

Edit `bot.py` line 108:
```python
await asyncio.sleep(60 * 20)  # Change 20 to desired minutes
```

### Multiple Job Searches

To monitor multiple searches, you can:
1. Run multiple instances with different `.env` files
2. Or modify the code to loop through multiple URLs

### Custom Embed Colors

Edit `bot.py` line 88:
```python
color=discord.Color.from_str("#378CCF")  # Change hex color
```

## Contributing

Contributions are welcome! Feel free to:
- Open issues for bugs or feature requests
- Submit pull requests with improvements
- Share your customizations

## License

This project is open source and available under the MIT License.

## Disclaimer

This bot is for personal use only. Please respect LinkedIn's Terms of Service and use responsibly. Don't spam or abuse the platform.

## Credits

- Original project by [hotsno](https://github.com/hotsno/linkedin-jobs-notifier)
- Updated and maintained by the community

## Support

If you encounter issues:
1. Check this README's Troubleshooting section
2. Run `debug_linkedin.py` to diagnose problems
3. Open an issue on GitHub with:
   - Error messages from console
   - Steps to reproduce
   - Your Python version (`python --version`)

---

**Happy job hunting! 🚀**