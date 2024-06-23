# Usage
## Running locally
1. Install requirements
```
pip install -r requirements.txt
```

2. Run server 
```
python server.py
```
3. Run client
```
python client.py
```
## Running on minikube
1. First install and configure minikube [(guide)](https://minikube.sigs.k8s.io/docs/start/)
2. Use minikube's docker instance
```
eval $(minikube docker-env)
```
3. Build images
```
 docker build -f docker/Dockerfile.server --tag 'nimble-server-image' .
 docker build -f docker/Dockerfile.client --tag 'nimble-client-image' .
```
4. Deploy to minikube
```
kubectl apply -f deployment/server-deployment.yaml
kubectl apply -f deployment/client-deployment.yaml
```

5. Check status on dashboard
```
minikube dashboard
```

## Running tests
1. Install dev dependencies
```
pip install -r requirements-dev
```
2. Run test
```
pytest
```

