import numpy as np
import cv2
import asyncio
from multiprocessing import Process, Manager
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.signaling import TcpSocketSignaling
from enum import Enum
from scipy.spatial import distance





class BouncingBall:

    def __init__(self, window_length, window_width, ball_radius):
       
        super().__init__()
        self.speed_x = 4
        self.speed_y = 4
        self.window_length = window_length
        self.window_width = window_width
        self.ball_radius = ball_radius
        self.ball_color = (100, 0, 255) 
        self.pos_x = int(window_width / 4)
        self.pos_y = int(window_length / 3)

    def increment_ball(self):
        """
        This method will give a new image where the position of the ball is updated
        based on the balls speed set during initialisation and direction (based on the previous movement)
        
        """
        black_bkgd = np.zeros((self.window_width, self.window_length, 3), dtype='uint8')

        # update the ball position
        self.pos_x = self.pos_x + self.speed_x
        self.pos_y = self.pos_y + self.speed_y

        img_with_circle = cv2.circle(black_bkgd, (self.pos_x, self.pos_y), self.ball_radius, self.ball_color, -1)

        # update the directions if the ball hits a wall
        if self.pos_x + self.ball_radius >= self.window_width:
            self.speed_x *= -1
        elif self.pos_x - self.ball_radius <= 0:
            self.speed_x *= -1
        if self.pos_y + self.ball_radius >= self.window_length:
            self.speed_y *= -1
        elif self.pos_y - self.ball_radius <= 0:
            self.speed_y *= -1

        return img_with_circle

    def get_current_position(self):
        """
        Returns the current (x, y) coordinates of where the ball is within the boundary box
        :return:
        """
        return self.pos_x, self.pos_y


class ImageFrameTrack(MediaStreamTrack):
    def __init__(self, track):
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        return frame


async def get_coordinates_estimation(peer_conn, signaling, queue_a):
    await signaling.connect()

    @peer_conn.on("datachannel")
    def on_datachannel(channel):

        @channel.on("message")
        def on_message(message):
            queue_a.put(message)

    await consume_signaling(peer_conn, signaling)


async def consume_signaling(peer_conn, signaling):
    while True:
        obj = await signaling.receive()

        if isinstance(obj, RTCSessionDescription):
            await peer_conn.setRemoteDescription(obj)

            await peer_conn.setLocalDescription(await peer_conn.createAnswer())
            await signaling.send(peer_conn.localDescription)
        elif isinstance(obj, RTCIceCandidate):
            peer_conn.addIceCandidate(obj)


def calculate_error(actual_ball, queue_a, debug_queue=None):
    """
    Calculates the error between the clients guesses placed on the queue
    """
    while True:
        if not queue_a.empty():
            estimation = queue_a.get()
            real_position = actual_ball.get_current_position()
            dist_error = distance.euclidean(real_position, estimation)
            display_error(dist_error)
            if debug_queue is not None:
                debug_queue.put(dist_error)


def display_error(dist_error):
    """
    Displays the error as a opencv Window. The error is written into the bottom left corner of the window.
    :param dist_error: Error to be written
    :return:
    """
    error_img = np.zeros((500, 500, 3), np.uint8)
    bottom_left_corner = (10, 500)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    font_color_white = (255, 255, 255)
    line_type = 2
    cv2.putText(error_img, str(dist_error), bottom_left_corner, font, font_scale, font_color_white, line_type)

    window_name = "error"
    cv2.namedWindow(window_name)
    cv2.startWindowThread()
    cv2.imshow(window_name, error_img)
    cv2.waitKey(1000)
    cv2.destroyAllWindows()  # note opencv has a bug on Unix where windows may not close
    cv2.waitKey(1)


def asyncio_run(pc, signaling, correspondence):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(correspondence)
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(pc.close())
        loop.run_until_complete(signaling.close())



class Server:

    def __init__(self,peer_conn):
        self.peer_conn = peer_conn

    async def setup(self):
        offer = TcpSocketSignaling("127.0.0.1", 9001)
        await offer.connect()
        self.peer_conn.addTrack(ImageFrameTrack())
        await self.peer_conn.setLocalDescription(await self.peer_conn.createOffer())

    async def offer_frame(self,frame):
        # frame = self.ball.increment_ball()
        if self.peer_conn:
            track = self.peer_conn.getSenders()[0].track
            track.update_frame(frame)
    
    # async def offer_frame(peer_conn, image_frame):
    #     offer = TcpSocketSignaling("127.0.0.1", 9001)
    #     await offer.connect()

    #     peer_conn.addTrack(ImageFrameTrack(image_frame))
    #     await peer_conn.setLocalDescription(await peer_conn.createOffer())

    async def run(self, bouncing_ball):
        await self.setup_connection()
        while True:
            self.offer_frame(bouncing_ball.increment_ball())
            await asyncio.sleep(1/30) 

 




if __name__ == "__main__":

    coordinates_signal = TcpSocketSignaling("127.0.0.1", 9002)
   

    peer_conn = RTCPeerConnection()
    
    server = Server(peer_conn)
    ball = BouncingBall(500, 500, 20)
    q1 = Manager().Queue()

    coro = get_coordinates_estimation(peer_conn, coordinates_signal, q1)

    p1 = Process(target=calculate_error, args=(ball, q1,))
    p2 = Process(target=asyncio_run, args=(peer_conn, coordinates_signal, coro,))

    while True:
        new_ball_position = ball.increment_ball()
        # server.offer_frame(peer_conn, new_ball_position)
        server.run(ball)
        key = cv2.waitKey(1)
        if key == '27':  # esc key
            break

    p1.join()
    p2.join()