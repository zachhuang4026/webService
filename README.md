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


**Push Container to Docker Hub**
```bash
# Create image
docker commit 72b5f88a7e0d adamlim1/flask_server
# Push image to Docker Hub
docker image push adamlim1/flask_server
# Pull image
docker run -it -p 5000:5000 --net ebay --ip 172.20.0.2 --name FlaskServer adamlim1/flask_server:latest
```

# ToDo

- Flesh out endpoints in all API Gateway


- Add to watch list / get watch list
- ADMIN POST from report item page????
- emails???
- Shipping cost
- Quantity?
- User: delete listing
- Update tables showing auction info with all feilds we want
- If auction status is sold, do not allow bids
 

- Integration of shopping service 
- UI for sending/receiving emails
 
Required API Gateway Integrations:
Sending Info to API Gateway:
Checkout - Process checkout ✅
Auctions - Add new item / auction 🟨
Auctions - update auction info (e.g. end early or delete if no bids) 🟨
Auctions - Place bid on auction or buy now 🟨
Watchlist - Add/remove item to account's watch list ✅
Report Item - Label item as reported with reason 🟨
Item Categories - Add new category or delete current category 🟨

Requesting Info from API gateway:
Auctions - Get list of auctions based on seller, status (active vs. closed), or description/category matching criteria (Return Auction ID, Item name, Category, current price, # bids, end time, status) 🟨
Auctions - Get information for specific auction_id (item name, current price, type (auction vs. buy now), item details, category) 🟨
Cart - Get list of items in users cart (Auction ID, Item name, Category, current price, # bids, end time) 🟨
Watchlist - Get list items on watchlist (Auction ID, Item name, Category, current price, # bids, end time) ✅
Item Categories - Get list of categories 🟨
Reported Items - Get list of reported items 🟨