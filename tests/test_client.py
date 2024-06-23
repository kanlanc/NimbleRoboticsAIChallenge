import asyncio
import json
import multiprocessing as mp
import queue
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import cv2
import numpy as np
import pytest
from aiortc import RTCDataChannel
from aiortc.mediastreams import MediaStreamError
from aiortc.rtcrtpreceiver import RemoteStreamTrack

from client import (
    cleanup,
    consume_frames,
    create_datachannel,
    predict_coordinates,
    process_frames,
    send_predicted_coordinates,
    run_client,
    setup_remote_track,
)


def generate_test_image_and_coordinates():
    """Creates a dummy image for testing"""
    width, height = 100, 100
    coordinates = (50, 50)
    img = np.zeros((width, height, 3), dtype=np.uint8)
    cv2.circle(
        img,
        coordinates,
        5,
        (255, 0, 0),
        -1,
    )
    return img, coordinates


def test_predict_coordinates():
    test_image, coordinates = generate_test_image_and_coordinates()
    result = predict_coordinates(test_image)
    assert isinstance(result, np.ndarray)
    assert result.shape == (2,)
    assert tuple(result.tolist()) == coordinates


@pytest.fixture
def mock_value():
    """Fixture to create a mock shared value."""
    mock_val = Mock()
    mock_val.get_lock = Mock()
    mock_val.get_lock.return_value = MagicMock()

    return mock_val


def test_process_frames_empty_queue(mock_queue, mock_value):
    """Test process_frames with an empty queue, expecting a log for an empty queue."""
    mock_queue().get.side_effect = [queue.Empty, None]

    with patch("client.logging.warning") as mock_log_warning:
        process_frames(mock_queue(), mock_value)

        mock_log_warning.assert_called_once_with("Queue is empty")


def test_process_frames_terminates_on_none(mock_queue, mock_value):
    """Test process_frames terminates processing when None is received."""
    mock_queue().get.side_effect = [None]  # Simulate receiving a termination signal

    with patch("client.logging.info") as mock_log_info:
        process_frames(mock_queue(), mock_value)
        mock_log_info.assert_called_once_with("Frame processing subprocess exited.")


def test_process_frames_updates_coordinates(mock_queue, mock_value, mocker):
    """Test process_frames updates coordinates correctly."""
    frame_mock = Mock()
    predicted_coordinates = (100, 200)
    mocker.patch("client.predict_coordinates", return_value=predicted_coordinates)
    mock_queue().get.side_effect = [
        frame_mock,
        None,
    ]

    process_frames(mock_queue(), mock_value)

    assert mock_value.x == predicted_coordinates[0]
    assert mock_value.y == predicted_coordinates[1]


@pytest.mark.asyncio
async def test_consume_frames_receives_and_puts_frames(mocker, mock_pc):
    mock_track = AsyncMock(spec=RemoteStreamTrack)
    mock_input_frames_q = MagicMock()

    mock_video_frame = MagicMock()
    mock_video_frame.to_ndarray.return_value = "mock_frame"

    mock_track.recv.side_effect = [
        mock_video_frame,
        asyncio.CancelledError(),
    ]

    mocker.patch("client.cv2.imshow")
    mocker.patch("client.cv2.waitKey", return_value=None)

    with pytest.raises(asyncio.CancelledError):
        await consume_frames(mock_track, mock_input_frames_q, mock_pc)

    mock_input_frames_q.put.assert_called_with("mock_frame")


@pytest.mark.asyncio
@patch("asyncio.sleep", side_effect=asyncio.CancelledError)
async def test_consume_frames_breaks_on_closed_pc(mock_pc):
    mock_track = AsyncMock(spec=RemoteStreamTrack)
    mock_input_frames_q = MagicMock()
    mock_pc.signalingState = "closed"

    mock_track.recv.side_effect = MediaStreamError()

    with pytest.raises(asyncio.CancelledError):
        await consume_frames(mock_track, mock_input_frames_q, mock_pc)

    mock_track.recv.assert_called()
    asyncio.sleep.assert_called_with(0.1)


@pytest.mark.asyncio
@patch("client.consume_frames", new_callable=AsyncMock)
async def test_setup_remote_track_with_video_track(mock_consume_frames):
    mock_pc = MagicMock()
    mock_track = AsyncMock()
    mock_track.kind = "video"
    mock_input_frames_q = MagicMock()

    setup_remote_track(mock_pc, mock_input_frames_q)

    on_track_handler = mock_pc.on.mock_calls[1][1][0]
    await on_track_handler(mock_track)

    mock_consume_frames.assert_called_once_with(
        mock_track, mock_input_frames_q, mock_pc
    )


@pytest.mark.asyncio
@patch("client.logging.error")
@patch("client.logging.info")
@patch("client.consume_frames", new_callable=AsyncMock)
async def test_setup_remote_track_with_non_video_track(
    mock_consume_frames, mock_log_info, mock_log_error
):
    mock_pc = MagicMock()
    mock_track = AsyncMock()
    mock_track.kind = "audio"
    mock_input_frames_q = MagicMock()

    setup_remote_track(mock_pc, mock_input_frames_q)

    on_track_handler = mock_pc.on.mock_calls[1][1][0]
    await on_track_handler(mock_track)

    mock_consume_frames.assert_not_called()
    mock_log_error.assert_called_once_with(
        f"Recieved track of incompatible kind {mock_track.kind}"
    )


# Assuming your function is in a module named your_module.py


