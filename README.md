# ⏱️ Time Logger

A local desktop app for logging time to Jira tickets—without the context-switching pain.

## The Problem

Logging time in Jira is annoying:
- Switching to the browser interrupts your flow
- Remembering to log time throughout the day is hard
- Logging at month-end means inaccurate guesswork
- Working on multiple tickets per day makes it worse

## The Solution

Time Logger is a lightweight popup that:
- **Appears at 3 PM daily** (via Windows Task Scheduler)
- **Lets you log all your tickets in one place** (not one at a time in Jira)
- **Syncs to Jira automatically** with one click
- **Tracks your streak** to gamify the habit
- **Stores entries locally** so nothing is lost if Jira is down

![Time Logger Screenshot](screenshot.png) <!-- TODO: add screenshot -->

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Jira Credentials

```bash
copy .env.example .env
notepad .env  # Fill in your JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN
```

You'll need a Jira API token. Generate one at:  
https://id.atlassian.com/manage-profile/security/api-tokens

### 3. Test It Works

```bash
python setup.py test   # Verify Jira connection
python time_logger.py  # Open the app manually
```

### 4. Set Up Daily Reminders

```bash
python setup.py install
```

This creates two Windows scheduled tasks:
| Task | Schedule | What it does |
|------|----------|--------------|
| TimeLogger-Daily | 3:00 PM, Mon-Fri | Opens the time entry popup |
| TimeLogger-WeeklySummary | 4:00 PM, Fridays | Shows your weekly stats |

## Usage

### Logging Time

1. The popup appears at 3 PM (or run `python time_logger.py` anytime)
2. Enter your time:
   - **Ticket ID**: e.g., `DHI-1234`
   - **Hours**: e.g., `2` or `1.5`
   - **Description**: (optional) what you worked on
3. Click **+ Add Another Entry** for multiple tickets
4. Click **Save & Send to Jira**

### Commands

```bash
python time_logger.py              # Open the time entry popup
python weekly_summary.py           # Show weekly stats (GUI)
python weekly_summary.py --console # Show weekly stats (terminal)
python sync_pending.py             # Retry any failed Jira syncs
python setup.py status             # Check scheduled task status
python setup.py run                # Trigger the popup manually
python setup.py uninstall          # Remove scheduled tasks
```

## How It Works

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   3 PM Popup    │ ──── │  SQLite DB      │ ──── │    Jira API     │
│   (tkinter)     │      │  (time_log.db)  │      │   (worklogs)    │
└─────────────────┘      └─────────────────┘      └─────────────────┘
         │                        │
         │                        │
         ▼                        ▼
    Fill out form           Permanent backup
    Click submit            Streak tracking
```

- **All entries are saved locally first** (SQLite database)
- **Then synced to Jira** via the REST API
- **If sync fails**, entries stay in the DB and can be retried later
- **Streak tracking** counts consecutive weekdays with logged time

## Gamification

Your current streak is shown in the popup header:

| Streak | Badge |
|--------|-------|
| 5+ days | 🔥 |
| 10+ days | 🌟 |
| 20+ days | 🏆 |

The Friday summary shows your weekly stats and progress.

## Troubleshooting

### "Jira not configured" error
Make sure your `.env` file exists and contains all three variables:
```
JIRA_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your-api-token
```

### Entries not syncing to Jira
- Run `python sync_pending.py` to retry failed entries
- Check ticket IDs are valid (e.g., `DHI-1234` not `dhi1234`)
- Verify your API token at https://id.atlassian.com/manage-profile/security/api-tokens

### Popup not appearing at 3 PM
```bash
python setup.py status  # Check if tasks are installed
python setup.py run     # Test manually
```

If tasks exist but aren't running:
- Open Task Scheduler (`taskschd.msc`)
- Check the task history for errors
- Ensure Python is in your system PATH

### Want to change the popup time?
1. Open Task Scheduler (`taskschd.msc`)
2. Find "TimeLogger-Daily"
3. Edit the trigger to your preferred time

## Files

```
time-logger/
├── .env                 # Your Jira credentials (NEVER COMMIT)
├── .env.example         # Template for credentials
├── .gitignore           # Keeps secrets out of git
├── time_log.db          # SQLite database (auto-created)
├── time_logger.py       # Main GUI app
├── database.py          # Database operations
├── jira_sync.py         # Jira API integration
├── weekly_summary.py    # Weekly stats display
├── sync_pending.py      # Retry failed syncs
├── setup.py             # Task scheduler setup CLI
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Security

- **Credentials** are stored in `.env` which is git-ignored
- **API tokens** should have minimal required permissions
- **Local database** contains only ticket IDs, hours, and descriptions
- **No passwords or sensitive data** are stored in the database

## Contributing

Found a bug? Have an idea? Open an issue or PR!

## License

Internal use at Arcadia.
