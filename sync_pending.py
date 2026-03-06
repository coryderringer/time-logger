"""
Sync Pending Entries - Send all unsent entries to Jira.
Useful for catching up if previous syncs failed.
"""

import database
import jira_sync


def main():
    """Sync all pending entries to Jira."""
    print("=" * 50)
    print("🔄 SYNCING PENDING ENTRIES TO JIRA")
    print("=" * 50)
    
    # Check connection first
    ok, msg = jira_sync.check_credentials()
    if not ok:
        print(f"\n❌ {msg}")
        print("\nPlease configure your .env file.")
        return
    
    ok, msg = jira_sync.test_connection()
    if not ok:
        print(f"\n❌ Connection failed: {msg}")
        return
    
    print(f"✓ {msg}")
    
    # Get pending entries
    entries = database.get_unsent_entries()
    
    if not entries:
        print("\n✓ No pending entries to sync!")
        return
    
    print(f"\nFound {len(entries)} pending entries:")
    for entry in entries:
        print(f"  • {entry['date']} | {entry['ticket_id']} | {entry['hours']}h")
    
    print("\nSyncing...")
    
    def progress_callback(entry_id, success, message):
        status = "✓" if success else "❌"
        print(f"  {status} {message}")
    
    results = jira_sync.sync_entries(entries, callback=progress_callback)
    
    print("\n" + "=" * 50)
    print(f"✓ Synced: {results['success']}")
    print(f"❌ Failed: {results['failed']}")
    
    if results['errors']:
        print("\nFailed entries (will retry next time):")
        for error in results['errors']:
            print(f"  • {error['ticket_id']}: {error['error']}")


if __name__ == "__main__":
    main()
