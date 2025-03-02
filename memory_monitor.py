import psutil
import time
import os
import json
from datetime import datetime
import logging
from collections import deque
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MemoryMonitor:
    def __init__(self, target_pid=None, history_size=1000):
        """
        Initialize memory monitor
        target_pid: PID of process to monitor (if None, monitors current process)
        history_size: Number of data points to keep in memory
        """
        self.target_pid = target_pid or os.getpid()
        self.process = psutil.Process(self.target_pid)
        self.history = deque(maxlen=history_size)
        self.running = False
        self.lock = threading.Lock()
        
    def get_memory_usage(self):
        """Get current memory usage in MB"""
        try:
            mem_info = self.process.memory_info()
            return {
                'timestamp': datetime.now().isoformat(),
                'rss': mem_info.rss / (1024 * 1024),  # RSS in MB
                'vms': mem_info.vms / (1024 * 1024),  # VMS in MB
                'cpu_percent': self.process.cpu_percent(),
                'num_threads': self.process.num_threads(),
                'status': self.process.status()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"Error getting memory usage: {e}")
            return None

    def start_monitoring(self, interval=1):
        """Start monitoring in a separate thread"""
        def monitor():
            while self.running:
                usage = self.get_memory_usage()
                if usage:
                    with self.lock:
                        self.history.append(usage)
                        current_rss = usage['rss']
                        if current_rss > 500:  # Alert if RSS > 500MB
                            logger.warning(f"High memory usage detected: {current_rss:.2f}MB")
                time.sleep(interval)

        self.running = True
        self.monitor_thread = threading.Thread(target=monitor)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info(f"Started monitoring process {self.target_pid}")

    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join()
        logger.info("Stopped monitoring")

    def save_history(self, filename='memory_log.json'):
        """Save monitoring history to file"""
        with self.lock:
            with open(filename, 'w') as f:
                json.dump(list(self.history), f, indent=2)
        logger.info(f"Saved memory history to {filename}")

    def print_current_usage(self):
        """Print current memory usage"""
        usage = self.get_memory_usage()
        if usage:
            print(f"\nCurrent Memory Usage:")
            print(f"RSS: {usage['rss']:.2f}MB")
            print(f"VMS: {usage['vms']:.2f}MB")
            print(f"CPU: {usage['cpu_percent']:.1f}%")
            print(f"Threads: {usage['num_threads']}")
            print(f"Status: {usage['status']}")

def find_transcribe_pid():
    """
    Find the PID of the running transcribe.py process
    Returns: PID if found, None otherwise
    """
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('transcribe.py' in cmd for cmd in cmdline):
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def monitor_telegram_bot(pid=None):
    """
    Monitor memory usage of the transcribe.py bot
    pid: Process ID of the running bot. If None, will automatically find transcribe.py
    """
    try:
        if pid is None:
            pid = find_transcribe_pid()
            if pid is None:
                logger.error("Could not find running transcribe.py process")
                return
            logger.info(f"Found transcribe.py process with PID: {pid}")
        
        # Initialize monitor for the bot process
        monitor = MemoryMonitor(pid)
        monitor.start_monitoring()

        try:
            while True:
                monitor.print_current_usage()
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nStopping monitoring...")
        finally:
            monitor.stop_monitoring()
            monitor.save_history()
            
    except Exception as e:
        logger.error(f"Error monitoring bot: {e}")

if __name__ == "__main__":
    monitor_telegram_bot()
