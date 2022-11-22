**Creating Docker Container for Flask Server**
```bash
# This process for creating Flask Container needs improved
docker run -it -p 5000:5000 --net ebay --name FlaskServer alpine
apk add --update python3 py3-pip
pip install flask
pip install PyJWT # https://stackoverflow.com/questions/33198428/jwt-module-object-has-no-attribute-encode
pip install requests
pip install PyYAML

docker exec -it FlaskServer /bin/sh
```

**Creating and Connecting to Docker Network**
```bash
# Create network
docker network create ebay
docker network connect --ip 172.20.0.2 ebay FlaskServer
docker network connect --ip 172.20.0.3 ebay FlaskServer
docker network connect --ip 172.20.0.4 ebay AccountService

# View containers connected to network
docker network inspect ebay
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

https://www.tutorialworks.com/container-networking/#:~:text=For%20containers%20to%20communicate%20with,use%20to%20address%20each%20other.