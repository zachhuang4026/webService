**Creating Docker Container for Flask Server**
```bash
# This process for creating Flask Container needs improved
docker run -it -p 5000:5000 --name FlaskServer alpine
apk add --update python3 py3-pip
pip install flask
pip install PyJWT # https://stackoverflow.com/questions/33198428/jwt-module-object-has-no-attribute-encode

docker exec -it FlaskServer /bin/sh
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

