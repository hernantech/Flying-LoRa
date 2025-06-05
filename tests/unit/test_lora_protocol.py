import pytest
import json
import time
from unittest.mock import MagicMock, patch
from lora_protocol import LoRaProtocolHandler, MessagePriority, LoRaPacket

def test_message_fragmentation():
    """Test message fragmentation and reassembly"""
    handler = LoRaProtocolHandler()
    
    # Create a large message that will require fragmentation
    large_message = "x" * (handler.MAX_PACKET_SIZE * 2)
    message_id = handler.send_message(large_message)
    
    # Check that message was fragmented
    assert len(handler.message_buffer) == 1
    assert message_id in handler.message_buffer
    
    # Verify fragments in send queue
    high_queue = handler.send_queue[MessagePriority.HIGH]
    med_queue = handler.send_queue[MessagePriority.MEDIUM]
    low_queue = handler.send_queue[MessagePriority.LOW]
    
    total_fragments = sum(
        queue.qsize() for queue in [high_queue, med_queue, low_queue]
    )
    expected_fragments = (len(large_message) + handler.MAX_PACKET_SIZE - 1) // handler.MAX_PACKET_SIZE
    
    assert total_fragments == expected_fragments

def test_message_priority():
    """Test message priority handling"""
    handler = LoRaProtocolHandler()
    
    # Send messages with different priorities
    handler.send_message("high priority", MessagePriority.HIGH)
    handler.send_message("medium priority", MessagePriority.MEDIUM)
    handler.send_message("low priority", MessagePriority.LOW)
    
    # Check queue sizes
    assert handler.send_queue[MessagePriority.HIGH].qsize() == 1
    assert handler.send_queue[MessagePriority.MEDIUM].qsize() == 1
    assert handler.send_queue[MessagePriority.LOW].qsize() == 1
    
    # Verify priority order
    _, high_packet = handler.send_queue[MessagePriority.HIGH].get()
    _, med_packet = handler.send_queue[MessagePriority.MEDIUM].get()
    _, low_packet = handler.send_queue[MessagePriority.LOW].get()
    
    assert high_packet.priority == MessagePriority.HIGH
    assert med_packet.priority == MessagePriority.MEDIUM
    assert low_packet.priority == MessagePriority.LOW

@patch('serial.Serial')
def test_packet_retransmission(mock_serial):
    """Test automatic packet retransmission"""
    handler = LoRaProtocolHandler()
    
    # Mock serial port
    mock_serial.return_value.write.return_value = len(b"test")
    handler.serial = mock_serial.return_value
    
    # Send message
    message_id = handler.send_message("test message")
    
    # Simulate timeout
    time.sleep(handler.ACK_TIMEOUT + 0.1)
    
    # Check pending acknowledgments
    handler._check_pending_acks()
    
    # Verify retransmission
    assert message_id in handler.message_buffer
    assert handler.signal_stats['retransmissions'] > 0

def test_crc_validation():
    """Test CRC validation"""
    handler = LoRaProtocolHandler()
    
    # Create valid packet
    valid_packet = LoRaPacket(
        message_id="test_1",
        fragment_id=0,
        total_fragments=1,
        priority=MessagePriority.MEDIUM,
        payload=b"test data",
        crc=None,  # Will be calculated
        rssi=-60,
        snr=10,
        timestamp=time.time()
    )
    
    # Calculate CRC
    import zlib
    valid_packet.crc = zlib.crc32(valid_packet.payload)
    
    # Create invalid packet with wrong CRC
    invalid_packet = LoRaPacket(
        message_id="test_2",
        fragment_id=0,
        total_fragments=1,
        priority=MessagePriority.MEDIUM,
        payload=b"test data",
        crc=12345,  # Wrong CRC
        rssi=-60,
        snr=10,
        timestamp=time.time()
    )
    
    # Test packet handling
    handler._handle_packet(valid_packet)
    handler._handle_packet(invalid_packet)
    
    # Check packet loss counter
    assert handler.signal_stats['packet_loss'] == 1

def test_signal_quality_monitoring():
    """Test signal quality monitoring"""
    handler = LoRaProtocolHandler()
    
    # Simulate receiving packets with different signal qualities
    for i in range(5):
        packet = LoRaPacket(
            message_id=f"test_{i}",
            fragment_id=0,
            total_fragments=1,
            priority=MessagePriority.MEDIUM,
            payload=b"test",
            crc=zlib.crc32(b"test"),
            rssi=-60 - i,  # Decreasing RSSI
            snr=10 - i,    # Decreasing SNR
            timestamp=time.time()
        )
        handler._handle_packet(packet)
    
    # Check signal quality stats
    stats = handler.get_signal_quality()
    assert 'rssi_avg' in stats
    assert 'snr_avg' in stats
    assert len(handler.signal_stats['rssi']) == 5
    assert len(handler.signal_stats['snr']) == 5

@pytest.mark.parametrize("message_size", [
    100,    # Small message
    1000,   # Medium message
    5000    # Large message
])
def test_message_sizes(message_size):
    """Test handling different message sizes"""
    handler = LoRaProtocolHandler()
    message = "x" * message_size
    
    # Send message
    message_id = handler.send_message(message)
    
    # Calculate expected fragments
    expected_fragments = (message_size + handler.MAX_PACKET_SIZE - 1) // handler.MAX_PACKET_SIZE
    
    # Check fragmentation
    total_fragments = sum(
        queue.qsize() for queue in handler.send_queue.values()
    )
    assert total_fragments == expected_fragments
    
    # Verify original message is stored
    assert message_id in handler.message_buffer
    assert len(handler.message_buffer[message_id]) == message_size

def test_concurrent_messages():
    """Test handling concurrent messages"""
    handler = LoRaProtocolHandler()
    
    # Send multiple messages concurrently
    import threading
    messages = []
    
    def send_message(text):
        message_id = handler.send_message(text)
        messages.append(message_id)
    
    threads = []
    for i in range(5):
        thread = threading.Thread(
            target=send_message,
            args=(f"message_{i}",)
        )
        threads.append(thread)
        thread.start()
    
    # Wait for all threads
    for thread in threads:
        thread.join()
    
    # Verify all messages were handled
    assert len(messages) == 5
    assert len(handler.message_buffer) == 5
    
    # Check message integrity
    for i, message_id in enumerate(messages):
        assert handler.message_buffer[message_id] == f"message_{i}" 