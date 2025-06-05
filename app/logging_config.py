"""
Logging configuration module for Flying LoRa server.
Provides structured logging with JSON formatting and remote syslog support.
"""

import logging
import logging.handlers
import json
import os
import socket
import time
from typing import Dict, Any, Optional
from pythonjsonlogger import jsonlogger
from functools import wraps

# Default log directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to the log record.
        
        Args:
            log_record: The log record being built
            record: The original LogRecord
            message_dict: The message dictionary
        """
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime())
        
        # Add hostname
        log_record['hostname'] = socket.gethostname()
        
        # Add process and thread info
        log_record['process'] = record.process
        log_record['processName'] = record.processName
        log_record['threadName'] = record.threadName
        
        # Add log level name
        log_record['level'] = record.levelname
        
        # Add module and function info
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

class LoggerConfig:
    """Configuration for the Flying LoRa logging system."""
    
    def __init__(
        self,
        app_name: str = 'flying-lora',
        log_level: str = 'INFO',
        enable_file_logging: bool = True,
        enable_syslog: bool = False,
        syslog_host: Optional[str] = None,
        syslog_port: int = 514,
        enable_json: bool = True,
        max_bytes: int = 10485760,  # 10MB
        backup_count: int = 5,
        debug_mode: bool = False
    ):
        """Initialize logging configuration.
        
        Args:
            app_name: Name of the application
            log_level: Minimum log level to record
            enable_file_logging: Whether to log to files
            enable_syslog: Whether to send logs to syslog
            syslog_host: Remote syslog host
            syslog_port: Remote syslog port
            enable_json: Whether to use JSON formatting
            max_bytes: Maximum size of each log file
            backup_count: Number of backup files to keep
            debug_mode: Whether to enable debug mode
        """
        self.app_name = app_name
        self.log_level = getattr(logging, log_level.upper())
        self.enable_file_logging = enable_file_logging
        self.enable_syslog = enable_syslog
        self.syslog_host = syslog_host
        self.syslog_port = syslog_port
        self.enable_json = enable_json
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.debug_mode = debug_mode
        
        # Create logger
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(self.log_level)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Set up handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up logging handlers based on configuration."""
        # Create formatters
        if self.enable_json:
            formatter = CustomJsonFormatter(
                '%(timestamp)s %(level)s %(name)s %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        if self.enable_file_logging:
            log_file = os.path.join(LOG_DIR, f'{self.app_name}.log')
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        # Syslog handler
        if self.enable_syslog and self.syslog_host:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(self.syslog_host, self.syslog_port)
            )
            syslog_handler.setFormatter(formatter)
            self.logger.addHandler(syslog_handler)
        
        # Debug file handler
        if self.debug_mode:
            debug_file = os.path.join(LOG_DIR, f'{self.app_name}_debug.log')
            debug_handler = logging.handlers.RotatingFileHandler(
                debug_file,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count
            )
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(formatter)
            self.logger.addHandler(debug_handler)
    
    def get_logger(self) -> logging.Logger:
        """Get the configured logger.
        
        Returns:
            The configured logging.Logger instance
        """
        return self.logger

def log_execution_time(logger: Optional[logging.Logger] = None):
    """Decorator to log function execution time.
    
    Args:
        logger: Logger to use, or None to use root logger
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            log = logger or logging.getLogger()
            log.debug(
                'Function execution time',
                extra={
                    'function': func.__name__,
                    'duration': duration,
                    'args': str(args),
                    'kwargs': str(kwargs)
                }
            )
            return result
        return wrapper
    return decorator

def init_logging(
    app_name: str = 'flying-lora',
    log_level: str = 'INFO',
    enable_file_logging: bool = True,
    enable_syslog: bool = False,
    syslog_host: Optional[str] = None,
    syslog_port: int = 514,
    enable_json: bool = True,
    max_bytes: int = 10485760,
    backup_count: int = 5,
    debug_mode: bool = False
) -> logging.Logger:
    """Initialize the logging system.
    
    Args:
        app_name: Name of the application
        log_level: Minimum log level to record
        enable_file_logging: Whether to log to files
        enable_syslog: Whether to send logs to syslog
        syslog_host: Remote syslog host
        syslog_port: Remote syslog port
        enable_json: Whether to use JSON formatting
        max_bytes: Maximum size of each log file
        backup_count: Number of backup files to keep
        debug_mode: Whether to enable debug mode
    
    Returns:
        The configured logging.Logger instance
    """
    config = LoggerConfig(
        app_name=app_name,
        log_level=log_level,
        enable_file_logging=enable_file_logging,
        enable_syslog=enable_syslog,
        syslog_host=syslog_host,
        syslog_port=syslog_port,
        enable_json=enable_json,
        max_bytes=max_bytes,
        backup_count=backup_count,
        debug_mode=debug_mode
    )
    return config.get_logger()

# Example usage:
# logger = init_logging(debug_mode=True)
# logger.info('Application started', extra={'version': '1.0.0'})
# 
# @log_execution_time(logger)
# def slow_function():
#     time.sleep(1)
#     return 'Done' 