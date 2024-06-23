# NimbleRoboticsAIChallenge



The ball webrtc works, and the error is being calculated correctly.

Done with the following libraries:

- opencv-python
- numpy
- aiortc
- aiohttp
- scipy
- asyncio


## How to run

Both docker-compose and Kubernetes are supported.

The simplest way to run the server and client is to run the integration_test file.

### Docker-compose

1. Run `docker-compose up` to start the server and client.

2. The server will open a window with the ball moving around. It will also open a window with the error.

### Kubernetes

1. Run `kubectl apply -f kubernetes/` to deploy the server and client.

2. The server will open a window with the ball moving around.



