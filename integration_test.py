import docker_client.client as client, docker_server.server as server

import cv2

from multiprocessing import Process,  Manager

import time


def test_ball_moving():
    
    ball = server.BouncingBall(500, 500, 20)
    start_time = time.time()  # Get the start time

    while True:
        current_time = time.time()
        if current_time - start_time > 5:  # Check if 5 seconds have passed
            break

        updated_ball = ball.increment_ball()
        cv2.startWindowThread()
        cv2.imshow('screensaver', updated_ball)
        key = cv2.waitKey(1)
        if key == 27:  # Check for ESC key (ASCII value of ESC is 27)
            break

    cv2.destroyAllWindows()  # Make sure to destroy all windows
    assert True


def test_error_finding():
    queue_a = Manager().Queue()
    queue_b = Manager().Queue()
    queue_c = Manager().Queue()

    ball = server.BouncingBall(500, 500, 20)
    new_ball_img = ball.increment_ball()

    queue_a.put(new_ball_img)

    p1 = Process(target=client.process_images, args=(queue_a, queue_b,))
    p1.start()
    p2 = Process(target=server.calculate_error, args=(ball, queue_b, queue_c,))
    p2.start()

    p1.join()
    p2.join()

    dist_error = queue_c.get()
    assert dist_error < 10.0



if __name__ == '__main__':
    # test_ball_moving()
    test_error_finding()