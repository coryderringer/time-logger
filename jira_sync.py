"""
Jira synchronization module for Time Logger.
Sends time entries to Jira as worklogs.
"""

import os
import sys
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get credentials from environment
JIRA_URL = os.getenv('JIRA_URL')
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')


def check_credentials() -> tuple[bool, str]:
    """
    Check if all required credentials are configured.
    
    Returns:
        Tuple of (success, message)
    """
    missing = []
    if not JIRA_URL:
        missing.append("JIRA_URL")
    if not JIRA_EMAIL:
        missing.append("JIRA_EMAIL")
    if not JIRA_API_TOKEN:
        missing.append("JIRA_API_TOKEN")
    
    if missing:
        return False, f"Missing environment variables: {', '.join(missing)}"
    
    return True, "All credentials configured"


def get_jira_client():
    """
    Get an authenticated Jira client.
    
    Returns:
        Jira client instance, or None if credentials are missing
    """
    try:
        from atlassian import Jira
    except ImportError:
        print("Error: atlassian-python-api not installed.")
        print("Run: pip install atlassian-python-api")
        return None
    
    ok, msg = check_credentials()
    if not ok:
        print(f"Error: {msg}")
        print("Please create a .env file with your Jira credentials.")
        print("See .env.example for the required format.")
        return None
    
    return Jira(
        url=JIRA_URL,
        username=JIRA_EMAIL,
        password=JIRA_API_TOKEN,
        cloud=True
    )


def test_connection() -> tuple[bool, str]:
    """
    Test the Jira connection.
    
    Returns:
        Tuple of (success, message)
    """
    jira = get_jira_client()
    if not jira:
        return False, "Could not create Jira client"
    
    try:
        myself = jira.myself()
        name = myself.get('displayName', 'Unknown')
        return True, f"Connected as: {name}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def add_worklog(
    ticket_id: str,
    hours: float,
    date: str,
    description: str = ""
) -> tuple[bool, str, Optional[str]]:
    """
    Add a worklog entry to a Jira ticket.
    
    Args:
        ticket_id: The Jira issue key (e.g., "DHI-1234")
        hours: Hours worked (decimal allowed)
        date: Date of work in YYYY-MM-DD format
        description: Optional description of work done
    
    Returns:
        Tuple of (success, message, worklog_id)
    """
    jira = get_jira_client()
    if not jira:
        return False, "Could not create Jira client", None
    
    # Convert hours to seconds (Jira uses seconds for time)
    time_spent_seconds = int(hours * 3600)
    
    # Format the start date/time for Jira
    # Jira expects ISO 8601 format with timezone
    started = f"{date}T09:00:00.000+0000"
    
    try:
        # Check if issue exists first
        try:
            issue = jira.issue(ticket_id)
        except Exception as e:
            return False, f"Ticket {ticket_id} not found: {str(e)}", None
        
        # Add the worklog
        # Using the REST API directly for more control
        worklog_data = {
            "timeSpentSeconds": time_spent_seconds,
            "started": started,
        }
        
        if description:
            # Jira Cloud uses ADF (Atlassian Document Format) for comments
            worklog_data["comment"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            }
        
        # POST to the worklog endpoint
        result = jira.post(
            f"rest/api/3/issue/{ticket_id}/worklog",
            data=worklog_data
        )
        
        worklog_id = result.get('id', 'unknown')
        hours_str = f"{hours:.1f}h" if hours != int(hours) else f"{int(hours)}h"
        
        return True, f"Added {hours_str} to {ticket_id}", worklog_id
        
    except Exception as e:
        return False, f"Failed to add worklog: {str(e)}", None


def sync_entries(entries: list[dict], callback=None) -> dict:
    """
    Sync a list of time entries to Jira.
    
    Args:
        entries: List of entry dicts from the database
        callback: Optional function to call with progress updates
                  callback(entry_id, success, message)
    
    Returns:
        Dictionary with 'success', 'failed', and 'errors' counts
    """
    from database import mark_entry_sent
    
    results = {
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    for entry in entries:
        success, message, worklog_id = add_worklog(
            ticket_id=entry['ticket_id'],
            hours=entry['hours'],
            date=entry['date'],
            description=entry.get('description', '')
        )
        
        if success:
            mark_entry_sent(entry['id'], worklog_id)
            results['success'] += 1
        else:
            results['failed'] += 1
            results['errors'].append({
                'entry_id': entry['id'],
                'ticket_id': entry['ticket_id'],
                'error': message
            })
        
        if callback:
            callback(entry['id'], success, message)
    
    return results


def sync_all_pending(callback=None) -> dict:
    """
    Sync all pending (unsent) entries to Jira.
    
    Args:
        callback: Optional progress callback function
    
    Returns:
        Results dictionary
    """
    from database import get_unsent_entries
    
    entries = get_unsent_entries()
    
    if not entries:
        return {'success': 0, 'failed': 0, 'errors': [], 'message': 'No pending entries'}
    
    return sync_entries(entries, callback)


if __name__ == "__main__":
    # Test the connection
    print("Testing Jira connection...")
    print("-" * 40)
    
    ok, msg = check_credentials()
    print(f"Credentials: {msg}")
    
    if ok:
        ok, msg = test_connection()
        print(f"Connection: {msg}")
        
        if ok:
            print("\n✓ Jira integration is working!")
            print("\nTo test adding a worklog, run:")
            print("  from jira_sync import add_worklog")
            print("  add_worklog('TICKET-123', 1.5, '2026-03-05', 'Test entry')")
    else:
        print("\nPlease create a .env file with your credentials.")
        print("Copy .env.example to .env and fill in your values.")
