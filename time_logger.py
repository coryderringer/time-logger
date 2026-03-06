"""
Time Logger - Daily time tracking popup application.
A tkinter GUI that helps you log time to Jira tickets.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Callable

import database
import jira_sync


class TimeEntryRow:
    """A single row in the time entry form."""
    
    def __init__(self, parent: tk.Frame, row_num: int, on_delete: Callable):
        self.parent = parent
        self.row_num = row_num
        self.on_delete = on_delete
        
        # Ticket ID
        self.ticket_var = tk.StringVar()
        self.ticket_entry = ttk.Entry(parent, textvariable=self.ticket_var, width=15)
        self.ticket_entry.grid(row=row_num, column=0, padx=2, pady=2, sticky="w")
        
        # Hours
        self.hours_var = tk.StringVar()
        self.hours_entry = ttk.Entry(parent, textvariable=self.hours_var, width=8)
        self.hours_entry.grid(row=row_num, column=1, padx=2, pady=2, sticky="w")
        
        # Description
        self.desc_var = tk.StringVar()
        self.desc_entry = ttk.Entry(parent, textvariable=self.desc_var, width=40)
        self.desc_entry.grid(row=row_num, column=2, padx=2, pady=2, sticky="we")
        
        # Delete button
        self.delete_btn = ttk.Button(parent, text="×", width=3, command=self._delete)
        self.delete_btn.grid(row=row_num, column=3, padx=2, pady=2)
    
    def _delete(self):
        self.on_delete(self)
    
    def destroy(self):
        self.ticket_entry.destroy()
        self.hours_entry.destroy()
        self.desc_entry.destroy()
        self.delete_btn.destroy()
    
    def get_data(self) -> dict | None:
        """Get the entry data, or None if row is empty/invalid."""
        ticket = self.ticket_var.get().strip().upper()
        hours_str = self.hours_var.get().strip()
        desc = self.desc_var.get().strip()
        
        if not ticket or not hours_str:
            return None
        
        try:
            hours = float(hours_str)
            if hours <= 0:
                return None
        except ValueError:
            return None
        
        return {
            'ticket_id': ticket,
            'hours': hours,
            'description': desc
        }
    
    def is_empty(self) -> bool:
        return not self.ticket_var.get().strip() and not self.hours_var.get().strip()


class TimeLoggerApp:
    """Main application window."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("⏱️ Time Logger")
        self.root.geometry("600x500")
        self.root.minsize(500, 400)
        
        # Make window stay on top initially
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        
        # Style configuration
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Streak.TLabel", font=("Segoe UI", 11))
        style.configure("Status.TLabel", font=("Segoe UI", 9))
        
        self.entry_rows: list[TimeEntryRow] = []
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        
        self._build_ui()
        self._add_entry_row()  # Start with one row
    
    def _build_ui(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header section
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(
            header_frame, 
            text="📋 Log Your Time", 
            style="Header.TLabel"
        ).pack(side=tk.LEFT)
        
        # Streak display
        streak = database.get_current_streak()
        streak_text = f"🔥 {streak} day streak!" if streak > 0 else "Start your streak today!"
        self.streak_label = ttk.Label(
            header_frame, 
            text=streak_text, 
            style="Streak.TLabel"
        )
        self.streak_label.pack(side=tk.RIGHT)
        
        # Date picker
        date_frame = ttk.Frame(main_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(date_frame, text="Date:").pack(side=tk.LEFT)
        date_entry = ttk.Entry(date_frame, textvariable=self.date_var, width=12)
        date_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        ttk.Button(
            date_frame, 
            text="Today", 
            command=lambda: self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
        ).pack(side=tk.LEFT)
        
        # Jira status
        ok, msg = jira_sync.check_credentials()
        status_text = "✓ Jira connected" if ok else "⚠️ Jira not configured"
        status_color = "green" if ok else "orange"
        self.jira_status = ttk.Label(date_frame, text=status_text, style="Status.TLabel")
        self.jira_status.pack(side=tk.RIGHT)
        
        # Column headers
        headers_frame = ttk.Frame(main_frame)
        headers_frame.pack(fill=tk.X)
        
        ttk.Label(headers_frame, text="Ticket ID", width=15).grid(row=0, column=0, sticky="w", padx=2)
        ttk.Label(headers_frame, text="Hours", width=8).grid(row=0, column=1, sticky="w", padx=2)
        ttk.Label(headers_frame, text="Description (optional)", width=40).grid(row=0, column=2, sticky="w", padx=2)
        ttk.Label(headers_frame, text="", width=3).grid(row=0, column=3)
        
        # Scrollable entry area
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        
        self.entries_frame = ttk.Frame(self.canvas)
        self.entries_frame.columnconfigure(2, weight=1)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.entries_frame, anchor="nw")
        
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.entries_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Add row button
        add_frame = ttk.Frame(main_frame)
        add_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            add_frame, 
            text="+ Add Another Entry", 
            command=self._add_entry_row
        ).pack(side=tk.LEFT)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(
            button_frame, 
            text="Save Locally", 
            command=self._save_entries
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame, 
            text="Save & Send to Jira", 
            command=self._save_and_sync
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            button_frame, 
            text="Cancel", 
            command=self.root.destroy
        ).pack(side=tk.RIGHT)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, style="Status.TLabel")
        status_bar.pack(fill=tk.X, pady=(10, 0))
    
    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _add_entry_row(self):
        row_num = len(self.entry_rows)
        row = TimeEntryRow(self.entries_frame, row_num, self._delete_entry_row)
        self.entry_rows.append(row)
        
        # Focus the new ticket field
        row.ticket_entry.focus_set()
    
    def _delete_entry_row(self, row: TimeEntryRow):
        if len(self.entry_rows) <= 1:
            # Don't delete the last row, just clear it
            row.ticket_var.set("")
            row.hours_var.set("")
            row.desc_var.set("")
            return
        
        row.destroy()
        self.entry_rows.remove(row)
        self._reindex_rows()
    
    def _reindex_rows(self):
        # Rebuild row positions after deletion
        for i, row in enumerate(self.entry_rows):
            row.ticket_entry.grid(row=i, column=0)
            row.hours_entry.grid(row=i, column=1)
            row.desc_entry.grid(row=i, column=2)
            row.delete_btn.grid(row=i, column=3)
            row.row_num = i
    
    def _get_valid_entries(self) -> list[dict]:
        """Get all valid entries from the form."""
        entries = []
        for row in self.entry_rows:
            data = row.get_data()
            if data:
                entries.append(data)
        return entries
    
    def _save_entries(self) -> list[int]:
        """Save entries to the local database."""
        entries = self._get_valid_entries()
        
        if not entries:
            messagebox.showwarning("No Entries", "Please enter at least one time entry.")
            return []
        
        date = self.date_var.get()
        
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter date in YYYY-MM-DD format.")
            return []
        
        saved_ids = []
        for entry in entries:
            entry_id = database.add_entry(
                date=date,
                ticket_id=entry['ticket_id'],
                hours=entry['hours'],
                description=entry['description']
            )
            saved_ids.append(entry_id)
        
        self.status_var.set(f"✓ Saved {len(saved_ids)} entries locally")
        
        # Update streak display
        streak = database.get_current_streak()
        streak_text = f"🔥 {streak} day streak!" if streak > 0 else "Start your streak today!"
        self.streak_label.config(text=streak_text)
        
        return saved_ids
    
    def _save_and_sync(self):
        """Save entries and immediately sync to Jira."""
        # First check Jira connection
        ok, msg = jira_sync.check_credentials()
        if not ok:
            messagebox.showerror(
                "Jira Not Configured", 
                "Please set up your Jira credentials in the .env file.\n\n" + msg
            )
            return
        
        ok, msg = jira_sync.test_connection()
        if not ok:
            messagebox.showerror("Jira Connection Failed", msg)
            return
        
        # Save to database
        saved_ids = self._save_entries()
        if not saved_ids:
            return
        
        # Get the entries we just saved
        entries = [e for e in database.get_unsent_entries() if e['id'] in saved_ids]
        
        # Sync to Jira
        self.status_var.set("Syncing to Jira...")
        self.root.update()
        
        results = jira_sync.sync_entries(entries)
        
        if results['failed'] == 0:
            self.status_var.set(f"✓ Synced {results['success']} entries to Jira!")
            messagebox.showinfo(
                "Success!", 
                f"Successfully logged {results['success']} time entries to Jira."
            )
            # Clear the form
            for row in self.entry_rows[1:]:
                row.destroy()
            self.entry_rows = self.entry_rows[:1]
            self.entry_rows[0].ticket_var.set("")
            self.entry_rows[0].hours_var.set("")
            self.entry_rows[0].desc_var.set("")
        else:
            error_msgs = "\n".join([
                f"• {e['ticket_id']}: {e['error']}" 
                for e in results['errors']
            ])
            messagebox.showwarning(
                "Partial Success",
                f"Synced {results['success']} entries.\n"
                f"Failed {results['failed']} entries:\n\n{error_msgs}\n\n"
                "Failed entries are saved locally and can be retried."
            )
            self.status_var.set(f"⚠️ {results['success']} synced, {results['failed']} failed")
    
    def run(self):
        """Start the application."""
        self.root.mainloop()


def main():
    """Entry point."""
    # Initialize database
    database.init_db()
    
    # Create and run the app
    app = TimeLoggerApp()
    app.run()


if __name__ == "__main__":
    main()
