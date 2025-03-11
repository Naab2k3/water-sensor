import time
import os, uos

class Logger:
    def __init__(self, log_dir='logs', max_lines_per_file=1000):
        self.log_dir = log_dir
        self.max_lines_per_file = max_lines_per_file
        try:
            uos.stat(self.log_dir)
        except OSError:
            uos.mkdir(self.log_dir)
        self.temp_logs = []
        self.ntp_synced = False
        self.UTCOFFSET = 25200

    def log(self, message, console=False):
        current_time = time.time() + self.UTCOFFSET
        timestamp = time.localtime(current_time)
        formatted_time = "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(*timestamp[:6])
        log_entry = f"{formatted_time} - {message}\n"
        
        # Always print to console
        print(log_entry.strip())
        
        # Only log to file if console is False
        if not console:
            if self.ntp_synced:
                self._write_log(log_entry, timestamp)
            else:
                self.temp_logs.append((log_entry, timestamp))

    def _write_log(self, log_entry, timestamp):
        filename = f"{self.log_dir}/{timestamp[0]:04}-{timestamp[1]:02}-{timestamp[2]:02}.log"
        self._rotate_logs(filename)
        try:
            with open(filename, 'a') as f:
                f.write(log_entry)
        except OSError as e:
            print(f"Error writing to log file: {e}")

    def _rotate_logs(self, filename):
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
            if len(lines) >= self.max_lines_per_file:
                # Rotate logs by removing the oldest line
                with open(filename, 'w') as f:
                    f.writelines(lines[1:])
        except OSError:
            # File doesn't exist, no need to rotate
            pass

    def set_ntp_synced(self):
        self.ntp_synced = True
        self._flush_temp_logs()

    def _flush_temp_logs(self):
        for log_entry, timestamp in self.temp_logs:
            self._write_log(log_entry, timestamp)
        self.temp_logs.clear()

    def clean_old_logs(self, days=7):
        current_time = time.time()
        for filename in uos.listdir(self.log_dir):
            file_path = f"{self.log_dir}/{filename}"
            if uos.stat(file_path)[8] < (current_time - days * 86400):
                uos.remove(file_path)
                self.log(f"Deleted old log file: {filename}")

    def get_logs(self, num_lines: int = 20) -> str:
        log_files = sorted(
            [f for f in uos.listdir(self.log_dir) if f.endswith('.log')],
            reverse=True
        )
        logs = []
        lines_read = 0

        for log_file in log_files:
            file_path = f"{self.log_dir}/{log_file}"
            with open(file_path, 'r') as f:
                file_lines = f.readlines()
                logs = file_lines[-num_lines + lines_read:] + logs
                lines_read += len(file_lines[-num_lines + lines_read:])
                if lines_read >= num_lines:
                    break

        return ''.join(logs[:num_lines])
