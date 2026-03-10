"""
Time Logger - Daily time tracking popup application.
A tkinter GUI that helps you log time to Jira tickets.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Callable, Optional, List, Dict
import sys

import database
import jira_sync


def flash_window(hwnd, count=5):
    """Flash the taskbar icon to grab attention (Windows only)."""
    if sys.platform != "win32":
        return
    
    try:
        import ctypes
        from ctypes import wintypes
        
        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.UINT),
                ('hwnd', wintypes.HWND),
                ('dwFlags', wintypes.DWORD),
                ('uCount', wintypes.UINT),
                ('dwTimeout', wintypes.DWORD),
            ]
        
        FLASHW_ALL = 0x03
        FLASHW_TIMERNOFG = 0x0C
        
        fw = FLASHWINFO()
        fw.cbSize = ctypes.sizeof(FLASHWINFO)
        fw.hwnd = hwnd
        fw.dwFlags = FLASHW_ALL | FLASHW_TIMERNOFG
        fw.uCount = count
        fw.dwTimeout = 0
        
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(fw))
    except Exception:
        pass  # Fail silently if flashing doesn't work


class MissedDaysDialog:
    """Dialog shown when there are missed days that would break the streak."""
    
    def __init__(self, parent, missed_days: List[str]):
        self.result = None  # Will be 'pto', 'holiday', 'reset', or 'cancel'
        self.missed_days = missed_days
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Missed Days Detected")
        self.dialog.geometry("450x350")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center on parent
        self.dialog.geometry(f"+{parent.winfo_x() + 50}+{parent.winfo_y() + 50}")
        
        self._build_ui()
    
    def _build_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        ttk.Label(
            main_frame,
            text="📅 Missed Days Detected",
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(0, 10))
        
        # Explanation
        days_text = ", ".join(self.missed_days) if len(self.missed_days) <= 3 else \
            f"{self.missed_days[0]} ... {self.missed_days[-1]} ({len(self.missed_days)} days)"
        
        ttk.Label(
            main_frame,
            text=f"You haven't logged time for:\n{days_text}",
            font=("Segoe UI", 10),
            justify=tk.CENTER
        ).pack(pady=(0, 15))
        
        ttk.Label(
            main_frame,
            text="Was this time off, or did you forget to log?",
            font=("Segoe UI", 10)
        ).pack(pady=(0, 15))
        
        # Buttons frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            btn_frame,
            text="🏖️ PTO / Vacation",
            command=lambda: self._select('pto'),
            width=20
        ).pack(pady=5)
        
        ttk.Button(
            btn_frame,
            text="🎉 Company Holiday",
            command=lambda: self._select('holiday'),
            width=20
        ).pack(pady=5)
        
        ttk.Button(
            btn_frame,
            text="😅 I Forgot - Reset Streak",
            command=lambda: self._select('reset'),
            width=20
        ).pack(pady=5)
        
        ttk.Button(
            btn_frame,
            text="Ask Me Later",
            command=lambda: self._select('cancel'),
            width=20
        ).pack(pady=5)
        
        # Info text
        ttk.Label(
            main_frame,
            text="(PTO/Holiday will preserve your streak)",
            font=("Segoe UI", 8),
            foreground="gray"
        ).pack(pady=(10, 0))
    
    def _select(self, choice: str):
        self.result = choice
        self.dialog.destroy()
    
    def show(self) -> str:
        """Show the dialog and return the user's choice."""
        self.dialog.wait_window()
        return self.result


