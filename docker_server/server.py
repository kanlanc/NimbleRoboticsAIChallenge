import numpy as np
import cv2
import asyncio
from multiprocessing import Process, Manager
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.signaling import TcpSocketSignaling
from enum import Enum
from scipy.spatial import distance








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
            print(f"Received message from client: {message}")

    while True:
        obj = await signaling.receive()

        if isinstance(obj, RTCSessionDescription):
            await peer_conn.setRemoteDescription(obj)

            await peer_conn.setLocalDescription(await peer_conn.createAnswer())
            await signaling.send(peer_conn.localDescription)

            
        elif isinstance(obj, RTCIceCandidate):
            peer_conn.addIceCandidate(obj)    


def calculate_error_and_display(actual_ball, queue_a, debug_queue=None):
    """
    Calculates the error between the clients guesses placed on the queue
    """
    while True:
        if not queue_a.empty():
            estimation = queue_a.get()
            real_position = actual_ball.get_current_position()
            dist_error = distance.euclidean(real_position, estimation)

            # Display the error as a opencv Window. The error is written into the bottom left corner of the window.
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

            if debug_queue is not None:
                debug_queue.put(dist_error)



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

    coordinates_signal = TcpSocketSignaling("0.0.0.0", 9002)
   

    peer_conn = RTCPeerConnection()
    
    server = Server(peer_conn)

    @peer_conn.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print(f"ICE Connection State has changed to {peer_conn.iceConnectionState}")
        if peer_conn.iceConnectionState == "failed" or peer_conn.iceConnectionState == "disconnected":
            print("Connection Failed. Closing peer connection.")
            await peer_conn.close()


    ball = BouncingBall(500, 500, 20)
    q1 = Manager().Queue()

    coro = get_coordinates_estimation(peer_conn, coordinates_signal, q1)

    p1 = Process(target=calculate_error_and_display, args=(ball, q1,))
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