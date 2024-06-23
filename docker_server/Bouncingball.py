
import numpy as np
import cv2
from multiprocessing import Process, Manager
from aiortc.contrib.signaling import TcpSocketSignaling


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