import logging
import os
import glob
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init()

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA
    }

    def format(self, record):
        # Add color to the log level
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{Style.RESET_ALL}"
        
        return super().format(record)

def setup_logger(name="migration", level="INFO"):
    """Set up logger with both file and console output"""
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Create file handler with delayed opening to avoid empty files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"logs/migration_{timestamp}.log"
    
    # Create a custom handler that only creates file when first log is written
    class DelayedFileHandler(logging.FileHandler):
        def __init__(self, filename, mode='a', encoding='utf-8', delay=True):
            self._filename = filename
            self._mode = mode
            self._encoding = encoding
            super().__init__(filename, mode, encoding, delay=True)
        
        def emit(self, record):
            # Create file only when first record is written
            if self.stream is None:
                self.stream = self._open()
            super().emit(record)
    
    file_handler = DelayedFileHandler(log_file, encoding='utf-8', delay=True)
    file_handler.setLevel(logging.DEBUG)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = ColoredFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Add formatters to handlers
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def cleanup_old_logs(keep_recent=5):
    """
    Clean up old log files, keeping only:
    - The 5 most recent logs
    - All logs that contain ERROR or CRITICAL messages
    Also removes empty log files and moves JSON reports to logs folder
    """
    try:
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            return
        
        # Move any JSON report files from main directory to logs folder
        move_json_reports_to_logs()
        
        # Get all log files (both .log and .json)
        log_files = glob.glob(os.path.join(logs_dir, "migration_*.log"))
        json_files = glob.glob(os.path.join(logs_dir, "migration_report_*.json"))
        
        # Remove empty log files first
        empty_files_removed = remove_empty_log_files(logs_dir)
        
        # Update log_files list after removing empty files
        log_files = glob.glob(os.path.join(logs_dir, "migration_*.log"))
        
        if len(log_files) <= keep_recent:
            if empty_files_removed > 0:
                print(f"Removed {empty_files_removed} empty log files")
            return  # Not enough files to clean up
        
        # Sort by modification time (newest first)
        log_files.sort(key=os.path.getmtime, reverse=True)
        
        # Keep the most recent files
        recent_files = set(log_files[:keep_recent])
        
        # Check older files for errors
        files_with_errors = set()
        for log_file in log_files[keep_recent:]:
            if has_errors_in_log(log_file):
                files_with_errors.add(log_file)
        
        # Files to keep: recent files + files with errors
        files_to_keep = recent_files | files_with_errors
        
        # Delete files that are not in the keep list
        deleted_count = 0
        for log_file in log_files:
            if log_file not in files_to_keep:
                try:
                    os.remove(log_file)
                    deleted_count += 1
                except OSError:
                    pass  # Ignore errors when deleting
        
        # Also clean up old JSON reports (keep same number as logs)
        json_files.sort(key=os.path.getmtime, reverse=True)
        for json_file in json_files[keep_recent * 2:]:  # Keep more JSON files as they're smaller
            try:
                os.remove(json_file)
                deleted_count += 1
            except OSError:
                pass
        
        total_cleaned = deleted_count + empty_files_removed
        if total_cleaned > 0:
            print(f"Cleaned up {total_cleaned} log files (kept {len(files_to_keep)} log files, {min(len(json_files), keep_recent * 2)} report files)")
            
    except Exception:
        # Don't let log cleanup errors affect the main application
        pass

def has_errors_in_log(log_file):
    """Check if a log file contains ERROR or CRITICAL messages"""
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            return 'ERROR' in content or 'CRITICAL' in content
    except Exception:
        # If we can't read the file, assume it has no errors
        return False

def remove_empty_log_files(logs_dir):
    """Remove empty log files from the logs directory"""
    removed_count = 0
    try:
        if not os.path.exists(logs_dir):
            return 0
            
        # Check all log files for emptiness
        all_log_files = glob.glob(os.path.join(logs_dir, "*.log"))
        
        # Get current timestamp to avoid deleting very recent files that might be in use
        import time
        current_time = time.time()
        
        for log_file in all_log_files:
            try:
                # Check if file exists and is empty
                if os.path.exists(log_file) and os.path.getsize(log_file) == 0:
                    # Check if file is old enough to safely delete (older than 10 seconds)
                    file_time = os.path.getmtime(log_file)
                    if current_time - file_time > 10:  # Only delete files older than 10 seconds
                        os.remove(log_file)
                        removed_count += 1
                        print(f"Removed empty log file: {os.path.basename(log_file)}")
                    else:
                        print(f"Skipping recent empty file: {os.path.basename(log_file)} (might be in use)")
            except (OSError, IOError) as e:
                # Silently skip files that are in use or can't be deleted
                pass
                
    except Exception as e:
        print(f"Error in remove_empty_log_files: {e}")
        pass  # Don't let cleanup errors affect the main application
    
    return removed_count

def move_json_reports_to_logs():
    """Move JSON migration reports from main directory to logs folder"""
    try:
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        
        # Find all migration report JSON files in main directory
        main_json_files = glob.glob("migration_report_*.json")
        
        moved_count = 0
        for json_file in main_json_files:
            try:
                # Move to logs directory
                destination = os.path.join(logs_dir, os.path.basename(json_file))
                
                # If destination already exists, add a timestamp to make it unique
                if os.path.exists(destination):
                    base_name, ext = os.path.splitext(os.path.basename(json_file))
                    timestamp = datetime.now().strftime("%H%M%S")
                    destination = os.path.join(logs_dir, f"{base_name}_{timestamp}{ext}")
                
                os.rename(json_file, destination)
                moved_count += 1
                
            except OSError:
                pass  # Ignore errors when moving files
        
        if moved_count > 0:
            print(f"Moved {moved_count} JSON report files to logs folder")
            
    except Exception:
        pass  # Don't let file operations affect the main application