import logging
import asyncio
from argparse import ArgumentParser

from aiortc import RTCPeerConnection, RTCIceCandidate
from aiortc.contrib.signaling import TcpSocketSignaling


async def wait_for_offer_and_send_answer(
    pc: RTCPeerConnection, signaling: TcpSocketSignaling
):
    """
    Waits for a WebRTC offer, sets it as the remote description, creates an answer, and sends it via the signaling object.

    Args:
        pc: The RTCPeerConnection through which the media will be transmitted.
        signaling: The signaling channel used to exchange SDP information.

    Returns:
        True if the process completes successfully, None if an exception is raised.

    Raises:
        Exception: If there's an issue with setting remote/local descriptions or sending the answer.
    """

    logging.info("Waiting for offer")
    offer = await receive_offer_with_retry(signaling)
    await pc.setRemoteDescription(offer)

    logging.info("Sending answer")
    await pc.setLocalDescription(await pc.createAnswer())
    await signaling.send(pc.localDescription)
    return True


async def send_offer_and_wait_for_answer(
    pc: RTCPeerConnection, signaling: TcpSocketSignaling
):
    """
    Creates a WebRTC offer, sends it, waits for a WebRTC answer, and sets it as the remote description.

    Args:
        pc: The RTCPeerConnection through which the media will be transmitted.
        signaling: The signaling channel used to exchange SDP information.

    Raises:
        Exception: If there's an issue with creating the offer, setting descriptions, or receiving the answer.
    """
    await pc.setLocalDescription(await pc.createOffer())
    logging.info("Sending offer")
    await signaling.send(pc.localDescription)

    logging.info("Waiting for answer")
    answer = await signaling.receive()
    if isinstance(answer, RTCIceCandidate):
        print("ICE boy in send_offer_and_wait_for_answer")

    await pc.setRemoteDescription(answer)


def log_pc_signaling_state_changes(pc: RTCPeerConnection, label: str):
    """
    Attaches a listener to the RTCPeerConnection's signaling state change events.

    Args:
        pc: The RTCPeerConnection object whose signaling state changes are to be logged.
        label: A descriptive label to prefix to log messages for easier identification.
    """

    @pc.on("signalingstatechange")
    async def on_signalingstatechange():
        logging.info(f"{label} PC signaling state changed to: {pc.signalingState}")


async def close_connection(pc: RTCPeerConnection, signaling: TcpSocketSignaling):
    """
    Gracefully closes the RTCPeerConnection and the signaling transport.

    Args:
        pc: The RTCPeerConnection to be closed.
        signaling: The signaling channel to be closed.
    """
    logging.info("Closing connections")
    await pc.close()
    await signaling.close()


async def receive_offer_with_retry(
    signaling: TcpSocketSignaling, retries: int = 20, delay: int = 1
) -> object:
    """
    Attempts to receive an offer through the signaling mechanism, with a specified number of retries
    and a delay between retries in case of connection refusal.

    Args:
        signaling: The signaling object used to receive the offer.
        retries: The number of attempts to make before giving up.
        delay: The delay between retry attempts in seconds.

    Returns:
        The received offer.

    Raises:
        ConnectionRefusedError: If the offer cannot be received after the specified number of retries.
    """
    for attempt in range(retries):
        try:
            return await signaling.receive()
        except ConnectionRefusedError as e:
            logging.warning("Connection refused, retrying...")
            if attempt < retries - 1:
                await asyncio.sleep(delay)
            else:
                logging.error("Failed to receive offer after retries.")
                raise e


def add_connection_arguments(parser: ArgumentParser) -> None:
    """
    Configures an ArgumentParser with common arguments for establishing a connection, including
    host address and ports for data and media channels.

    Args:
        parser: The ArgumentParser instance to which the arguments will be added.
    """
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Server hostname or IP address"
    )
    parser.add_argument("--data_port", type=int, default=1234, help="Data channel port")
    parser.add_argument(
        "--media_port", type=int, default=1235, help="Media channel port"
    )
