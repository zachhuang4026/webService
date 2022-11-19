import sys
from flask import Flask, render_template, request, jsonify, make_response, redirect, url_for, session
from functools import wraps
import jwt
from datetime import datetime, timedelta

# Alternative approach to JWT
# from flask_jwt_extended import create_access_token

app = Flask(__name__)

# Define secret key for encoding/decoding JWT tokens
# ToDo - move this to env file
app.config['SECRET_KEY'] = 'your secret key'
app.config['DEBUG'] = True

from decorators import TokenDecorator # #token_required, token_optional,
# https://www.geeksforgeeks.org/using-jwt-for-user-authentication-in-flask/
# decorator for verifying the JWT
# def #token_required(f):
#     @wraps(f)
#     def decorated(*args, **kwargs):
#         token = None
#         # jwt is passed in the request cookies or header
#         if 'x-access-token' in request.cookies:
#             token = request.cookies['x-access-token']
#         elif 'x-access-token' in request.headers:
#             token = request.headers['x-access-token']
#         print(token)

#         if not token: # No token provided
#             response = make_response(redirect(url_for('login')))
#             response.set_cookie('callback', url_for(f.__name__)) # set cookie to return to intended page
#             return response
  
#         try:
#             # decoding the payload to fetch the stored details
#             data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
#             userid = data['userid']
        
#         except: # If not logged in, redirect
#             response = make_response(redirect(url_for('login')))
#             response.set_cookie('callback', url_for(f.__name__)) # set cookie to return to intended page
#             return response
#         # returns the current logged in users context to the routes
#         return f(userid, *args, **kwargs) # f(current_user, *args, **kwargs)
#     return decorated

# def token_optional(f):
#     @wraps(f)
#     def decorated(*args, **kwargs):
#         token = None
#         # jwt is passed in the request cookies or header
#         if 'x-access-token' in request.cookies:
#             token = request.cookies['x-access-token']
#         elif 'x-access-token' in request.headers:
#             token = request.headers['x-access-token']
#         print(token)

#         try: # if token provided and valid
#             data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
#             userid = data['userid']
#         except: # No token
#             userid = None
#         # returns the current logged in users context to the routes
#         return f(userid, *args, **kwargs) # f(current_user, *args, **kwargs)
#     return decorated

@app.route('/login', methods =['POST', 'GET'])
def login():
    # Authenticate user, set token
    resp = None

    # Handle form input
    if request.method == "POST":
        username = request.form.get('email')
        password = request.form.get('password')

        # ToDo - validate with User Microservice and create token there
        # Make POST to User login service
        
        # Dummy Function for Debugging - Create and set random token
        if app.config['DEBUG'] == True: 
            token = jwt.encode({'userid':19, 'is_admin':True, 'exp':datetime.utcnow() + timedelta(minutes=2)}, app.config['SECRET_KEY'])

        # Get redirect route from cookie
        callback = request.cookies.get('callback')
        if callback is None:
            callback = url_for('index')
        response = make_response(redirect(callback))
        response.set_cookie('x-access-token', token)
        session['login'] = True # Set session value to show logged in info
        return response # Response if token is valid

    return render_template('login.html') # Response for GET

@app.route('/logout', methods =['GET'])
def logout():
    response = make_response(redirect(url_for('index')))
    response.delete_cookie('x-access-token')
    session['login'] = False
    return response

## eBay Routes

@app.route('/')
@TokenDecorator(token='optional')
def index(userid):
    if userid is None:
        user = 'guest'
    else:
        user = userid
    session['username'] = 'username'

    if app.config['DEBUG'] == True:
        # Dummy list of items
        listings = [{'auction_id': x, 'item_name': f'Item {x}', 'price': x} for x in range(1,5)]
    else: # ToDo - make call to Auction microservice to get list of auctions in progress   
        pass
    
    return render_template('home.html', user=user, active_listings=listings)

@app.route('/cart', methods =['POST', 'GET'])
@TokenDecorator(token='required')
def viewCart(userid):
    # ToDo - get data from Shopping microservice
    # list of items and item info
    if app.config['DEBUG'] == True:
        # Dummy list of items
        items = [{'auction_id': x, 'item_name': f'Item {x}', 'price': x} for x in range(1,5)]
        total_price = sum([x['price'] for x in items])
    else: # ToDo - make call to Auction microservice to get list of auctions in progress   
        pass

    return render_template('cart.html', user=userid, cart_items=items, total_price=total_price)

@app.route('/checkout', methods =['POST', 'GET']) # ToDo - does this take GET?
@TokenDecorator(token='required')
def checkout(userid):
    # ToDo - Delete the items shown in cart
    
    return render_template('landing.html',
            header="Success!",
            context_text="Checkout complete",
            redirect_link='/',
            redirect_text='Return home')

@app.route('/watchlist')
@TokenDecorator(token='required')
def viewWatchlist(userid):
    # ToDo - get data from Shopping microservice
    # list of items and item info
    return render_template('watchlist.html', user=userid)

@app.route('/auction/<listing_id>')
def viewAuction(listing_id=None):
    # ToDo - get data from Auction microservice
    # image, price, end time, details
    return render_template('auction.html', listing_id=listing_id)

@app.route('/create/auction')
@TokenDecorator(token='required')
def createAuction():
    return render_template('create_auction.html')

@app.route('/create/account', methods =['POST', 'GET'])
def createAccount():
    # Handle form input
    if request.method == "POST":
        name = request.form.get('name')
        username = request.form.get('email')
        password = request.form.get('password')
        
        if app.config['DEBUG'] == True: # Skip microservice communication
            return render_template('landing.html',
            header='Success!',
            context_text="Account successfully created. Login to account now:",
            redirect_link='/login',
            redirect_text='Login')
        else:
            # ToDo - Create Account w/ User Microservice
            # Handle response from microservice for success/failure
            pass

    else: # GET - render form
        return render_template('create_account.html')

@app.route('/account')
@TokenDecorator(token='required')
def accountInfo(userid):
    return render_template('account.html', user=userid)

@app.route('/admin')
@TokenDecorator(token='required', profile='admin')
def admin_homepage(userid):
    return render_template('admin.html', user=userid)

@app.route('/admin/users', methods=['POST', 'GET'])
@TokenDecorator(token='required', profile='admin')
def admin_edit_users(userid):
    if request.method == 'POST':
        # ToDo - Communicate with User Microservice
        pass
    return render_template('admin_users.html', user=userid)

@app.route('/admin/auctions', methods=['POST', 'GET'])
@TokenDecorator(token='required', profile='admin')
def admin_edit_auctions(userid):
    if request.method == 'POST':
        # ToDo - Communicate with Auction Microservice
        pass
    return render_template('admin_auctions.html', user=userid)

# Update Account
# Delete Account
# Bid success landing page
# Checkout
# Admin - suspend/delete users
# Admin - edit listings


## Dummy routes for testing JWT
@app.route('/protected')
@TokenDecorator(token='required')
def protected(userid):
    print(request.cookies.get('x-access-token'))
    return 'Protected page'

@app.route('/open')
def open():
    print(request.cookies.get('x-access-token'))
    return 'Open page'


app.run(host='0.0.0.0', port=5000)

