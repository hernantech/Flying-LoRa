import sqlite3
import json
import time
import threading
import logging
import zlib
from typing import Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from config import ConfigManager
from logging_config import LoggerSetup

class TimeSeriesDB:
    def __init__(self, db_path: str = "data/timeseries.db"):
        # Initialize configuration and logging
        self.config = ConfigManager()
        self.log_setup = LoggerSetup()
        self.logger = self.log_setup.get_logger()
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Database configuration
        self.db_path = db_path
        self.retention_days = self.config.get('storage.retention_days', 30)
        self.compression_threshold = self.config.get('storage.compression_threshold', 1024)  # bytes
        self.buffer_size = self.config.get('storage.buffer_size', 1000)  # records
        
        # Initialize buffers
        self.data_buffer: List[Dict] = []
        self.buffer_lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        # Start background tasks
        self.running = True
        self.flush_thread = threading.Thread(target=self._periodic_flush)
        self.cleanup_thread = threading.Thread(target=self._periodic_cleanup)
        self.flush_thread.start()
        self.cleanup_thread.start()

    def _init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Time-series data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS timeseries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL,
                    tags TEXT,
                    data BLOB,
                    is_compressed INTEGER DEFAULT 0
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON timeseries(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric ON timeseries(metric_name)")
            
            # Metadata table for retention policies
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS retention_policies (
                    metric_name TEXT PRIMARY KEY,
                    retention_days INTEGER NOT NULL,
                    compression_enabled INTEGER DEFAULT 1
                )
            """)
            
            conn.commit()

    def insert(self, metric_name: str, value: Optional[float] = None, 
               tags: Optional[Dict] = None, data: Optional[Dict] = None):
        """Insert a new time-series record"""
        try:
            record = {
                'timestamp': time.time(),
                'metric_name': metric_name,
                'value': value,
                'tags': json.dumps(tags) if tags else None,
                'data': self._prepare_data(data) if data else None,
                'is_compressed': 0
            }
            
            with self.buffer_lock:
                self.data_buffer.append(record)
                
                # Flush if buffer is full
                if len(self.data_buffer) >= self.buffer_size:
                    self._flush_buffer()
                    
        except Exception as e:
            self.logger.error(f"Failed to insert record: {e}")

    def query(self, metric_name: str, start_time: float, end_time: float,
              tags: Optional[Dict] = None, limit: Optional[int] = None) -> pd.DataFrame:
        """Query time-series data"""
        try:
            # Flush buffer before querying
            self._flush_buffer()
            
            query = """
                SELECT timestamp, metric_name, value, tags, data, is_compressed
                FROM timeseries
                WHERE metric_name = ? AND timestamp BETWEEN ? AND ?
            """
            params = [metric_name, start_time, end_time]
            
            if tags:
                # Convert tags to JSON string for comparison
                tags_json = json.dumps(tags)
                query += " AND tags = ?"
                params.append(tags_json)
            
            if limit:
                query += f" LIMIT {limit}"
            
            with sqlite3.connect(self.db_path) as conn:
                # Read data into DataFrame
                df = pd.read_sql_query(query, conn, params=params)
                
                # Decompress and parse data
                if not df.empty:
                    df['tags'] = df['tags'].apply(lambda x: json.loads(x) if x else None)
                    df['data'] = df.apply(lambda row: self._decompress_data(row['data'], row['is_compressed']), axis=1)
                
                return df
            
        except Exception as e:
            self.logger.error(f"Query failed: {e}")
            return pd.DataFrame()

    def set_retention_policy(self, metric_name: str, retention_days: int, compression_enabled: bool = True):
        """Set retention policy for a metric"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO retention_policies (metric_name, retention_days, compression_enabled)
                    VALUES (?, ?, ?)
                """, (metric_name, retention_days, int(compression_enabled)))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to set retention policy: {e}")

    def export_data(self, metric_name: str, start_time: float, end_time: float,
                    format: str = 'csv', output_path: Optional[str] = None) -> Optional[str]:
        """Export data to CSV or JSON format"""
        try:
            df = self.query(metric_name, start_time, end_time)
            
            if df.empty:
                return None
            
            if not output_path:
                output_path = f"exports/{metric_name}_{int(start_time)}_{int(end_time)}.{format}"
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            if format.lower() == 'csv':
                df.to_csv(output_path, index=False)
            elif format.lower() == 'json':
                df.to_json(output_path, orient='records', date_format='iso')
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return None

    def get_metrics_summary(self) -> Dict:
        """Get summary of stored metrics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get metrics count and size
                cursor.execute("""
                    SELECT 
                        metric_name,
                        COUNT(*) as count,
                        SUM(LENGTH(data)) as total_size,
                        MIN(timestamp) as first_timestamp,
                        MAX(timestamp) as last_timestamp
                    FROM timeseries
                    GROUP BY metric_name
                """)
                
                summary = {}
                for row in cursor.fetchall():
                    metric_name, count, total_size, first_ts, last_ts = row
                    summary[metric_name] = {
                        'count': count,
                        'size_bytes': total_size or 0,
                        'first_timestamp': first_ts,
                        'last_timestamp': last_ts
                    }
                
                return summary
                
        except Exception as e:
            self.logger.error(f"Failed to get metrics summary: {e}")
            return {}

    def _prepare_data(self, data: Dict) -> bytes:
        """Prepare data for storage, with optional compression"""
        try:
            json_data = json.dumps(data).encode()
            
            # Compress if data is large enough
            if len(json_data) > self.compression_threshold:
                compressed_data = zlib.compress(json_data)
                if len(compressed_data) < len(json_data):
                    return compressed_data
            
            return json_data
            
        except Exception as e:
            self.logger.error(f"Data preparation failed: {e}")
            return b''

    def _decompress_data(self, data: bytes, is_compressed: bool) -> Optional[Dict]:
        """Decompress and parse data"""
        if not data:
            return None
            
        try:
            if is_compressed:
                data = zlib.decompress(data)
            return json.loads(data.decode())
            
        except Exception as e:
            self.logger.error(f"Data decompression failed: {e}")
            return None

    def _flush_buffer(self):
        """Flush buffered data to database"""
        with self.buffer_lock:
            if not self.data_buffer:
                return
            
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.executemany("""
                        INSERT INTO timeseries 
                        (timestamp, metric_name, value, tags, data, is_compressed)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, [
                        (
                            record['timestamp'],
                            record['metric_name'],
                            record['value'],
                            record['tags'],
                            record['data'],
                            record['is_compressed']
                        )
                        for record in self.data_buffer
                    ])
                    conn.commit()
                
                self.data_buffer.clear()
                
            except Exception as e:
                self.logger.error(f"Buffer flush failed: {e}")

    def _periodic_flush(self):
        """Periodically flush buffer"""
        while self.running:
            try:
                self._flush_buffer()
                time.sleep(60)  # Flush every minute
                
            except Exception as e:
                self.logger.error(f"Periodic flush failed: {e}")
                time.sleep(5)

    def _periodic_cleanup(self):
        """Periodically clean up old data"""
        while self.running:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Get retention policies
                    cursor.execute("SELECT metric_name, retention_days FROM retention_policies")
                    policies = dict(cursor.fetchall())
                    
                    # Apply default retention policy for metrics without specific policy
                    cursor.execute("SELECT DISTINCT metric_name FROM timeseries")
                    all_metrics = [row[0] for row in cursor.fetchall()]
                    
                    for metric in all_metrics:
                        retention_days = policies.get(metric, self.retention_days)
                        cutoff_time = time.time() - (retention_days * 86400)
                        
                        # Delete old data
                        cursor.execute("""
                            DELETE FROM timeseries
                            WHERE metric_name = ? AND timestamp < ?
                        """, (metric, cutoff_time))
                    
                    conn.commit()
                    
                # Sleep for 6 hours before next cleanup
                time.sleep(21600)
                
            except Exception as e:
                self.logger.error(f"Periodic cleanup failed: {e}")
                time.sleep(300)

    def close(self):
        """Close database connection and stop background tasks"""
        self.running = False
        self._flush_buffer()
        
        if self.flush_thread:
            self.flush_thread.join()
        if self.cleanup_thread:
            self.cleanup_thread.join()

# Example usage
if __name__ == '__main__':
    db = TimeSeriesDB()
    
    # Example: Insert some test data
    db.insert(
        metric_name="temperature",
        value=25.5,
        tags={'sensor': 'main', 'location': 'room1'},
        data={'humidity': 60, 'pressure': 1013}
    )
    
    # Example: Set retention policy
    db.set_retention_policy("temperature", retention_days=7)
    
    # Example: Query data
    end_time = time.time()
    start_time = end_time - 3600  # Last hour
    df = db.query("temperature", start_time, end_time)
    print("\nQuery Results:")
    print(df)
    
    # Example: Export data
    export_path = db.export_data("temperature", start_time, end_time, format='csv')
    if export_path:
        print(f"\nData exported to: {export_path}")
    
    # Example: Get metrics summary
    summary = db.get_metrics_summary()
    print("\nMetrics Summary:")
    print(json.dumps(summary, indent=2))
    
    db.close() 