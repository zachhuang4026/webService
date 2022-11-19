import sys
from flask import Flask, render_template, request, jsonify, make_response, redirect, url_for, session
from functools import wraps
import jwt
from datetime import datetime, timedelta

app = Flask(__name__)

# Define secret key for encoding/decoding JWT tokens
# ToDo - move this to env file
app.config['SECRET_KEY'] = 'your secret key'
app.config['DEBUG'] = True

from decorators import TokenDecorator

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
            account_id = 19
            is_admin = True
            token = jwt.encode({'userid':account_id, 'is_admin':is_admin, 'exp':datetime.utcnow() + timedelta(minutes=2)}, app.config['SECRET_KEY'])

        # Get redirect route from cookie
        callback = request.cookies.get('callback')
        if callback is None:
            callback = url_for('index')
        response = make_response(redirect(callback))
        response.set_cookie('x-access-token', token)
        session['login'] = True # Set session value to show logged in info
        if is_admin:
            session['is_admin'] = True
        return response # Response if token is valid

    return render_template('login.html') # Response for GET

@app.route('/logout', methods =['GET'])
def logout():
    response = make_response(redirect(url_for('index')))
    # Clear cookies and session variables
    response.delete_cookie('x-access-token')
    session['login'] = False
    session['is_admin'] = False
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

@app.route('/reportItem')
@TokenDecorator(token='required')
def reportItem(userid):
    # ToDo - handle POST
    # ToDo - get item Name
    listing_id = request.args.get('listing_id')
    return render_template('report_item.html', listing_id=listing_id)


@app.route('/create/auction', methods=['POST', 'GET'])
@TokenDecorator(token='required')
def createAuction(userid):
    if request.method == 'POST':
        # ToDo - post results directly to API gateway?
        # ToDo - handling of timezones, listing/end times etc.
        print('Received results from create auction form')
        print(request.form.get('item_name'))
        print(request.form.get('listing_type'))
        print(request.form.get('start_time'))
        print(request.form.get('end_time'))
        return 'results'
    
    # On GET
    ts = datetime.now()
    date_str = str(ts.year) + '-' + str(ts.month) + '-' + str(ts.day)

    # Item Categories
    if app.config['DEBUG'] == True:
        category_lst = ['Clothing', 'Electronics', 'Books']
    # Otherwise, get category info from API Gateway

    return render_template('create_auction.html', today=date_str, item_categories=category_lst)

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

@app.route('/account', methods=['POST','GET'])
@TokenDecorator(token='required')
def accountInfo(userid):
    if app.config['DEBUG'] == True:
        # use dummy info
        account_info = {'name': 'User', 'email': 'user@gmail.com', 'password': 'pass'}
    else:
        pass
        # Get account info from API Gateway/User Service

    if request.method == 'POST':
        print(request.form.get('email'))
        print('Here')
        if request.form.get('email') is None: # Conversion from viewing -> updating info
            return render_template('account.html', user=userid, account_info=account_info, update=True)
        else:
            # Update info via API
            return redirect(url_for('accountInfo'))

    return render_template('account.html', user=userid, account_info=account_info, update=False)

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