class TimeEntryRow:
    """A single row in the time entry form."""
    
    def __init__(self, parent: tk.Frame, row_num: int, on_delete: Callable, on_save_ticket: Callable):
        self.parent = parent
        self.row_num = row_num
        self.on_delete = on_delete
        self.on_save_ticket = on_save_ticket
        
        # Ticket ID (combobox with saved tickets)
        self.ticket_var = tk.StringVar()
        self.ticket_combo = ttk.Combobox(parent, textvariable=self.ticket_var, width=18)
        self.ticket_combo.grid(row=row_num, column=0, padx=2, pady=2, sticky="w")
        self.refresh_saved_tickets()
        
        # Bind selection to extract ticket ID from "Nickname (DHI-1234)" format
        self.ticket_combo.bind('<<ComboboxSelected>>', self._on_ticket_selected)
        
        # Save ticket button (star)
        self.save_btn = ttk.Button(parent, text="☆", width=2, command=self._save_ticket)
        self.save_btn.grid(row=row_num, column=1, padx=1, pady=2)
        
        # Hours
        self.hours_var = tk.StringVar()
        self.hours_entry = ttk.Entry(parent, textvariable=self.hours_var, width=8)
        self.hours_entry.grid(row=row_num, column=2, padx=2, pady=2, sticky="w")
        
        # Description
        self.desc_var = tk.StringVar()
        self.desc_entry = ttk.Entry(parent, textvariable=self.desc_var, width=35)
        self.desc_entry.grid(row=row_num, column=3, padx=2, pady=2, sticky="we")
        
        # Delete button
        self.delete_btn = ttk.Button(parent, text="×", width=3, command=self._delete)
        self.delete_btn.grid(row=row_num, column=4, padx=2, pady=2)
    
    def _delete(self):
        self.on_delete(self)
    
    def _save_ticket(self):
        """Save the current ticket for quick selection."""
        ticket_id = self._extract_ticket_id(self.ticket_var.get())
        if ticket_id:
            self.on_save_ticket(ticket_id)
    
    def _on_ticket_selected(self, event):
        """When a saved ticket is selected, extract just the ticket ID."""
        selected = self.ticket_var.get()
        ticket_id = self._extract_ticket_id(selected)
        if ticket_id != selected:
            self.ticket_var.set(ticket_id)
    
    def _extract_ticket_id(self, value: str) -> str:
        """Extract ticket ID from 'Nickname (DHI-1234)' format or return as-is."""
        value = value.strip()
        if '(' in value and value.endswith(')'):
            # Extract ID from "Nickname (DHI-1234)" format
            start = value.rfind('(') + 1
            end = value.rfind(')')
            return value[start:end].strip()
        return value.upper()
    
    def refresh_saved_tickets(self):
        """Refresh the dropdown with saved tickets."""
        saved = database.get_saved_tickets()
        # Format: "Nickname (DHI-1234)"
        values = [f"{t['nickname']} ({t['ticket_id']})" for t in saved]
        self.ticket_combo['values'] = values
    
    def destroy(self):
        self.ticket_combo.destroy()
        self.save_btn.destroy()
        self.hours_entry.destroy()
        self.desc_entry.destroy()
        self.delete_btn.destroy()
    
    def get_data(self) -> Optional[Dict]:
        """Get the entry data, or None if row is empty/invalid."""
        raw_ticket = self.ticket_var.get().strip()
        ticket = self._extract_ticket_id(raw_ticket)
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
        
        # Update last_used for saved tickets
        database.update_ticket_last_used(ticket)
        
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
        self.root.geometry("620x520")
        self.root.minsize(520, 420)
        
        # Make window AGGRESSIVELY visible
        self.root.attributes('-topmost', True)
        self.root.lift()
        self.root.focus_force()
        
        # Flash the taskbar to get attention
        self._flash_window()
        
        # Stay on top for 3 seconds, then allow other windows
        self.root.after(3000, lambda: self.root.attributes('-topmost', False))
        
        # Style configuration
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Streak.TLabel", font=("Segoe UI", 11))
        style.configure("Status.TLabel", font=("Segoe UI", 9))
        
        self.entry_rows = []  # List of TimeEntryRow
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        
        self._build_ui()
        self._add_entry_row()  # Start with one row
        
        # Check for missed days after UI is built
        self.root.after(100, self._check_missed_days)
    
    def _flash_window(self):
        """Flash the taskbar icon to grab attention."""
        try:
            # Get the window handle (HWND) from tkinter
            hwnd = int(self.root.wm_frame(), 16)
            flash_window(hwnd, count=5)
        except Exception:
            pass  # Fail silently
    
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
        
        # Column headers (aligned with entry row columns)
        headers_frame = ttk.Frame(main_frame)
        headers_frame.pack(fill=tk.X)
        
        ttk.Label(headers_frame, text="Ticket ID", width=21).grid(row=0, column=0, sticky="w", padx=2)
        ttk.Label(headers_frame, text="", width=3).grid(row=0, column=1, padx=1)  # Star button column
        ttk.Label(headers_frame, text="Hours", width=8).grid(row=0, column=2, sticky="w", padx=2)
        ttk.Label(headers_frame, text="Description (optional)", width=35).grid(row=0, column=3, sticky="w", padx=2)
        ttk.Label(headers_frame, text="", width=3).grid(row=0, column=4)
        
        # Scrollable entry area
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        
        self.entries_frame = ttk.Frame(self.canvas)
        self.entries_frame.columnconfigure(3, weight=1)  # Description column expands
        
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
        
        ttk.Button(
            add_frame,
            text="⚙ Manage Saved Tickets",
            command=self._manage_saved_tickets
        ).pack(side=tk.RIGHT)
        
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
        
        # Status bar (with extra bottom padding to prevent cutoff)
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, style="Status.TLabel")
        status_bar.pack(fill=tk.X, pady=(10, 10))
    
    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _add_entry_row(self):
        row_num = len(self.entry_rows)
        row = TimeEntryRow(self.entries_frame, row_num, self._delete_entry_row, self._save_ticket_dialog)
        self.entry_rows.append(row)
        
        # Focus the new ticket field
        row.ticket_combo.focus_set()
    
    def _save_ticket_dialog(self, ticket_id: str):
        """Show dialog to save a ticket with a nickname."""
        if not ticket_id:
            messagebox.showwarning("No Ticket", "Enter a ticket ID first, then click the star to save it.")
            return
        
        # Simple dialog for nickname
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Ticket")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Save {ticket_id} with nickname:").pack(pady=(15, 5))
        
        nickname_var = tk.StringVar()
        nickname_entry = ttk.Entry(dialog, textvariable=nickname_var, width=25)
        nickname_entry.pack(pady=5)
        nickname_entry.focus_set()
        
        def save():
            nickname = nickname_var.get().strip()
            if nickname:
                database.save_ticket(ticket_id, nickname)
                # Refresh all row dropdowns
                for row in self.entry_rows:
                    row.refresh_saved_tickets()
                dialog.destroy()
                messagebox.showinfo("Saved!", f"Saved '{nickname}' ({ticket_id}) for quick access.")
            else:
                messagebox.showwarning("No Nickname", "Please enter a nickname for this ticket.")
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Allow Enter to save
        nickname_entry.bind('<Return>', lambda e: save())
    
    def _manage_saved_tickets(self):
        """Open dialog to manage (view/delete) saved tickets."""
        saved = database.get_saved_tickets()
        
        if not saved:
            messagebox.showinfo("No Saved Tickets", "You haven't saved any tickets yet.\n\nTo save a ticket, enter a ticket ID and click the ☆ star button.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Saved Tickets")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Saved Tickets", font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))
        
        # Scrollable list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        tickets_frame = ttk.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        canvas_window = canvas.create_window((0, 0), window=tickets_frame, anchor="nw")
        
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        
        tickets_frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        
        def refresh_list():
            # Clear existing items
            for widget in tickets_frame.winfo_children():
                widget.destroy()
            
            current_saved = database.get_saved_tickets()
            
            if not current_saved:
                dialog.destroy()
                return
            
            for ticket in current_saved:
                row = ttk.Frame(tickets_frame)
                row.pack(fill=tk.X, pady=2)
                
                ttk.Label(
                    row, 
                    text=f"{ticket['nickname']} ({ticket['ticket_id']})",
                    width=35
                ).pack(side=tk.LEFT, padx=5)
                
                def make_delete(tid=ticket['ticket_id'], nick=ticket['nickname']):
                    def delete():
                        if messagebox.askyesno("Delete?", f"Remove '{nick}' from saved tickets?"):
                            database.delete_saved_ticket(tid)
                            # Refresh all dropdowns
                            for entry_row in self.entry_rows:
                                entry_row.refresh_saved_tickets()
                            refresh_list()
                    return delete
                
                ttk.Button(row, text="🗑", width=3, command=make_delete()).pack(side=tk.RIGHT, padx=5)
        
        refresh_list()
        
        ttk.Button(main_frame, text="Done", command=dialog.destroy).pack(pady=(10, 0))
    
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
            row.ticket_combo.grid(row=i, column=0)
            row.save_btn.grid(row=i, column=1)
            row.hours_entry.grid(row=i, column=2)
            row.desc_entry.grid(row=i, column=3)
            row.delete_btn.grid(row=i, column=4)
            row.row_num = i
    
    def _check_missed_days(self):
        """Check for missed days and prompt user if streak would be broken."""
        missed = database.get_missed_days()
        
        if not missed:
            return  # No missed days, streak is intact!
        
        # Show dialog asking what to do
        dialog = MissedDaysDialog(self.root, missed)
        choice = dialog.show()
        
        if choice == 'pto':
            for date in missed:
                database.add_excused_day(date, 'PTO')
            self._update_streak_display()
            messagebox.showinfo(
                "Days Marked as PTO",
                f"Marked {len(missed)} day(s) as PTO.\nYour streak is preserved! 🎉"
            )
        
        elif choice == 'holiday':
            for date in missed:
                database.add_excused_day(date, 'Holiday')
            self._update_streak_display()
            messagebox.showinfo(
                "Days Marked as Holiday",
                f"Marked {len(missed)} day(s) as company holiday.\nYour streak is preserved! 🎉"
            )
        
        elif choice == 'reset':
            # Don't mark as excused - streak will naturally reset
            self._update_streak_display()
            messagebox.showinfo(
                "Streak Reset",
                "No worries! Start fresh today. 💪"
            )
        
        # 'cancel' - do nothing, ask again next time
    
    def _update_streak_display(self):
        """Refresh the streak label."""
        streak = database.get_current_streak()
        streak_text = f"🔥 {streak} day streak!" if streak > 0 else "Start your streak today!"
        self.streak_label.config(text=streak_text)
    
    def _get_valid_entries(self) -> List[Dict]:
        """Get all valid entries from the form."""
        entries = []
        for row in self.entry_rows:
            data = row.get_data()
            if data:
                entries.append(data)
        return entries
    
    def _save_entries(self) -> List[int]:
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
        self._update_streak_display()
        
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
