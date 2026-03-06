"""
Time Logger Setup Script
Run this to configure scheduled tasks for the time logger.

Usage:
    python setup.py install              - Create scheduled tasks (3pm daily, 4pm Friday)
    python setup.py install --time 4:30PM - Use a custom reminder time
    python setup.py uninstall            - Remove scheduled tasks
    python setup.py test                 - Test the Jira connection
    python setup.py status               - Show current task status
"""

import subprocess
import sys
import os
from pathlib import Path

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# Get the directory where this script lives
PROJECT_PATH = Path(__file__).parent.resolve()


def run_powershell(command: str, capture: bool = True) -> tuple[bool, str]:
    """Run a PowerShell command and return (success, output)."""
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=capture,
            text=True
        )
        output = result.stdout + result.stderr if capture else ""
        return result.returncode == 0, output.strip()
    except Exception as e:
        return False, str(e)


def get_pythonw_path():
    """Get the full path to pythonw.exe (or python.exe as fallback)."""
    import sys
    python_path = sys.executable
    
    # Try to find pythonw.exe in the same directory
    python_dir = Path(python_path).parent
    pythonw_path = python_dir / "pythonw.exe"
    
    if pythonw_path.exists():
        return str(pythonw_path)
    
    # For Microsoft Store Python, pythonw might be in a different location
    # Fall back to python.exe (will show console briefly)
    return python_path


def parse_time_arg():
    """Parse --time argument if provided, default to 3:00PM."""
    import re
    for i, arg in enumerate(sys.argv):
        if arg == "--time" and i + 1 < len(sys.argv):
            time_str = sys.argv[i + 1]
            # Validate format (e.g., 3:00PM, 4:30PM, 2:00PM)
            if re.match(r'^\d{1,2}:\d{2}(AM|PM)$', time_str, re.IGNORECASE):
                return time_str.upper()
            else:
                print(f"Invalid time format: {time_str}")
                print("Use format like: 3:00PM, 4:30PM, 10:00AM")
                sys.exit(1)
    return "3:00PM"


def install_tasks():
    """Create the scheduled tasks."""
    reminder_time = parse_time_arg()
    
    print("=" * 50)
    print("⏱️  TIME LOGGER - SETUP")
    print("=" * 50)
    print()
    print(f"Project path: {PROJECT_PATH}")
    print()
    
    # Get Python path
    python_exe = get_pythonw_path()
    print(f"Python executable: {python_exe}")
    print()
    
    # Check Python is available
    print("Checking Python installation...")
    ok, output = run_powershell("python --version")
    if ok:
        print(f"  ✓ {output}")
    else:
        print("  ⚠ Python not found in PATH - tasks may not run correctly")
    print()
    
    print("Creating scheduled tasks...")
    print()
    
    # Task 1: Daily reminder
    print(f"1. TimeLogger-Daily ({reminder_time}, Mon-Fri)")
    daily_cmd = f'''
$action = New-ScheduledTaskAction -Execute "{python_exe}" -Argument '"{PROJECT_PATH}\\time_logger.py"' -WorkingDirectory "{PROJECT_PATH}"
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At {reminder_time}
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "TimeLogger-Daily" -Action $action -Trigger $trigger -Settings $settings -Description "Opens the time logger popup" -Force | Out-Null
'''
    ok, output = run_powershell(daily_cmd)
    if ok:
        print("   ✓ Created successfully")
    else:
        print(f"   ✗ Failed: {output}")
    
    # Task 2: Weekly summary on Fridays
    print("2. TimeLogger-WeeklySummary (4:00 PM, Fridays)")
    weekly_cmd = f'''
$action = New-ScheduledTaskAction -Execute "{python_exe}" -Argument '"{PROJECT_PATH}\\weekly_summary.py"' -WorkingDirectory "{PROJECT_PATH}"
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Friday -At 4:00PM
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "TimeLogger-WeeklySummary" -Action $action -Trigger $trigger -Settings $settings -Description "Shows weekly summary" -Force | Out-Null
'''
    ok, output = run_powershell(weekly_cmd)
    if ok:
        print("   ✓ Created successfully")
    else:
        print(f"   ✗ Failed: {output}")
    
    print()
    print("=" * 50)
    print("✓ Setup complete!")
    print()
    print(f"The time logger will now pop up at {reminder_time} on weekdays.")
    print("You'll see a weekly summary at 4:00 PM on Fridays.")
    print()
    print("To test it now, run:")
    print("  python time_logger.py")
    print()
    print("To trigger the scheduled task manually:")
    print("  python setup.py run")
    print()


def uninstall_tasks():
    """Remove the scheduled tasks."""
    print("Removing scheduled tasks...")
    print()
    
    for task_name in ["TimeLogger-Daily", "TimeLogger-WeeklySummary"]:
        print(f"  Removing {task_name}...", end=" ")
        ok, output = run_powershell(
            f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false -ErrorAction SilentlyContinue"
        )
        print("✓ Done" if ok else "✓ Not found (already removed)")
    
    print()
    print("Scheduled tasks removed.")


def show_status():
    """Show the status of scheduled tasks."""
    print("Scheduled Task Status")
    print("=" * 50)
    print()
    
    for task_name in ["TimeLogger-Daily", "TimeLogger-WeeklySummary"]:
        ok, output = run_powershell(
            f"Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue | "
            f"Select-Object TaskName, State | Format-List"
        )
        if ok and output:
            # Parse the output
            print(f"📋 {task_name}")
            ok2, info = run_powershell(
                f"Get-ScheduledTaskInfo -TaskName '{task_name}' -ErrorAction SilentlyContinue | "
                f"Select-Object LastRunTime, NextRunTime | Format-List"
            )
            if ok2 and info:
                for line in info.split('\n'):
                    if line.strip():
                        print(f"   {line.strip()}")
            print()
        else:
            print(f"📋 {task_name}: Not installed")
            print()


def run_task():
    """Manually trigger the daily task."""
    print("Triggering TimeLogger-Daily task...")
    ok, output = run_powershell("Start-ScheduledTask -TaskName 'TimeLogger-Daily'")
    if ok:
        print("✓ Task triggered - popup should appear!")
    else:
        print(f"✗ Failed: {output}")
        print("\nTry running directly instead:")
        print("  python time_logger.py")


def test_connection():
    """Test the Jira connection."""
    print("Testing Jira connection...")
    print()
    
    # Import and test
    try:
        sys.path.insert(0, str(PROJECT_PATH))
        import jira_sync
        
        ok, msg = jira_sync.check_credentials()
        print(f"Credentials: {msg}")
        
        if ok:
            ok, msg = jira_sync.test_connection()
            print(f"Connection: {msg}")
            
            if ok:
                print()
                print("✓ Jira integration is working!")
        else:
            print()
            print("Please create a .env file with your credentials.")
            print("See .env.example for the format.")
    except Exception as e:
        print(f"Error: {e}")


def show_help():
    """Show usage information."""
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    commands = {
        'install': install_tasks,
        'uninstall': uninstall_tasks,
        'remove': uninstall_tasks,
        'status': show_status,
        'test': test_connection,
        'run': run_task,
        'help': show_help,
        '--help': show_help,
        '-h': show_help,
    }
    
    if command in commands:
        commands[command]()
    else:
        print(f"Unknown command: {command}")
        print()
        show_help()


if __name__ == "__main__":
    main()
