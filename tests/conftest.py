from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiortc import RTCDataChannel, RTCPeerConnection
from aiortc.contrib.signaling import TcpSocketSignaling


@pytest.fixture
def mock_pc():
    pc = MagicMock(spec=RTCPeerConnection)
    pc.signalingState = "stable"
    return pc


@pytest.fixture
def mock_signaling():
    return MagicMock(spec=TcpSocketSignaling)


@pytest.fixture
def mock_data_channel():
    channel = AsyncMock(spec=RTCDataChannel)
    channel.readyState = "open"
    return channel


@pytest.fixture
def mock_queue():
    with patch("multiprocessing.Queue", autospec=True) as mock_q:
        yield mock_q


@pytest.fixture
def mock_track():
    mock_track = MagicMock()
    mock_track.coordinates = [0, 0]
    return mock_track


@pytest.fixture
def mock_channel():
    mock_channel = MagicMock(spec=RTCDataChannel)
    mock_channel.label = "test_channel"
    return mock_channel
