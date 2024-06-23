from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils import (
    close_connection,
    receive_offer_with_retry,
    send_offer_and_wait_for_answer,
    wait_for_offer_and_send_answer,
)


@pytest.mark.asyncio
@patch("utils.receive_offer_with_retry", return_value="offer")
async def test_wait_for_offer_and_send_answer_success(mock_receive_offer_with_retry):
    mock_pc = MagicMock()
    mock_pc.setRemoteDescription = AsyncMock()
    mock_pc.createAnswer = AsyncMock(return_value="answer")
    mock_pc.setLocalDescription = AsyncMock()
    mock_pc.localDescription = "answer"

    mock_signaling = AsyncMock()
    mock_signaling.receive = AsyncMock(return_value="offer")
    mock_signaling.send = AsyncMock()

    assert await wait_for_offer_and_send_answer(mock_pc, mock_signaling)
    mock_pc.setRemoteDescription.assert_awaited_once_with("offer")
    mock_pc.setLocalDescription.assert_awaited_once_with("answer")
    mock_signaling.send.assert_awaited_once_with("answer")


@pytest.mark.asyncio
@patch(
    "utils.receive_offer_with_retry",
    side_effect=Exception("Test exception while wating for answer"),
)
async def test_wait_for_offer_and_send_answer_failure(mock_receive_offer_with_retry):
    mock_pc = MagicMock()
    mock_pc.setRemoteDescription = AsyncMock()
    mock_pc.createAnswer = AsyncMock(return_value="answer")
    mock_pc.setLocalDescription = AsyncMock()
    mock_pc.localDescription = "answer"

    mock_signaling = AsyncMock()
    mock_signaling.receive = AsyncMock(return_value="offer")
    mock_signaling.send = AsyncMock()

    with pytest.raises(Exception, match="Test exception while wating for answer"):
        await wait_for_offer_and_send_answer(mock_pc, mock_signaling)

    mock_pc.setRemoteDescription.assert_not_called()
    mock_pc.setLocalDescription.assert_not_called()
    mock_signaling.send.assert_not_called()


@pytest.mark.asyncio
async def test_send_offer_and_wait_for_answer_success(mock_pc, mock_signaling):
    mock_offer = AsyncMock()
    mock_pc.createOffer.return_value = mock_offer

    mock_answer = AsyncMock()
    mock_signaling.receive.return_value = mock_answer

    await send_offer_and_wait_for_answer(mock_pc, mock_signaling)

    mock_pc.setLocalDescription.assert_awaited_once_with(mock_offer)
    mock_signaling.send.assert_awaited_once_with(mock_pc.localDescription)
    mock_signaling.receive.assert_awaited_once()
    mock_pc.setRemoteDescription.assert_awaited_once_with(mock_answer)


@pytest.mark.asyncio
async def test_send_offer_and_wait_for_answer_failure(mock_pc, mock_signaling):
    mock_pc.createOffer.side_effect = Exception("Test exception during offer creation")

    with pytest.raises(Exception, match="Test exception during offer creation"):
        await send_offer_and_wait_for_answer(mock_pc, mock_signaling)

    mock_pc.setLocalDescription.assert_not_called()
    mock_signaling.send.assert_not_called()
    mock_signaling.receive.assert_not_called()
    mock_pc.setRemoteDescription.assert_not_called()


@pytest.mark.asyncio
async def test_close_connection(mock_pc, mock_signaling):
    await close_connection(mock_pc, mock_signaling)

    mock_pc.close.assert_awaited_once()
    mock_signaling.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_receive_offer_with_retry_success(mock_signaling):
    mock_signaling.receive = AsyncMock(return_value="offer")

    offer = await receive_offer_with_retry(mock_signaling)
    assert offer == "offer"


@pytest.mark.asyncio
async def test_receive_offer_with_retry_failure(mock_signaling):
    mock_signaling = AsyncMock()
    mock_signaling.receive = AsyncMock(
        side_effect=ConnectionRefusedError("Connection refused")
    )

    with pytest.raises(ConnectionRefusedError, match="Connection refused"):
        await receive_offer_with_retry(mock_signaling, retries=1, delay=1)
