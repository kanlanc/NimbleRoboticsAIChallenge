import numpy as np
import cv2
import asyncio
from multiprocessing import Process, Manager
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.signaling import TcpSocketSignaling
from enum import Enum
from scipy.spatial import distance





class BouncingBall:
    def __init__(self, length, width, radius):
        self.validate_parameters(length, width, radius)
        self.length = length
        self.width = width
        self.radius = radius
        self.dx, self.dy = 4,4
        self.x = width // 4
        self.y = length // 3
        self.color = (100, 0, 255)  

    def validate_parameters(self, length, width, radius):
        if not (500 <= length <= 2000 and 500 <= width <= 2000 and 10 <= radius <= 100):
            raise ValueError("One or more parameters are out of bounds.")
        
    def increment_ball(self):
        self.x += self.dx
        self.y += self.dy
        if not (self.radius <= self.x <= self.width - self.radius):
            self.dx *= -1
        if not (self.radius <= self.y <= self.length - self.radius):
            self.dy *= -1

        frame = np.zeros((self.width, self.length, 3), dtype='uint8')
        cv2.circle(frame, (self.x, self.y), self.radius, self.color, -1)
        return frame

    def position(self):
        return self.x, self.y


class ImageFrameTrack(MediaStreamTrack):
    def __init__(self, track):
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        return frame

class Server:
    def __init__(self, ball, video_signal):
        self.peer_conn = RTCPeerConnection()
        self.ball = ball
        self.video_signal = video_signal
        self.queue = Manager().Queue()

    async def setup(self):
        await self.video_signal.connect()
        self.peer_conn.addTrack(ImageFrameTrack())
        await self.peer_conn.setLocalDescription(await self.peer_conn.createOffer())

    async def offer_frame(self):
        frame = self.ball.increment_ball()
        if self.peer_conn:
            track = self.peer_conn.getSenders()[0].track
            track.update_frame(frame)
        


    def run(self):
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.setup())
            while True:
                loop.run_until_complete(self.offer_frame())
                key = cv2.waitKey(1)
                if key == 27:  # Esc key
                    break
        finally:
            loop.run_until_complete(self.peer_conn.close())
            loop.run_until_complete(self.video_signal.close())

if __name__ == "__main__":
    video_signal = TcpSocketSignaling("127.0.0.1", 9001)
    ball = BouncingBall(500, 500, 20)
    server = Server(ball, video_signal)
    server.run()