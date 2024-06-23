import json
import math
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from aiortc import RTCPeerConnection

from server import distance_between, on_message, run_server, setup_data_channel


def test_distance_between_coordinates():
    """Test distance calculation with positive coordinates."""
    point_a = np.array([1, 2])
    point_b = np.array([4, 6])
    expected_distance = math.sqrt((4 - 1) ** 2 + (6 - 2) ** 2)
    assert distance_between(point_a, point_b) == expected_distance


@patch("server.logging.info")
def test_on_message_valid_coordinates(mock_info):
    valid_message = json.dumps([3, 4])
    actual_coordinates = np.array([0, 0])
    expected_distance = distance_between(
        np.array(json.loads(valid_message)), actual_coordinates
    )

    on_message(valid_message, actual_coordinates)

    mock_info.assert_called_once_with(
        f"Prediction Error (distance): {expected_distance}"
    )


@patch("server.logging.error")
def test_on_message_invalid_json(mock_error):
    invalid_message = "{not_valid_json}"
    on_message(invalid_message, np.array([0, 0]))
    mock_error.assert_called_once()


@patch("server.logging.info")
@patch("server.on_message")
def test_setup_data_channel(
    mock_on_message, mock_log_info, mock_pc, mock_track, mock_channel
):
    setup_data_channel(mock_pc, mock_track)

    mock_pc.on.assert_called_once_with("datachannel")
    event_handler = mock_pc.on.mock_calls[1][1][0]
    event_handler(mock_channel)

    mock_log_info.assert_called_once_with(f"Channel {mock_channel.label} created ")

    test_message = "Test message"
    mock_channel.on.call_count = 1
    message_handler = mock_channel.on.mock_calls[0][1][1]
    message_handler(test_message)

    mock_on_message.assert_called_once_with(test_message, mock_track.coordinates)


@pytest.mark.asyncio
@patch("server.wait_for_offer_and_send_answer", new_callable=AsyncMock)
@patch("server.send_offer_and_wait_for_answer", new_callable=AsyncMock)
@patch("server.setup_data_channel")
@patch("server.logging.error")
@patch("server.BallBouncingTrack")
async def test_run_client_exception(
    mock_track,
    mock_log_error,
    mock_setup_data_channel,
    mock_send_offer_and_wait_for_answer,
    mock_wait_for_offer_and_send_answer,
):
    mock_wait_for_offer_and_send_answer.side_effect = Exception("Test exception")

    mock_media_pc = AsyncMock()
    mock_media_signaling = AsyncMock()
    mock_data_pc = AsyncMock()
    mock_data_signaling = AsyncMock()

    await run_server(
        mock_media_pc,
        mock_media_signaling,
        mock_data_pc,
        mock_data_signaling,
    )

    mock_log_error.assert_called_once_with("Server error: Test exception")


@pytest.mark.asyncio
@patch("server.wait_for_offer_and_send_answer", new_callable=AsyncMock)
@patch("server.send_offer_and_wait_for_answer", new_callable=AsyncMock)
@patch("server.setup_data_channel")
@patch("server.logging.error")
@patch("server.BallBouncingTrack")
async def test_run_client_success(
    mock_bouncing_ball_track,
    mock_log_error,
    mock_setup_data_channel,
    mock_send_offer_and_wait_for_answer,
    mock_wait_for_offer_and_send_answer,
):
    mock_media_pc = AsyncMock(spec=RTCPeerConnection)
    mock_data_pc = AsyncMock(spec=RTCPeerConnection)
    mock_media_signaling = AsyncMock()
    mock_data_signaling = AsyncMock()

    await run_server(
        mock_media_pc,
        mock_media_signaling,
        mock_data_pc,
        mock_data_signaling,
    )
    assert mock_media_pc.addTrack.call_count == 1
    mock_bouncing_ball_track.assert_called_with(640, 480)

    mock_send_offer_and_wait_for_answer.assert_called_once_with(
        mock_media_pc, mock_media_signaling
    )

    mock_setup_data_channel.assert_called_once_with(
        mock_data_pc, mock_bouncing_ball_track.return_value
    )

    mock_wait_for_offer_and_send_answer.assert_called_once_with(
        mock_data_pc, mock_data_signaling
    )

    mock_media_signaling.receive.assert_awaited_once()
    mock_log_error.assert_not_called()
    return
