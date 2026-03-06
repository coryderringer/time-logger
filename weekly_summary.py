"""
Weekly Summary - Shows time logging stats for the week.
Can be run manually or scheduled for Fridays.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime

import database


class WeeklySummaryWindow:
    """A popup showing weekly stats and streak info."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("📊 Weekly Time Summary")
        self.root.geometry("450x400")
        self.root.resizable(False, False)
        
        # Keep on top briefly
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        
        self._build_ui()
    
    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = ttk.Label(
            main_frame, 
            text="📊 Your Week in Review",
            font=("Segoe UI", 16, "bold")
        )
        header.pack(pady=(0, 20))
        
        # Current streak (big and prominent)
        streak = database.get_current_streak()
        streak_frame = ttk.Frame(main_frame)
        streak_frame.pack(fill=tk.X, pady=10)
        
        if streak > 0:
            streak_emoji = "🔥" if streak >= 5 else "✨"
            streak_text = f"{streak_emoji} {streak} Day Streak!"
            if streak >= 20:
                streak_text += " 🏆"
            elif streak >= 10:
                streak_text += " 🌟"
            elif streak >= 5:
                streak_text += " 💪"
        else:
            streak_text = "No current streak - start one today!"
        
        ttk.Label(
            streak_frame, 
            text=streak_text,
            font=("Segoe UI", 14, "bold")
        ).pack()
        
        # Divider
        ttk.Separator(main_frame, orient="horizontal").pack(fill=tk.X, pady=15)
        
        # This week's stats
        week_stats = database.get_week_stats(weeks_back=0)
        
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(
            stats_frame, 
            text="This Week",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w")
        
        ttk.Label(
            stats_frame,
            text=f"📅 Days logged: {week_stats['days_logged']} / 5",
            font=("Segoe UI", 10)
        ).pack(anchor="w", pady=2)
        
        ttk.Label(
            stats_frame,
            text=f"⏱️ Total hours: {week_stats['total_hours']:.1f}",
            font=("Segoe UI", 10)
        ).pack(anchor="w", pady=2)
        
        ttk.Label(
            stats_frame,
            text=f"📝 Entries: {week_stats['entries_count']}",
            font=("Segoe UI", 10)
        ).pack(anchor="w", pady=2)
        
        # Progress bar for days logged
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        progress = min(week_stats['days_logged'] / 5 * 100, 100)
        progress_bar = ttk.Progressbar(
            progress_frame, 
            value=progress, 
            length=300,
            mode='determinate'
        )
        progress_bar.pack()
        
        # Last week comparison
        last_week_stats = database.get_week_stats(weeks_back=1)
        
        if last_week_stats['days_logged'] > 0:
            ttk.Separator(main_frame, orient="horizontal").pack(fill=tk.X, pady=15)
            
            compare_frame = ttk.Frame(main_frame)
            compare_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(
                compare_frame, 
                text="Last Week",
                font=("Segoe UI", 11, "bold")
            ).pack(anchor="w")
            
            ttk.Label(
                compare_frame,
                text=f"Days: {last_week_stats['days_logged']} | Hours: {last_week_stats['total_hours']:.1f} | Entries: {last_week_stats['entries_count']}",
                font=("Segoe UI", 9)
            ).pack(anchor="w", pady=2)
        
        # Month stats
        month_stats = database.get_month_stats()
        
        ttk.Separator(main_frame, orient="horizontal").pack(fill=tk.X, pady=15)
        
        month_frame = ttk.Frame(main_frame)
        month_frame.pack(fill=tk.X, pady=5)
        
        month_name = datetime.now().strftime("%B %Y")
        ttk.Label(
            month_frame, 
            text=f"📆 {month_name}",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        
        ttk.Label(
            month_frame,
            text=f"Days: {month_stats['days_logged']} | Hours: {month_stats['total_hours']:.1f} | Entries: {month_stats['entries_count']}",
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=2)
        
        # Close button
        ttk.Button(
            main_frame, 
            text="Got it! 👍", 
            command=self.root.destroy
        ).pack(pady=(20, 0))
    
    def run(self):
        self.root.mainloop()


def print_summary():
    """Print summary to console (for non-GUI usage)."""
    streak = database.get_current_streak()
    week_stats = database.get_week_stats()
    month_stats = database.get_month_stats()
    
    print("=" * 50)
    print("📊 TIME LOGGING SUMMARY")
    print("=" * 50)
    
    print(f"\n🔥 Current Streak: {streak} days")
    
    print(f"\n📅 This Week ({week_stats['week_start']} to {week_stats['week_end']})")
    print(f"   Days logged: {week_stats['days_logged']} / 5")
    print(f"   Total hours: {week_stats['total_hours']:.1f}")
    print(f"   Entries: {week_stats['entries_count']}")
    
    print(f"\n📆 This Month ({month_stats['month']})")
    print(f"   Days logged: {month_stats['days_logged']}")
    print(f"   Total hours: {month_stats['total_hours']:.1f}")
    print(f"   Entries: {month_stats['entries_count']}")
    
    print("=" * 50)


def main():
    """Show the weekly summary window."""
    import sys
    
    if "--console" in sys.argv:
        print_summary()
    else:
        app = WeeklySummaryWindow()
        app.run()


if __name__ == "__main__":
    main()
