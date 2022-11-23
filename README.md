**Creating Docker Container for Flask Server**
```bash
# Create container on ebay network with static IP. Map localhost:5000 to container port 5000
docker run -it -p 5000:5000 --net ebay --ip 172.20.0.2 --name FlaskServer alpine
apk add --update python3 py3-pip
pip install flask
pip install PyJWT # https://stackoverflow.com/questions/33198428/jwt-module-object-has-no-attribute-encode
pip install requests

docker exec -it FlaskServer /bin/sh
```
**Copying Files to Docker Container**
```bash
# From local
docker cp webService FlaskServer:/.
```

**Running Flask Web App**
```bash
# Copy files from local to Docker container
cp webService FlaskServer:/.
# Exec into Docker container
docker exec -it FlaskServer /bin/sh
cd /webService
python3 app.py
```


**Create JWT Token**
```python
import jwt
from datetime import datetime, timedelta
token = jwt.encode({'public_id':19, 'exp':datetime.utcnow() + timedelta(minutes=30)}, 'your secret key')
```
- Include in request header as {'x-access-token': token}

Python decorator with arguments
https://stackoverflow.com/questions/10176226/how-do-i-pass-extra-arguments-to-a-python-decorator

# ToDo
- Import dummy data from configs
- Display auction start/end times
- Admin analytics page
- Watch list: add/remove items
