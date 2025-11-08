#!/usr/bin/env python3
"""
Standalone log cleanup script
Run this when no applications are using the log files
"""
import os
import glob
import time
from datetime import datetime

def cleanup_empty_log_files():
    """Clean up empty log files when no processes are using them"""
    print("🧹 Standalone Log Cleanup")
    print("=" * 30)
    
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        print("No logs directory found.")
        return
    
    # Move any JSON reports from main directory
    main_json_files = glob.glob("migration_report_*.json")
    if main_json_files:
        moved_count = 0
        for json_file in main_json_files:
            try:
                destination = os.path.join(logs_dir, os.path.basename(json_file))
                if os.path.exists(destination):
                    base_name, ext = os.path.splitext(os.path.basename(json_file))
                    timestamp = datetime.now().strftime("%H%M%S")
                    destination = os.path.join(logs_dir, f"{base_name}_{timestamp}{ext}")
                
                os.rename(json_file, destination)
                moved_count += 1
                print(f"   Moved: {json_file} -> logs/")
            except Exception as e:
                print(f"   Error moving {json_file}: {e}")
        
        if moved_count > 0:
            print(f"✅ Moved {moved_count} JSON files to logs directory")
    
    # Check for empty log files
    all_log_files = glob.glob(os.path.join(logs_dir, "*.log"))
    empty_files = []
    
    print(f"\n📊 Analyzing {len(all_log_files)} log files:")
    for log_file in all_log_files:
        try:
            size = os.path.getsize(log_file)
            name = os.path.basename(log_file)
            if size == 0:
                empty_files.append(log_file)
                print(f"   ❌ {name}: {size} bytes (EMPTY)")
            else:
                print(f"   ✅ {name}: {size} bytes")
        except Exception as e:
            print(f"   ⚠️  {name}: Error reading ({e})")
    
    # Remove empty files
    if empty_files:
        print(f"\n🗑️  Removing {len(empty_files)} empty log files:")
        removed_count = 0
        for empty_file in empty_files:
            try:
                os.remove(empty_file)
                removed_count += 1
                print(f"   ✅ Removed: {os.path.basename(empty_file)}")
            except Exception as e:
                print(f"   ❌ Could not remove {os.path.basename(empty_file)}: {e}")
        
        print(f"\n✅ Successfully removed {removed_count}/{len(empty_files)} empty files")
    else:
        print("\n✅ No empty log files found!")
    
    # Clean up old log files (keep 5 most recent + any with errors)
    print(f"\n🗄️  Checking for old log files to clean up...")
    
    # Sort by modification time (newest first)
    all_log_files = glob.glob(os.path.join(logs_dir, "*.log"))  # Refresh list after deletions
    if len(all_log_files) > 5:
        all_log_files.sort(key=os.path.getmtime, reverse=True)
        
        # Keep recent files
        recent_files = set(all_log_files[:5])
        
        # Check older files for errors
        files_with_errors = set()
        for log_file in all_log_files[5:]:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'ERROR' in content or 'CRITICAL' in content:
                        files_with_errors.add(log_file)
            except Exception:
                pass
        
        # Delete old files without errors
        files_to_delete = set(all_log_files[5:]) - files_with_errors
        
        if files_to_delete:
            print(f"   Removing {len(files_to_delete)} old log files:")
            for old_file in files_to_delete:
                try:
                    os.remove(old_file)
                    print(f"   ✅ Removed old file: {os.path.basename(old_file)}")
                except Exception as e:
                    print(f"   ❌ Could not remove {os.path.basename(old_file)}: {e}")
        
        print(f"✅ Kept {len(recent_files)} recent files + {len(files_with_errors)} files with errors")
    else:
        print("   All log files are recent enough to keep")

def main():
    try:
        cleanup_empty_log_files()
        print("\n🎉 Log cleanup completed!")
    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")

if __name__ == "__main__":
    main()