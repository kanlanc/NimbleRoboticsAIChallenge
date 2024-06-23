import argparse
import cv2
import asyncio
import json
import logging
import multiprocessing as mp
import queue
from ctypes import Structure, c_int
import numpy as np
from aiortc import (
    RTCDataChannel,
    RTCPeerConnection,
)
from aiortc.contrib.signaling import TcpSocketSignaling
from aiortc.mediastreams import MediaStreamError
from aiortc.rtcrtpreceiver import RemoteStreamTrack

from utils import (
    add_connection_arguments,
    close_connection,
    log_pc_signaling_state_changes,
    wait_for_offer_and_send_answer,
    send_offer_and_wait_for_answer,
)
import os

DISPLAY_IMAGES = os.environ.get(
    "DISPLAY_IMAGES", "True"
)  # Set to "False" in production environment

logging.basicConfig(level=logging.INFO)


class Coordinates(Structure):
    """
    A ctypes Structure for shared memory storage of ball coordinates.
    """

    _fields_ = [("x", c_int), ("y", c_int)]


def predict_coordinates(img: np.ndarray) -> np.ndarray:
    """
    Predicts the ball's position by finding the mean coordinates of the brightest area in the image.

    Args:
        img: The image array in which to predict the ball's position.

    Returns:
        A numpy array containing the x and y coordinates of the predicted ball position.
    """
    img[img < 128] = 0
    img = img.sum(axis=2)
    idxes = np.nonzero(img)
    return np.mean(idxes, axis=1)[::-1].astype(int)


def process_frames(
    input_frames_q: mp.Queue, shared_predicted_coordinates: mp.Value
) -> None:
    """
    Continuously processes video frames from a queue to predict ball coordinates.

    Args:
        input_frames_q: A multiprocessing queue from which video frames are received.
        shared_predicted_coordinates: A shared memory value for storing predicted coordinates.
    """
    try:
        while True:
            try:
                frame = input_frames_q.get(timeout=5)
            except queue.Empty:
                logging.warning("Queue is empty")
                continue

            if frame is None:
                break
            coordinates = predict_coordinates(frame)
            with shared_predicted_coordinates.get_lock():
                shared_predicted_coordinates.x, shared_predicted_coordinates.y = (
                    coordinates
                )

    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Frame processing subprocess exited.")


async def consume_frames(
    track: RemoteStreamTrack, input_frames_q: mp.Queue, pc: RTCPeerConnection
) -> None:
    """
    Consumes frames from a video track and enqueues them for processing.

    Args:
        track: The remote video track from which frames are received.
        input_frames_q: The multiprocessing queue to which video frames are enqueued.
        pc: The RTCPeerConnection associated with the track.
    """
    while True:
        try:
            video_frame = await track.recv()
            logging.info("Frame received")
            frame = video_frame.to_ndarray(format="bgr24")
            input_frames_q.put(frame)
            if DISPLAY_IMAGES == "True":
                cv2.imshow("Received bouncing ball stream", frame)
                cv2.waitKey(1)
        except MediaStreamError as e:
            await asyncio.sleep(0.1)  # pausing to allow pending closing of connections
            if pc.signalingState == "closed":
                break
            else:
                raise e


def setup_remote_track(pc: RTCPeerConnection, input_frames_q: mp.Queue):
    """
    Configures handling for incoming video tracks on the PeerConnection.

    Args:
        pc: The RTCPeerConnection to configure.
        input_frames_q: The queue to use for incoming video frames.
    """

    @pc.on("track")
    async def on_track(track: RemoteStreamTrack):
        if track.kind != "video":
            logging.error(f"Recieved track of incompatible kind {track.kind}")
            return
        logging.info("Recieved video track")
        asyncio.ensure_future(consume_frames(track, input_frames_q, pc))


def create_datachannel(
    pc: RTCPeerConnection, shared_predicted_coordinates: mp.Value
) -> RTCDataChannel:
    """
    Creates and configures a data channel for sending predicted ball coordinates.

    Args:
        pc: The RTCPeerConnection over which the data channel is created.
        shared_predicted_coordinates: Shared memory object for reading predicted coordinates.

    Returns:
        The created RTCDataChannel.
    """
    channel = pc.createDataChannel("ball_coordinates")

    @channel.on("open")
    async def on_open():
        logging.info(f"Data Channel: {channel.label} opened")
        asyncio.ensure_future(
            send_predicted_coordinates(channel, shared_predicted_coordinates, pc)
        )

    return channel


async def send_predicted_coordinates(
    channel: RTCDataChannel, shared_predicted_coordinates: mp.Value, pc: RTCDataChannel
) -> None:
    """
    Periodically sends the predicted ball coordinates over the data channel.

    Args:
        channel: The RTCDataChannel through which the coordinates are sent.
        shared_predicted_coordinates: The shared memory object from which coordinates are read.
    """
    while True:
        await asyncio.sleep(0.1)
        if channel.readyState != "open":
            logging.info("Channel closed")
            break
        x, y = shared_predicted_coordinates.x, shared_predicted_coordinates.y
        if x == -1 or y == -1:
            continue
        logging.info(f"Sending predicted ball coordinates: {x}, {y}")
        channel.send(json.dumps((x, y)))


async def run_client(
    media_pc: RTCPeerConnection,
    media_signaling: TcpSocketSignaling,
    data_pc: RTCPeerConnection,
    data_signaling: TcpSocketSignaling,
    input_frames_q: mp.Queue,
    shared_predicted_coordinates: mp.Value,
):
    """
    Sets up the client to handle WebRTC connections for video streaming and data communication.

    Args:
        media_pc: The PeerConnection for media streaming.
        media_signaling: The signaling channel for the media connection.
        data_pc: The PeerConnection for data communication.
        data_signaling: The signaling channel for the data connection.
        input_frames_q: The queue to use for incoming video frames.
        shared_predicted_coordinates: The shared memory object used to store/read the predicted coordinates.
    """
    try:
        setup_remote_track(media_pc, input_frames_q)
        await wait_for_offer_and_send_answer(media_pc, media_signaling)

        create_datachannel(data_pc, shared_predicted_coordinates)
        await send_offer_and_wait_for_answer(data_pc, data_signaling)

        await media_signaling.receive()  # waiting for BYE
    except Exception as e:
        logging.error(f"Client error: {e}")


async def cleanup(
    media_pc, data_pc, media_signaling, data_signaling, input_frames_q, process_a
):
    logging.info("Cleaning up")
    input_frames_q.put(None)
    process_a.join()

    await close_connection(media_pc, media_signaling)
    await close_connection(data_pc, data_signaling)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_connection_arguments(parser)
    args = parser.parse_args()

    input_frames_q = mp.Queue(maxsize=100)
    shared_predicted_coordinates = mp.Value(Coordinates, -1, -1, lock=True)
    process_a = mp.Process(
        target=process_frames,
        name="process_a",
        args=(input_frames_q, shared_predicted_coordinates),
    )
    process_a.start()

    media_pc = RTCPeerConnection()
    data_pc = RTCPeerConnection()
    log_pc_signaling_state_changes(media_pc, "Media")
    log_pc_signaling_state_changes(data_pc, "Data")
    media_signaling = TcpSocketSignaling(args.host, args.media_port)
    data_signaling = TcpSocketSignaling("0.0.0.0", args.data_port)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            run_client(
                media_pc,
                media_signaling,
                data_pc,
                data_signaling,
                input_frames_q,
                shared_predicted_coordinates,
            )
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
                input_frames_q,
                process_a,
            )
        )
