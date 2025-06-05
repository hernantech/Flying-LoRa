import os
import pytest
import tempfile
import redis
import sqlite3
from unittest.mock import MagicMock
from config import ConfigManager
from lora_protocol import LoRaProtocolHandler
from mesh_network import MeshNetworkManager
from data_storage import TimeSeriesDB
from cache_manager import CacheManager
from detection_service import DetectionService
from hardware_interface import HardwareInterface

@pytest.fixture(scope="session")
def config():
    """Global test configuration"""
    os.environ['APP_ENV'] = 'test'
    config = ConfigManager()
    return config

@pytest.fixture(scope="function")
def temp_db():
    """Temporary SQLite database"""
    fd, path = tempfile.mkstemp()
    conn = sqlite3.connect(path)
    yield path
    
    conn.close()
    os.close(fd)
    os.unlink(path)

@pytest.fixture(scope="function")
def redis_mock():
    """Mock Redis instance"""
    return MagicMock(spec=redis.Redis)

@pytest.fixture(scope="function")
def lora_mock():
    """Mock LoRa hardware interface"""
    mock = MagicMock(spec=LoRaProtocolHandler)
    mock.send_message.return_value = True
    mock.get_signal_quality.return_value = {'rssi': -60, 'snr': 10}
    return mock

@pytest.fixture(scope="function")
def camera_mock():
    """Mock camera feed"""
    mock = MagicMock()
    mock.read.return_value = (True, b'mock_frame_data')
    mock.isOpened.return_value = True
    return mock

@pytest.fixture(scope="function")
def hardware_mock(camera_mock):
    """Mock hardware interface"""
    mock = MagicMock(spec=HardwareInterface)
    mock.camera = camera_mock
    mock.get_gps_location.return_value = {
        'latitude': 37.7749,
        'longitude': -122.4194,
        'altitude': 100,
        'accuracy': 5.0
    }
    return mock

@pytest.fixture(scope="function")
def time_series_db(temp_db):
    """TimeSeriesDB instance with temporary database"""
    db = TimeSeriesDB(db_path=temp_db)
    yield db
    db.close()

@pytest.fixture(scope="function")
def cache_manager(redis_mock):
    """CacheManager instance with mock Redis"""
    manager = CacheManager()
    manager.redis = redis_mock
    yield manager
    manager.close()

@pytest.fixture(scope="function")
def mesh_network(lora_mock):
    """MeshNetworkManager instance with mock LoRa"""
    manager = MeshNetworkManager("test_node")
    manager.lora = lora_mock
    yield manager
    manager.stop()

@pytest.fixture(scope="function")
def detection_service(hardware_mock):
    """DetectionService instance with mock hardware"""
    service = DetectionService()
    service.hardware = hardware_mock
    yield service
    service.stop() 