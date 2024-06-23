import asyncio
import fractions
import time
from typing import Tuple

import av
import cv2
import numpy as np
from aiortc import MediaStreamTrack


class Ball:
    """
    Represents a ball with a radius and color.

    Attributes:
        radius (int): The radius of the ball.
        color (Tuple[int, int, int]): The color of the ball in BGR format.
    """

    def __init__(self, radius, color):
        """
        Initializes a new instance of the Ball class.

        Args:
            radius (int): The radius of the ball.
            color (Tuple[int, int, int]): The color of the ball in BGR format.
        """
        self.radius = radius
        self.color = color


class BallBouncingTrack(MediaStreamTrack):
    """
    A MediaStreamTrack that generates video frames of a ball bouncing within a rectangular area.
    """

    kind = "video"
    _start: float
    _timestamp: int

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        ball_radius: int = 20,
        ball_color: Tuple[int, int, int] = (0, 0, 255),
        initial_velocity: Tuple[int, int] = (15, -10),
    ):
        """
        Initializes a new instance of the BouncingBallTrack class.

        Args:
            screen_width (int): The width of the screen in pixels.
            screen_height (int): The height of the screen in pixels.
            ball_radius (int, optional): The radius of the ball. Defaults to 20.
            ball_color (Tuple[int, int, int], optional): The color of the ball in BGR format. Defaults to (0, 0, 255).
            initial_velocity (Tuple[int, int], optional): The initial velocity of the ball in pixels per frame. Defaults to (15, -10).
        """
        super().__init__()
        self.width = screen_width
        self.height = screen_height
        self.ball = Ball(ball_radius, ball_color)
        self.velocity = np.array(initial_velocity)
        self.reset_ball_position()

    def reset_ball_position(self) -> None:
        """Resets the ball's position to the center of the screen."""
        self.coordinates = np.array([self.width // 2, self.height // 2])

    def update_ball_position(self) -> None:
        """
        Updates the ball's position based on its velocity, reversing direction upon collision with the screen edges.
        """
        self.coordinates += self.velocity

        # Check for collisions with screen edges and reverse velocity
        for i in range(2):
            if (
                self.coordinates[i] - self.ball.radius <= 0
                or self.coordinates[i] + self.ball.radius
                >= [self.width, self.height][i]
            ):
                self.velocity[i] *= -1

    async def next_timestamp(self) -> Tuple[int, fractions.Fraction]:
        """
        Calculates the next timestamp for the video frame, ensuring a consistent frame rate.

        Returns:
            Tuple[int, fractions.Fraction]: The next timestamp and the time base.
        """
        VIDEO_CLOCK_RATE = 90000
        VIDEO_PTIME = 1 / 30  # 30fps
        VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)

        if hasattr(self, "_timestamp"):
            self._timestamp += int(VIDEO_PTIME * VIDEO_CLOCK_RATE)
            wait = self._start + (self._timestamp / VIDEO_CLOCK_RATE) - time.time()
            await asyncio.sleep(wait)
        else:
            self._start = time.time()
            self._timestamp = 0

        return self._timestamp, VIDEO_TIME_BASE

    def get_current_frame(self) -> np.ndarray:
        """
        Generates the current video frame displaying the ball at its current position.

        Returns:
            np.ndarray: The current video frame as a NumPy array.
        """
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cv2.circle(
            frame,
            tuple(self.coordinates.astype(int)),  # type: ignore
            self.ball.radius,  # type: ignore
            self.ball.color,
            -1,
        )
        return frame

    async def recv(self) -> av.VideoFrame:
        """
        Updates the ball's position, generates the next video frame, and returns it.

        Returns:
            av.VideoFrame: The next video frame.
        """
        self.update_ball_position()
        frame = self.get_current_frame()

        video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        pts, time_base = await self.next_timestamp()
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame
