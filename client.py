import asyncio
import cv2
import numpy as np
from multiprocessing import Process, Manager
from aiortc import RTCPeerConnection
from aiortc.contrib.signaling import TcpSocketSignaling



class Client:
    def __init__(self):
        self.queue_images = Manager().Queue()
        self.queue_centers = Manager().Queue()
        self.peer_conn = RTCPeerConnection()
        self.setup_client()

    async def setup_client(self):

        image_signal = TcpSocketSignaling("127.0.0.1", 9001)
        cordinate_signal = TcpSocketSignaling("127.0.0.1", 9002)


        await image_signal.connect()
        await cordinate_signal.connect()
        self.peer_conn.on("datachannel", self.on_datachannel)

    async def receive_frame(self):
        answer = await self.peer_conn.createAnswer()
        await self.peer_conn.setLocalDescription(answer)
        self.queue_images.put(answer.sdp)

    def on_datachannel(self, channel):
        channel.on("message", self.on_message)

    def on_message(self, message):
        self.queue_centers.put(message)

def process_images(input_queue, output_queue):
    while True:
        if not input_queue.empty():
            image = input_queue.get()
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, image.shape[0] / 4,
                                       param1=100, param2=10, minRadius=10, maxRadius=100)
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                for (x, y, r) in circles:
                    output_queue.put((x, y))

async def send_coordinates(peer_conn, queue):
    channel = peer_conn.createDataChannel("cordinates")
    while True:
        if not queue.empty():
            message = queue.get()
            channel.send(str(message))
            await asyncio.sleep(1)

async def run_client(client):
    await client.setup_client()
    await client.receive_frame()

if __name__ == '__main__':
    client = Client()
    process = Process(target=process_images, args=(client.queue_images, client.queue_centers))
    process.start()
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run_client(client))
        loop.run_until_complete(send_coordinates(client.peer_conn, client.queue_centers))
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(client.peer_conn.close())
        process.join()