"""
Database module for Time Logger.
Uses SQLite to store time entries and streak tracking.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Database file lives in the same directory as this script
DB_PATH = Path(__file__).parent / "time_log.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Time entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            hours REAL NOT NULL,
            description TEXT,
            sent_to_jira INTEGER DEFAULT 0,
            jira_worklog_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT
        )
    """)
    
    # Index for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(date)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_entries_sent ON entries(sent_to_jira)
    """)
    
    # Daily log tracking for streaks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (
            date TEXT PRIMARY KEY,
            logged_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Excused days (PTO, holidays) - don't break streaks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS excused_days (
            date TEXT PRIMARY KEY,
            reason TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


def add_entry(date: str, ticket_id: str, hours: float, description: str = "") -> int:
    """
    Add a new time entry.
    
    Args:
        date: Date string in YYYY-MM-DD format
        ticket_id: Jira ticket ID (e.g., "DHI-1234")
        hours: Hours worked (can be decimal, e.g., 1.5)
        description: Optional work description
    
    Returns:
        The ID of the newly created entry
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO entries (date, ticket_id, hours, description)
        VALUES (?, ?, ?, ?)
    """, (date, ticket_id.upper().strip(), hours, description.strip()))
    
    entry_id = cursor.lastrowid
    
    # Also mark this date as logged (for streak tracking)
    cursor.execute("""
        INSERT OR IGNORE INTO daily_logs (date) VALUES (?)
    """, (date,))
    
    conn.commit()
    conn.close()
    
    return entry_id


def get_entries_for_date(date: str) -> list[dict]:
    """Get all entries for a specific date."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM entries WHERE date = ? ORDER BY created_at
    """, (date,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_unsent_entries() -> list[dict]:
    """Get all entries that haven't been sent to Jira yet."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM entries WHERE sent_to_jira = 0 ORDER BY date, created_at
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def mark_entry_sent(entry_id: int, worklog_id: str = None):
    """Mark an entry as successfully sent to Jira."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE entries 
        SET sent_to_jira = 1, 
            jira_worklog_id = ?,
            sent_at = ?
        WHERE id = ?
    """, (worklog_id, datetime.now().isoformat(), entry_id))
    
    conn.commit()
    conn.close()


def delete_entry(entry_id: int):
    """Delete an entry by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    
    conn.commit()
    conn.close()


def add_excused_day(date: str, reason: str):
    """
    Mark a day as excused (PTO, holiday, etc.) so it doesn't break streaks.
    
    Args:
        date: Date string in YYYY-MM-DD format
        reason: One of 'PTO', 'Holiday', or custom reason
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO excused_days (date, reason) VALUES (?, ?)
    """, (date, reason))
    
    conn.commit()
    conn.close()


def get_excused_days() -> set[str]:
    """Get all excused dates as a set of date strings."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT date FROM excused_days")
    rows = cursor.fetchall()
    conn.close()
    
    return set(row['date'] for row in rows)


