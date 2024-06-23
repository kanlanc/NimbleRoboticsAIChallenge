import argparse
import asyncio
import json
import logging

import numpy as np
from aiortc import RTCPeerConnection, RTCDataChannel
from aiortc.contrib.signaling import TcpSocketSignaling

from ball_bouncing_track import BallBouncingTrack
from utils import (
    add_connection_arguments,
    close_connection,
    log_pc_signaling_state_changes,
    send_offer_and_wait_for_answer,
    wait_for_offer_and_send_answer,
)

logging.basicConfig(level=logging.INFO)


def distance_between(pred_coordinates: np.array, actual_coordinates: np.array) -> float:
    """Calculate the Euclidean distance between two points."""
    return np.linalg.norm(pred_coordinates - actual_coordinates)


def on_message(message: str, actual_coordinates: np.array) -> None:
    """Handles incoming messages on the data channel."""
    try:
        pred_coordinates = np.array(json.loads(message))
        error_distance = distance_between(pred_coordinates, actual_coordinates)
        logging.info(f"Prediction Error (distance): {error_distance}")
    except (json.JSONDecodeError, ValueError) as e:
        logging.error(f"Invalid data received on data channel: {e}")


def setup_data_channel(pc: RTCPeerConnection, track: BallBouncingTrack) -> None:
    """Configures the data channel for receiving messages."""

    @pc.on("datachannel")
    def on_datachannel(channel: RTCDataChannel):
        logging.info(f"Channel {channel.label} created ")
        channel.on("message", lambda msg: on_message(msg, track.coordinates))


async def run_server(
    media_pc: RTCPeerConnection,
    media_signaling: TcpSocketSignaling,
    data_pc: RTCPeerConnection,
    data_signaling: TcpSocketSignaling,
) -> None:
    """
    Sets up the server to handle WebRTC connections for video streaming and data communication.

    Args:
        media_pc: The PeerConnection for media streaming.
        media_signaling: The signaling channel for the media connection.
        data_pc: The PeerConnection for data communication.
        data_signaling: The signaling channel for the data connection.
    """

    try:
        track = BallBouncingTrack(640, 480)
        media_pc.addTrack(track)
        await send_offer_and_wait_for_answer(media_pc, media_signaling)

        setup_data_channel(data_pc, track)
        await wait_for_offer_and_send_answer(data_pc, data_signaling)

        await media_signaling.receive()
    except Exception as e:
        logging.error(f"Server error: {e}")


async def cleanup(
    media_pc,
    data_pc,
    media_signaling,
    data_signaling,
):
    """
    Closes all active connections and signaling channels in an orderly manner.

    Args:
        media_pc: The PeerConnection for media streaming.
        media_signaling: The signaling channel for the media connection.
        data_pc: The PeerConnection for data communication.
        data_signaling: The signaling channel for the data connection.
    """

    logging.info("Cleaning up")
    await close_connection(media_pc, media_signaling)
    await close_connection(data_pc, data_signaling)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_connection_arguments(parser)
    args = parser.parse_args()

    media_pc = RTCPeerConnection()
    data_pc = RTCPeerConnection()
    log_pc_signaling_state_changes(media_pc, "Media")
    log_pc_signaling_state_changes(data_pc, "Data")
    media_signaling = TcpSocketSignaling("0.0.0.0", args.media_port)
    data_signaling = TcpSocketSignaling(args.host, args.data_port)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            run_server(media_pc, media_signaling, data_pc, data_signaling)
        )
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(
            cleanup(
                media_pc,
                data_pc,
                media_signaling,
                data_signaling,
            )
        )