@pytest.mark.asyncio
@patch("client.send_predicted_coordinates", new_callable=AsyncMock)
@patch("client.logging.info")
async def test_create_datachannel(
    mock_log_info,
    mock_send_predicted_coordinates,
    mock_pc,
    mock_value,
    mock_data_channel,
):
    mock_data_channel = AsyncMock(spec=RTCDataChannel)
    mock_data_channel.label = "ball_coordinates"
    mock_data_channel.readyState = "closed"
    mock_pc.createDataChannel.return_value = mock_data_channel

    result_channel = create_datachannel(mock_pc, mock_value)

    assert result_channel == mock_data_channel
    mock_pc.createDataChannel.assert_called_once_with("ball_coordinates")

    await mock_data_channel.on.mock_calls[1][1][0]()

    mock_log_info.assert_called_once_with(
        f"Data Channel: {mock_data_channel.label} opened"
    )
    mock_send_predicted_coordinates.assert_called_once_with(
        mock_data_channel, mock_value, mock_pc
    )


@pytest.mark.asyncio
@patch("client.logging.info")
async def test_send_predicted_coordinates(mock_log_info):
    mock_channel = MagicMock()
    mock_channel.readyState = "open"
    mock_channel.send = MagicMock()

    class MockSharedCoordinates:
        x = 10
        y = 20

    shared_predicted_coordinates = MockSharedCoordinates()
    task = asyncio.create_task(
        send_predicted_coordinates(
            mock_channel, shared_predicted_coordinates, mock_channel
        )
    )

    await asyncio.sleep(0.3)
    mock_channel.readyState = "closed"
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    mock_channel.send.assert_called_with(json.dumps((10, 20)))
    mock_log_info.assert_any_call("Sending predicted ball coordinates: 10, 20")
    mock_log_info.assert_any_call("Channel closed")


@pytest.mark.asyncio
@patch("client.close_connection", new_callable=AsyncMock)
@patch("client.logging.info")
async def test_cleanup(mock_log_info, mock_close_connection):
    mock_media_pc = AsyncMock()
    mock_data_pc = AsyncMock()
    mock_media_signaling = AsyncMock()
    mock_data_signaling = AsyncMock()

    input_frames_q = mp.Queue()

    mock_process_a = MagicMock(spec=mp.Process)
    mock_process_a.join = MagicMock()

    await cleanup(
        mock_media_pc,
        mock_data_pc,
        mock_media_signaling,
        mock_data_signaling,
        input_frames_q,
        mock_process_a,
    )

    assert input_frames_q.get() is None, "Queue should return None as the value"
    mock_process_a.join.assert_called_once()

    mock_close_connection.assert_has_calls(
        [
            ((mock_media_pc, mock_media_signaling),),
            ((mock_data_pc, mock_data_signaling),),
        ],
        any_order=False,
    )


@pytest.mark.asyncio
@patch("client.setup_remote_track")
@patch("client.wait_for_offer_and_send_answer", new_callable=AsyncMock)
@patch("client.create_datachannel")
@patch("client.send_offer_and_wait_for_answer", new_callable=AsyncMock)
@patch("client.logging.error")
async def test_run_client_exception(
    mock_log_error,
    mock_send_offer_and_wait_for_answer,
    mock_create_datachannel,
    mock_wait_for_offer_and_send_answer,
    mock_setup_remote_track,
):
    mock_wait_for_offer_and_send_answer.side_effect = Exception("Test exception")

    mock_media_pc = AsyncMock()
    mock_media_signaling = AsyncMock()
    mock_data_pc = AsyncMock()
    mock_data_signaling = AsyncMock()
    mock_input_frames_q = MagicMock()
    mock_shared_predicted_coordinates = MagicMock()

    await run_client(
        mock_media_pc,
        mock_media_signaling,
        mock_data_pc,
        mock_data_signaling,
        mock_input_frames_q,
        mock_shared_predicted_coordinates,
    )

    mock_log_error.assert_called_once_with("Client error: Test exception")

    mock_create_datachannel.assert_not_called()


@pytest.mark.asyncio
@patch("client.setup_remote_track")
@patch("client.wait_for_offer_and_send_answer", new_callable=AsyncMock)
@patch("client.create_datachannel")
@patch("client.send_offer_and_wait_for_answer", new_callable=AsyncMock)
@patch("client.logging.error")
async def test_run_client_success(
    mock_log_error,
    mock_send_offer_and_wait_for_answer,
    mock_create_datachannel,
    mock_wait_for_offer_and_send_answer,
    mock_setup_remote_track,
):
    # Mock the arguments
    mock_media_pc = AsyncMock()
    mock_media_signaling = AsyncMock()
    mock_data_pc = AsyncMock()
    mock_data_signaling = AsyncMock()
    mock_input_frames_q = MagicMock()
    mock_shared_predicted_coordinates = MagicMock()

    # Run the function under test
    await run_client(
        mock_media_pc,
        mock_media_signaling,
        mock_data_pc,
        mock_data_signaling,
        mock_input_frames_q,
        mock_shared_predicted_coordinates,
    )

    # Verify that all the setup and communication functions were called correctly
    mock_setup_remote_track.assert_called_once_with(mock_media_pc, mock_input_frames_q)
    mock_wait_for_offer_and_send_answer.assert_called_once_with(
        mock_media_pc, mock_media_signaling
    )
    mock_create_datachannel.assert_called_once_with(
        mock_data_pc, mock_shared_predicted_coordinates
    )
    mock_send_offer_and_wait_for_answer.assert_called_once_with(
        mock_data_pc, mock_data_signaling
    )
    mock_media_signaling.receive.assert_called_once()
    mock_log_error.assert_not_called()