def get_missed_days() -> list[str]:
    """
    Get weekdays between last logged day and today that aren't logged or excused.
    These are days that would break the streak.
    
    Returns:
        List of date strings (YYYY-MM-DD) for missed days, oldest first
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get logged dates
    cursor.execute("SELECT date FROM daily_logs ORDER BY date DESC")
    logged_rows = cursor.fetchall()
    
    # Get excused dates
    cursor.execute("SELECT date FROM excused_days")
    excused_rows = cursor.fetchall()
    
    conn.close()
    
    logged_dates = set(row['date'] for row in logged_rows)
    excused_dates = set(row['date'] for row in excused_rows)
    
    if not logged_rows:
        return []  # No history yet, nothing is "missed"
    
    # Find the most recent logged date
    last_logged = max(logged_dates)
    last_logged_date = datetime.strptime(last_logged, "%Y-%m-%d").date()
    
    # Check each weekday between last logged and today
    missed = []
    current_date = last_logged_date + timedelta(days=1)
    today = datetime.now().date()
    
    while current_date < today:  # Don't include today - they might log later
        date_str = current_date.strftime("%Y-%m-%d")
        weekday = current_date.weekday()
        
        # Only count weekdays that aren't logged or excused
        if weekday < 5:  # Monday-Friday
            if date_str not in logged_dates and date_str not in excused_dates:
                missed.append(date_str)
        
        current_date += timedelta(days=1)
    
    return missed


def get_current_streak() -> int:
    """
    Calculate the current logging streak.
    A streak is consecutive days (excluding weekends and excused days) with logged time.
    
    Returns:
        Number of consecutive days in the current streak
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT date FROM daily_logs ORDER BY date DESC")
    logged_rows = cursor.fetchall()
    
    cursor.execute("SELECT date FROM excused_days")
    excused_rows = cursor.fetchall()
    
    conn.close()
    
    if not logged_rows:
        return 0
    
    logged_dates = set(row['date'] for row in logged_rows)
    excused_dates = set(row['date'] for row in excused_rows)
    
    # Start from today and count backwards
    streak = 0
    current_date = datetime.now().date()
    
    while True:
        date_str = current_date.strftime("%Y-%m-%d")
        weekday = current_date.weekday()
        
        # Skip weekends (Saturday=5, Sunday=6)
        if weekday >= 5:
            current_date -= timedelta(days=1)
            continue
        
        # Skip excused days (PTO, holidays)
        if date_str in excused_dates:
            current_date -= timedelta(days=1)
            continue
        
        if date_str in logged_dates:
            streak += 1
            current_date -= timedelta(days=1)
        else:
            # Allow for "today not logged yet" case
            if streak == 0 and current_date == datetime.now().date():
                current_date -= timedelta(days=1)
                continue
            break
    
    return streak


def get_week_stats(weeks_back: int = 0) -> dict:
    """
    Get statistics for a specific week.
    
    Args:
        weeks_back: 0 for current week, 1 for last week, etc.
    
    Returns:
        Dictionary with days_logged, total_hours, and entries_count
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate week boundaries (Monday to Sunday)
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday() + (7 * weeks_back))
    end_of_week = start_of_week + timedelta(days=6)
    
    start_str = start_of_week.strftime("%Y-%m-%d")
    end_str = end_of_week.strftime("%Y-%m-%d")
    
    # Get unique days logged
    cursor.execute("""
        SELECT COUNT(DISTINCT date) as days_logged
        FROM daily_logs 
        WHERE date BETWEEN ? AND ?
    """, (start_str, end_str))
    days_logged = cursor.fetchone()['days_logged']
    
    # Get total hours and entry count
    cursor.execute("""
        SELECT 
            COALESCE(SUM(hours), 0) as total_hours,
            COUNT(*) as entries_count
        FROM entries 
        WHERE date BETWEEN ? AND ?
    """, (start_str, end_str))
    
    row = cursor.fetchone()
    conn.close()
    
    return {
        'week_start': start_str,
        'week_end': end_str,
        'days_logged': days_logged,
        'total_hours': row['total_hours'],
        'entries_count': row['entries_count']
    }


def get_month_stats(year: int = None, month: int = None) -> dict:
    """Get statistics for a specific month."""
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month
    
    conn = get_connection()
    cursor = conn.cursor()
    
    month_str = f"{year}-{month:02d}"
    
    cursor.execute("""
        SELECT COUNT(DISTINCT date) as days_logged
        FROM daily_logs 
        WHERE date LIKE ?
    """, (f"{month_str}%",))
    days_logged = cursor.fetchone()['days_logged']
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(hours), 0) as total_hours,
            COUNT(*) as entries_count
        FROM entries 
        WHERE date LIKE ?
    """, (f"{month_str}%",))
    
    row = cursor.fetchone()
    conn.close()
    
    return {
        'month': month_str,
        'days_logged': days_logged,
        'total_hours': row['total_hours'],
        'entries_count': row['entries_count']
    }


# Initialize the database when this module is imported
init_db()


if __name__ == "__main__":
    # Quick test
    print("Database initialized at:", DB_PATH)
    print("Current streak:", get_current_streak())
    print("This week stats:", get_week_stats())
