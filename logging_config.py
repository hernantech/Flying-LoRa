import logging
import logging.handlers
import json
import os
import socket
from datetime import datetime
from functools import wraps
import time
from typing import Optional, Dict, Any, Callable
import threading

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.threadName,
            'process': record.process
        }

        # Add extra fields if they exist
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)

class LoggerSetup:
    def __init__(
        self,
        log_dir: str = 'logs',
        app_name: str = 'flying_lora',
        max_size_mb: int = 100,
        backup_count: int = 5,
        remote_syslog: Optional[tuple] = None,
        debug_mode: bool = False
    ):
        self.log_dir = log_dir
        self.app_name = app_name
        self.max_size_mb = max_size_mb
        self.backup_count = backup_count
        self.remote_syslog = remote_syslog
        self.debug_mode = debug_mode
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Initialize logger
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Add handlers
        self._setup_file_handler()
        self._setup_console_handler()
        if remote_syslog:
            self._setup_syslog_handler()

    def _setup_file_handler(self):
        """Setup rotating file handler with JSON formatting"""
        log_file = os.path.join(self.log_dir, f'{self.app_name}.log')
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.max_size_mb * 1024 * 1024,
            backupCount=self.backup_count
        )
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)

    def _setup_console_handler(self):
        """Setup console handler for development"""
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)

    def _setup_syslog_handler(self):
        """Setup remote syslog handler"""
        host, port = self.remote_syslog
        handler = logging.handlers.SysLogHandler(
            address=(host, port),
            facility=logging.handlers.SysLogHandler.LOG_LOCAL0
        )
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)

    def get_logger(self) -> logging.Logger:
        """Get the configured logger"""
        return self.logger

    def set_debug_mode(self, enabled: bool):
        """Toggle debug mode"""
        self.debug_mode = enabled
        self.logger.setLevel(logging.DEBUG if enabled else logging.INFO)

class PerformanceProfiler:
    """Context manager and decorator for performance profiling"""
    def __init__(self, logger: logging.Logger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
        self.thread_id = threading.get_ident()

    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"Starting operation: {self.operation}", 
                         extra={'extra_fields': {'operation': self.operation, 'event': 'start'}})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        extra = {
            'operation': self.operation,
            'duration': duration,
            'thread_id': self.thread_id,
            'event': 'end'
        }
        if exc_type:
            extra['error'] = str(exc_val)
            self.logger.error(f"Operation failed: {self.operation}", extra={'extra_fields': extra})
        else:
            self.logger.debug(f"Completed operation: {self.operation} in {duration:.3f}s",
                            extra={'extra_fields': extra})

    @classmethod
    def profile(cls, logger: logging.Logger):
        """Decorator for performance profiling"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                with cls(logger, func.__name__):
                    return func(*args, **kwargs)
            return wrapper
        return decorator

# Example usage
if __name__ == '__main__':
    # Initialize logging
    log_setup = LoggerSetup(
        debug_mode=True,
        remote_syslog=('localhost', 514)  # Example remote syslog
    )
    logger = log_setup.get_logger()

    # Example structured logging
    logger.info("System startup", extra={
        'extra_fields': {
            'version': '1.0.0',
            'environment': 'development'
        }
    })

    # Example performance profiling
    @PerformanceProfiler.profile(logger)
    def example_operation():
        time.sleep(1)  # Simulate work
        return "Operation complete"

    # Using context manager
    with PerformanceProfiler(logger, "manual_operation"):
        time.sleep(0.5)  # Simulate work

    # Using decorator
    example_operation() 