#!/usr/bin/env python3
"""
Shopify to WooCommerce Migration Tool - GUI Application
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import json
import os
from datetime import datetime
from migration_engine import MigrationEngine

class MigrationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Shopify to woo migration tool")
        self.root.geometry("1400x800")
        self.root.resizable(True, True)
        
        # Initialize migration engine
        self.migration_engine = MigrationEngine(
            progress_callback=self.update_progress,
            log_callback=self.add_log_message
        )
        
        # Track application state for smart exit confirmation
        self.migration_in_progress = False
        self.has_errors = False
        self.has_unsaved_changes = False
        self.last_saved_data = {}
        
        self.setup_ui()
        # Load .env file automatically on startup
        self.load_env_file()
        
        # Track initial state after loading
        self.update_saved_state()
        
        # Add change tracking to all input fields
        self.setup_change_tracking()
        
        # Run cleanup after a short delay to let logger initialization complete
        self.root.after(2000, self.cleanup_logs_on_startup)
        
    def setup_ui(self):
        """Set up the GUI layout"""
        # Configure root window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure main frame grid - left panel fixed width, right panel expands
        main_frame.columnconfigure(0, weight=0, minsize=520)  # Fixed width left panel
        main_frame.columnconfigure(1, weight=1)  # Expanding right panel
        main_frame.rowconfigure(0, weight=1)
        
        # Left panel for inputs and controls
        left_panel = ttk.Frame(main_frame)
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 5), pady=10)
        
        # Right panel for output
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 10), pady=10)
        
        self.setup_left_panel(left_panel)
        self.setup_right_panel(right_panel)
        
    def setup_left_panel(self, parent):
        """Set up the left panel with inputs and controls"""
        # Create StringVars
        self.shopify_url_var = tk.StringVar()
        self.shopify_token_var = tk.StringVar()
        self.wc_url_var = tk.StringVar()
        self.wc_key_var = tk.StringVar()
        self.wc_secret_var = tk.StringVar()
        self.wp_username_var = tk.StringVar()
        self.wp_password_var = tk.StringVar()
        
        # Field definitions
        fields = [
            ("Enter SHOPIFY STORE URL", self.shopify_url_var, False),
            ("Enter SHOPIFY ACCESS TOKEN", self.shopify_token_var, False),
            ("Enter WOOCOMMERCE URL", self.wc_url_var, False),
            ("Enter WOOCOMMERCE CONSUMER KEY", self.wc_key_var, False),
            ("Enter WOOCOMMERCE CONSUMER SECRET", self.wc_secret_var, False),
            ("Enter WORDPRESS USERNAME (Optional)", self.wp_username_var, False),
            ("Enter WORDPRESS APP PASSWORD (Optional)", self.wp_password_var, False)
        ]
        
        # Create labels and entry fields
        current_row = 0
        for i, (label_text, var, is_password) in enumerate(fields):
            # Label on the left
            label = ttk.Label(parent, text=label_text, anchor='w')
            label.grid(row=current_row, column=0, sticky=tk.W, pady=10, padx=(10, 5))
            
            # Entry field in the middle - no password masking
            entry = ttk.Entry(parent, textvariable=var, width=30)
            entry.grid(row=current_row, column=1, sticky=(tk.W, tk.E), pady=10, padx=5)
            
            current_row += 1
        
        # File operation buttons - positioned between the input fields (center-aligned vertically)
        # Using rowspan to center them between multiple rows
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=2, rowspan=3, sticky=(tk.N, tk.S), padx=(15, 10))
        
        # Center the buttons vertically within the frame
        button_frame.rowconfigure(0, weight=1)
        button_frame.rowconfigure(3, weight=1)
        
        save_btn = ttk.Button(button_frame, text="Save to file", command=self.save_credentials, width=15)
        save_btn.grid(row=1, column=0, pady=(0, 5), ipady=5)
        
        load_btn = ttk.Button(button_frame, text="Load from file", command=self.load_credentials, width=15)
        load_btn.grid(row=2, column=0, pady=(5, 0), ipady=5)
        
        # Action buttons - large and centered below input fields
        self.dry_run_btn = ttk.Button(parent, text="Dry run", command=self.run_dry_run)
        self.dry_run_btn.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), 
                              pady=(40, 10), padx=40, ipady=15)
        
        # Frame for migrate and stop buttons side by side
        migrate_frame = ttk.Frame(parent)
        migrate_frame.grid(row=current_row+1, column=0, columnspan=3, sticky=(tk.W, tk.E), 
                          pady=10, padx=40)
        migrate_frame.columnconfigure(0, weight=1)
        migrate_frame.columnconfigure(1, weight=0)
        
        self.migrate_btn = ttk.Button(migrate_frame, text="Migrate", command=self.run_migration)
        self.migrate_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), ipady=15)
        
        self.stop_btn = ttk.Button(migrate_frame, text="Stop", command=self.stop_migration, state='disabled')
        self.stop_btn.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), ipady=15)
        
        # Configure column weights
        parent.columnconfigure(0, weight=0, minsize=230)  # Label column
        parent.columnconfigure(1, weight=1)  # Entry column - expandable
        parent.columnconfigure(2, weight=0)  # Button column
        
    def setup_right_panel(self, parent):
        """Set up the right panel with output area"""
        # Output header with clear button
        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=(5, 5))
        header_frame.columnconfigure(0, weight=1)
        
        output_label = ttk.Label(header_frame, text="Output", font=('TkDefaultFont', 10, 'bold'))
        output_label.grid(row=0, column=0, sticky=tk.W)
        
        clear_button = ttk.Button(header_frame, text="Clear", command=self.clear_output)
        clear_button.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))
        
        # Output text area with scrollbar - black background like terminal
        text_frame = ttk.Frame(parent)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(0, 5))
        
        self.output_text = scrolledtext.ScrolledText(
            text_frame,
            bg='black',
            fg='white',
            font=('Consolas', 9),
            wrap=tk.WORD,
            insertbackground='white'
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure column and row weights for resizing
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # Add initial message
        self.add_log_message("Shopify to WooCommerce Migration Tool v1.0")
        self.add_log_message("Ready to start migration. Enter your credentials and click 'Dry run' to test.")
        self.add_log_message("-" * 60)
    
    def add_log_message(self, message):
        """Add a message to the output area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        # Check for errors in the message
        if any(keyword in message.upper() for keyword in ['ERROR', 'FAILED', 'EXCEPTION', 'CRITICAL']):
            self.has_errors = True
        
        # Run in main thread
        self.root.after(0, self._append_text, formatted_message)
        
    def _append_text(self, text):
        """Append text to output area (must run in main thread)"""
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
    
    def clear_output(self):
        """Clear the output area and reset error state"""
        self.output_text.delete(1.0, tk.END)
        self.has_errors = False
        self.add_log_message("Output cleared")
        self.root.update_idletasks()
    
    def update_progress(self, percentage, status=""):
        """Update the progress bar and status"""
        # This can be implemented if you add a progress bar to the UI
        pass
    
    def validate_inputs(self):
        """Validate that all required inputs are provided"""
        required_fields = [
            (self.shopify_url_var.get(), "Shopify Store URL"),
            (self.shopify_token_var.get(), "Shopify Access Token"),
            (self.wc_url_var.get(), "WooCommerce URL"),
            (self.wc_key_var.get(), "WooCommerce Consumer Key"),
            (self.wc_secret_var.get(), "WooCommerce Consumer Secret")
        ]
        
        missing_fields = [name for value, name in required_fields if not value.strip()]
        
        if missing_fields:
            messagebox.showerror("Missing Fields", f"Please fill in the following fields:\n- " + "\n- ".join(missing_fields))
            return False
            
        return True
    
    def disable_buttons(self):
        """Disable action buttons during migration"""
        self.dry_run_btn.config(state='disabled')
        self.migrate_btn.config(state='disabled')
        self.stop_btn.config(state='normal')  # Enable stop button
    
    def enable_buttons(self):
        """Enable action buttons after migration"""
        self.dry_run_btn.config(state='normal')
        self.migrate_btn.config(state='normal')
        self.stop_btn.config(state='disabled')  # Disable stop button
    
    def stop_migration(self):
        """Request migration to stop gracefully"""
        if self.migration_in_progress:
            self.migration_engine.stop_migration()
            self.add_log_message("STOP requested - migration will halt after current item...")
            self.stop_btn.config(state='disabled')  # Disable to prevent multiple clicks
    
    def run_dry_run(self):
        """Run migration in dry run mode"""
        if not self.validate_inputs():
            return
            
        self.add_log_message("Starting dry run...")
        self.disable_buttons()
        self.migration_in_progress = True
        self.has_errors = False  # Reset errors for new migration
        
        # Run in background thread
        thread = threading.Thread(target=self._run_migration_thread, args=(True,))
        thread.daemon = True
        thread.start()
    
    def run_migration(self):
        """Run actual migration"""
        if not self.validate_inputs():
            return
            
        # Confirm with user
        result = messagebox.askyesno(
            "Confirm Migration",
            "This will perform the actual migration and create data in your WooCommerce store.\n\n"
            "Are you sure you want to continue?"
        )
        
        if not result:
            return
            
        self.add_log_message("Starting live migration...")
        self.disable_buttons()
        self.migration_in_progress = True
        self.has_errors = False  # Reset errors for new migration
        
        # Run in background thread
        thread = threading.Thread(target=self._run_migration_thread, args=(False,))
        thread.daemon = True
        thread.start()
    
    def _run_migration_thread(self, dry_run=False):
        """Run migration in background thread"""
        try:
            # Connect to APIs
            wp_username = self.wp_username_var.get().strip() or None
            wp_password = self.wp_password_var.get().strip() or None
            
            success = self.migration_engine.connect_apis(
                self.shopify_url_var.get().strip(),
                self.shopify_token_var.get().strip(),
                self.wc_url_var.get().strip(),
                self.wc_key_var.get().strip(),
                self.wc_secret_var.get().strip(),
                wp_username,
                wp_password
            )
            
            if not success:
                self.add_log_message("Failed to connect to APIs. Please check your credentials.")
                self.root.after(0, self.enable_buttons)
                return
            
            # Run migration
            result = self.migration_engine.run_migration(dry_run)
            
            # Handle both old boolean and new dict return formats
            if isinstance(result, dict):
                success = result.get('success', False)
                has_errors = result.get('has_errors', False)
                has_failures = result.get('has_failures', False)
                report = result.get('report', {})
            else:
                # Backwards compatibility with boolean return
                success = result
                has_errors = False
                has_failures = False
                report = {}
            
            mode = "dry run" if dry_run else "migration"
            
            if not success:
                # Complete failure - migration crashed
                self.add_log_message(f"{mode.title()} failed. Check the logs for details.")
            elif has_errors or has_failures:
                # Completed but with errors/failures
                error_count = len(report.get('errors', []))
                total_failures = sum(
                    stats.get('failed', 0) 
                    for stats in report.values() 
                    if isinstance(stats, dict) and 'failed' in stats
                )
                self.add_log_message(f"{mode.title()} completed with errors!")
                if error_count > 0:
                    self.add_log_message(f"  - {error_count} error(s) logged")
                if total_failures > 0:
                    self.add_log_message(f"  - {total_failures} item(s) failed to migrate")
                self.add_log_message("  Check the output above for details.")
            else:
                # Complete success
                self.add_log_message(f"{mode.title()} completed successfully!")
                
        except Exception as e:
            self.add_log_message(f"Error during migration: {str(e)}")
            
        finally:
            # Re-enable buttons and update migration state
            self.migration_in_progress = False
            self.root.after(0, self.enable_buttons)
            
            # Clean up any empty log files that might have been created
            self.root.after(2000, self.cleanup_logs_on_startup)  # Delay to let file operations complete
    
    def save_credentials(self):
        """Save credentials to .env file"""
        if not any([
            self.shopify_url_var.get().strip(),
            self.shopify_token_var.get().strip(),
            self.wc_url_var.get().strip(),
            self.wc_key_var.get().strip(),
            self.wc_secret_var.get().strip()
        ]):
            messagebox.showwarning("No Data", "No credentials to save.")
            return
            
        try:
            env_content = f"""# Shopify Configuration
SHOPIFY_STORE_URL={self.shopify_url_var.get()}
SHOPIFY_ACCESS_TOKEN={self.shopify_token_var.get()}

# WooCommerce Configuration
WOOCOMMERCE_URL={self.wc_url_var.get()}
WOOCOMMERCE_CONSUMER_KEY={self.wc_key_var.get()}
WOOCOMMERCE_CONSUMER_SECRET={self.wc_secret_var.get()}

# WordPress Configuration (Optional - for page migration)
WORDPRESS_USERNAME={self.wp_username_var.get()}
WORDPRESS_APP_PASSWORD={self.wp_password_var.get()}

# Migration Settings
BATCH_SIZE=50
LOG_LEVEL=INFO
DRY_RUN=false
MAX_RETRIES=3
DELAY_BETWEEN_REQUESTS=1
"""
            
            with open('.env', 'w') as f:
                f.write(env_content)
                
            self.add_log_message("Credentials saved to .env file")
            self.update_saved_state()  # Mark as saved
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save credentials: {str(e)}")
    
    def load_credentials(self):
        """Load credentials from .env file"""
        try:
            # Open file dialog to choose .env file
            file_path = filedialog.askopenfilename(
                title="Select .env file",
                filetypes=[("Environment files", "*.env"), ("All files", "*.*")],
                initialdir=os.getcwd()
            )
            
            # If user cancels, return
            if not file_path:
                return
            
            # Read the selected .env file
            env_vars = {}
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#'):
                        # Parse KEY=VALUE pairs
                        if '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            
            # Populate fields from the loaded variables
            self.shopify_url_var.set(env_vars.get('SHOPIFY_STORE_URL', ''))
            self.shopify_token_var.set(env_vars.get('SHOPIFY_ACCESS_TOKEN', ''))
            self.wc_url_var.set(env_vars.get('WOOCOMMERCE_URL', ''))
            self.wc_key_var.set(env_vars.get('WOOCOMMERCE_CONSUMER_KEY', ''))
            self.wc_secret_var.set(env_vars.get('WOOCOMMERCE_CONSUMER_SECRET', ''))
            self.wp_username_var.set(env_vars.get('WORDPRESS_USERNAME', ''))
            self.wp_password_var.set(env_vars.get('WORDPRESS_APP_PASSWORD', ''))
            
            self.add_log_message(f"Credentials loaded from {os.path.basename(file_path)}")
            self.update_saved_state()  # Mark as saved since we just loaded
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load credentials: {str(e)}")
    
    def load_env_file(self):
        """Automatically load .env file on startup if it exists"""
        try:
            if os.path.exists('.env'):
                from dotenv import load_dotenv
                load_dotenv()
                
                # Populate fields from environment variables
                self.shopify_url_var.set(os.getenv('SHOPIFY_STORE_URL', ''))
                self.shopify_token_var.set(os.getenv('SHOPIFY_ACCESS_TOKEN', ''))
                self.wc_url_var.set(os.getenv('WOOCOMMERCE_URL', ''))
                self.wc_key_var.set(os.getenv('WOOCOMMERCE_CONSUMER_KEY', ''))
                self.wc_secret_var.set(os.getenv('WOOCOMMERCE_CONSUMER_SECRET', ''))
                self.wp_username_var.set(os.getenv('WORDPRESS_USERNAME', ''))
                self.wp_password_var.set(os.getenv('WORDPRESS_APP_PASSWORD', ''))
                
                self.add_log_message("Automatically loaded credentials from .env file")
            else:
                self.add_log_message("No .env file found. Please enter credentials manually or create one.")
                
        except Exception as e:
            self.add_log_message(f"Error loading .env file: {str(e)}")
    
    def setup_change_tracking(self):
        """Set up change tracking for all input fields"""
        for var in [self.shopify_url_var, self.shopify_token_var, self.wc_url_var, 
                   self.wc_key_var, self.wc_secret_var, self.wp_username_var, self.wp_password_var]:
            var.trace('w', self.on_field_change)
    
    def on_field_change(self, *args):
        """Called when any input field changes"""
        self.check_unsaved_changes()
    
    def check_unsaved_changes(self):
        """Check if current data differs from last saved state"""
        current_data = self.get_current_data()
        self.has_unsaved_changes = current_data != self.last_saved_data
    
    def get_current_data(self):
        """Get current form data as a dictionary"""
        return {
            'shopify_url': self.shopify_url_var.get().strip(),
            'shopify_token': self.shopify_token_var.get().strip(),
            'wc_url': self.wc_url_var.get().strip(),
            'wc_key': self.wc_key_var.get().strip(),
            'wc_secret': self.wc_secret_var.get().strip(),
            'wp_username': self.wp_username_var.get().strip(),
            'wp_password': self.wp_password_var.get().strip()
        }
    
    def update_saved_state(self):
        """Update the saved state to current form data"""
        self.last_saved_data = self.get_current_data()
        self.has_unsaved_changes = False
    
    def should_show_exit_confirmation(self):
        """Determine if exit confirmation should be shown"""
        return (
            self.migration_in_progress or 
            self.has_errors or 
            self.has_unsaved_changes
        )
    
    def cleanup_on_exit(self):
        """Clean up logs when exiting the application"""
        try:
            from logger import cleanup_old_logs
            cleanup_old_logs()
        except Exception:
            pass  # Don't let cleanup errors prevent exit
    
    def cleanup_logs_on_startup(self):
        """Additional cleanup on startup to catch any empty files"""
        try:
            from logger import remove_empty_log_files, move_json_reports_to_logs
            # Just clean up empty files and move JSON reports, don't do full cleanup yet
            move_json_reports_to_logs()
            remove_empty_log_files("logs")
        except Exception:
            pass  # Don't let cleanup errors prevent startup

def main():
    """Main entry point"""
    # Hide console window on Windows
    import sys
    import platform
    
    if platform.system() == 'Windows':
        try:
            import ctypes
            # Get the console window handle
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            
            # Get console window
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                # Hide the console window (SW_HIDE = 0)
                user32.ShowWindow(hwnd, 0)
        except Exception as e:
            # If hiding fails, continue anyway - GUI will still work
            pass
    
    root = tk.Tk()
    app = MigrationGUI(root)
    
    # Handle window close with smart confirmation
    def on_closing():
        if app.should_show_exit_confirmation():
            reasons = []
            if app.migration_in_progress:
                reasons.append("• Migration is currently in progress")
            if app.has_errors:
                reasons.append("• There are errors in the output log")
            if app.has_unsaved_changes:
                reasons.append("• You have unsaved credential changes")
            
            reason_text = "\n".join(reasons)
            message = f"Are you sure you want to quit?\n\n{reason_text}"
            
            if messagebox.askokcancel("Confirm Exit", message):
                app.cleanup_on_exit()
                root.destroy()
        else:
            app.cleanup_on_exit()
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the GUI
    root.mainloop()

if __name__ == "__main__":
    main()