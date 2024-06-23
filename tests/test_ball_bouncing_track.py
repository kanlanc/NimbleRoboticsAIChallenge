import fractions
from unittest.mock import patch

import av
import numpy as np
import pytest

from ball_bouncing_track import Ball, BallBouncingTrack


def test_ball_initialization():
    test_radius = 5
    test_color = (255, 0, 0)

    ball = Ball(test_radius, test_color)

    assert ball.radius == test_radius
    assert ball.color == test_color


@pytest.fixture
def default_bouncing_ball_track():
    return BallBouncingTrack(screen_width=800, screen_height=600)


def test_initialization(default_bouncing_ball_track):
    track = default_bouncing_ball_track
    assert track.width == 800
    assert track.height == 600
    assert isinstance(track.ball, Ball)
    assert np.array_equal(track.velocity, np.array([15, -10]))
    assert np.array_equal(track.coordinates, np.array([400, 300]))


def test_reset_ball_position(default_bouncing_ball_track):
    track = default_bouncing_ball_track
    track.coordinates = np.array([100, 100])
    track.reset_ball_position()
    assert np.array_equal(
        track.coordinates, np.array([track.width // 2, track.height // 2])
    )


def test_update_ball_position(default_bouncing_ball_track):
    track = default_bouncing_ball_track
    initial_coordinates = track.coordinates.copy()
    track.update_ball_position()

    # Initial velocity moves the ball right and up
    assert track.coordinates[0] > initial_coordinates[0]
    assert track.coordinates[1] < initial_coordinates[1]

    # Simulate collision with the right wall
    track.coordinates = np.array([780, 300])
    track.update_ball_position()
    assert track.velocity[0] < 0


def test_get_current_frame(default_bouncing_ball_track):
    frame = default_bouncing_ball_track.get_current_frame()
    assert frame.shape == (600, 800, 3)


@pytest.mark.asyncio
async def test_recv(default_bouncing_ball_track):
    frame = await default_bouncing_ball_track.recv()
    assert isinstance(frame, av.VideoFrame)


@pytest.mark.asyncio
async def test_next_timestamp_initial_call():
    track = BallBouncingTrack(screen_width=640, screen_height=480)

    with patch("ball_bouncing_track.time.time", return_value=1000):
        timestamp, time_base = await track.next_timestamp()

    assert timestamp == 0
    assert time_base == fractions.Fraction(1, 90000)


@pytest.mark.asyncio
async def test_next_timestamp_subsequent_calls():
    track = BallBouncingTrack(screen_width=640, screen_height=480)

    track._start = 1000
    track._timestamp = 0

    with patch("ball_bouncing_track.time.time", return_value=1000.033):
        timestamp, _ = await track.next_timestamp()

    expected_timestamp_increase = int((1 / 30) * 90000)
    assert timestamp == expected_timestamp_increase
