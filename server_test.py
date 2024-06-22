# UNIT TESTS
import pytest
import server

def test_bouncing_ball_small_radius_error():
    with pytest.raises(ValueError, match="Invalid ball radius: too small"):
        server.BouncingBall(500, 500, 1)

def test_bouncing_ball_large_radius_error():
    with pytest.raises(ValueError, match="Invalid ball radius: too large"):
        server.BouncingBall(500, 500, 101)

def test_bouncing_ball_small_length_error():
    with pytest.raises(ValueError, match="Invalid window length: too small"):
        server.BouncingBall(100, 500, 20)

def test_bouncing_ball_large_length_error():
    with pytest.raises(ValueError, match="Invalid window length: too large"):
        server.BouncingBall(3000, 500, 20)

def test_bouncing_ball_small_width_error():
    with pytest.raises(ValueError, match="Invalid window width: too small"):
        server.BouncingBall(500, 200, 20)

def test_bouncing_ball_large_width_error():
    with pytest.raises(ValueError, match="Invalid window width: too large"):
        server.BouncingBall(500, 5000, 20)

def test_bouncing_ball_slow_increment():
    ball = server.BouncingBall(500, 500, 20)
    expected_x = 500 // 4
    expected_y = 500 // 3
    assert ball.get_current_position() == (expected_x, expected_y), "Initial position incorrect"
    ball.increment_ball()
    assert ball.get_current_position() == (expected_x + 1, expected_y + 1), "Position after increment incorrect"