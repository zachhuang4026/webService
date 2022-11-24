import sys
from flask import Flask, render_template, request, jsonify, make_response, redirect, url_for, session
from functools import wraps
import jwt
from datetime import datetime, timedelta
import requests
import configparser

app = Flask(__name__)

# Define secret key for encoding/decoding JWT tokens
# ToDo - move this to env file
app.config['SECRET_KEY'] = 'your secret key'
app.config['DEBUG'] = True

config = configparser.ConfigParser()
config.read('config.ini')

from decorators import TokenDecorator

def request_builder(endpoint, service, config=config):
    ip = config[service]['ip']
    port = config[service]['port']
    return f'http://{ip}:{port}/{endpoint}'

@app.route('/api')
def check_api_gateway():
    try:
        url = request_builder(endpoint='', service='api_gateway')
        response = requests.get(url).json()
        status_code = response['status_code']
    except:
        status_code = 502
        response = {'message': 'Bad gateway. API Gateway could not be reached', 'status_code': status_code}
    return jsonify(response), status_code

@app.route('/login', methods =['POST', 'GET'])
def login(DEBUG=False):
    # Authenticate account, set token
    resp = None

    # Handle form input
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        print(email, password)

        if None in [email, password]:
            status_code = 400
            response = {'message': 'Bad request. Did not contain required values in JSON', 'status_code': status_code}
            return jsonify(response), status_code
        # ToDo - validate with Account Microservice and create token there
        # Make POST to Account login service
        account_info = {'email': email, 'password': password}
        
        # Dummy Function for Debugging - Create and set random token
        if DEBUG == True: # Dummy data
            account_id = 19
            is_admin = True
            token = jwt.encode({'account_id':account_id, 'is_admin':is_admin, 'exp':datetime.utcnow() + timedelta(minutes=2)}, app.config['SECRET_KEY'])
        
        else:
            try:
                url = request_builder('login', 'api_gateway')
                response = requests.post(url, json=account_info)
            except:
                status_code = 502
                response = {'message': 'Bad gateway. API Gateway could not be reached', 'status_code': status_code}
                return jsonify(response), status_code
            
            if response.status_code == 200:
                token = response.json().get('token')
            else:
                # response = {'message': response.json()['message'], 'status_code': response.status_code}
                return render_template('landing.html',
                    header=f"Error: {response.json()['status_code']}",
                    context_text=response.json()['message'],
                    redirect_link='/login',
                    redirect_text='Login')
        
        # Get redirect route from cookie
        callback = request.cookies.get('callback')
        if callback is None:
            callback = url_for('index')
        response = make_response(redirect(callback))
        response.set_cookie('x-access-token', token)
        session['login'] = True # Set session value to show logged in info

        token_data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"]) # Secret key must match secret key used for encoding
        if token_data['is_admin']:
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
def index(token):
    
    if token is None:
        user = 'guest'
    else:
        user = token
    session['username'] = 'username'

    if app.config['DEBUG'] == True:
        # Dummy list of items
        listings = [{'auction_id': x, 'item_name': f'Item {x}', 'price': x} for x in range(1,5)]
    else: # ToDo - make call to Auction microservice to get list of auctions in progress   
        pass
    
    response = make_response(render_template('home.html', user=token, active_listings=listings))
    response.set_cookie('callback', url_for('index'))
    return response

@app.route('/cart', methods =['POST', 'GET'])
@TokenDecorator(token='required')
def viewCart(token):
    # ToDo - get data from Shopping microservice
    # list of items and item info
    if app.config['DEBUG'] == True:
        # Dummy list of items
        items = [{'auction_id': x, 'item_name': f'Item {x}', 'price': x} for x in range(1,5)]
        total_price = sum([x['price'] for x in items])
    else: # ToDo - make call to Auction microservice to get list of auctions in progress   
        pass

    return render_template('cart.html', user=token, cart_items=items, total_price=total_price)

@app.route('/checkout', methods =['POST', 'GET']) # ToDo - does this take GET?
@TokenDecorator(token='required')
def checkout(token):
    # ToDo - Delete the items shown in cart
    
    return render_template('landing.html',
            header="Success!",
            context_text="Checkout complete",
            redirect_link='/',
            redirect_text='Return home')

@app.route('/watchlist', methods=['POST', 'GET'])
@TokenDecorator(token='required')
def viewWatchlist(token):

    if request.method == 'POST': # Handle response back from Add to Watchlist click
        print('******** MAKING POST TO ADD TO WATCHLIST ********')
        # Get inputs to relay
        token = request.form.get('token')
        listing_id = request.form.get('listing_id')
        print(token)
        print(listing_id)
        # Relay to API Gateway
        # Render template based on response
        return render_template('landing.html',
            header='Success!',
            context_text=f"Item {listing_id} successfully added to watchlist. View now:",
            redirect_link='/watchlist',
            redirect_text='Watchlist')
    # GET response
    # ToDo - get data from Shopping microservice
    # list of items and item info
    return render_template('watchlist.html', user=token)

@app.route('/auction/<listing_id>')
@TokenDecorator(token='optional')
def viewAuction(token, listing_id=None):
    # ToDo - get data from Auction microservice
    # image, price, end time, details
    if app.config['DEBUG'] == True:
        if int(listing_id) % 2 == 0:
            listing_type = 'buy_now'
        else:
            listing_type = 'auction'
    
    response = make_response(render_template('auction.html', token=token, listing_id=listing_id, listing_type=listing_type))
    response.set_cookie('callback', url_for('viewAuction', listing_id=listing_id))
    return response

@app.route('/reportItem')
@TokenDecorator(token='required')
def reportItem(token):
    # ToDo - handle POST
    # ToDo - get item Name
    listing_id = request.args.get('listing_id')
    return render_template('report_item.html', listing_id=listing_id)


@app.route('/create/auction', methods=['POST', 'GET'])
@TokenDecorator(token='required')
def createAuction(token):
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
def createAccount(DEBUG=False):
    # Handle form input
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if DEBUG == True: # Skip microservice communication
            return render_template('landing.html',
            header='Success!',
            context_text="Account successfully created. Login to account now:",
            redirect_link='/login',
            redirect_text='Login')
        # Create Account w/ Account Microservice
        else: 
            account_info = {'data': {'name': name, 'email': email, 'password': password}}
            api_gateway_ip = config['api_gateway']['ip']
            api_gateway_port = config['api_gateway']['port']
            try:
                response = requests.post(f'http://{api_gateway_ip}:{api_gateway_port}/createAccount', json=account_info)
                
                if response.status_code == 201:
                    header='Success!'
                else:
                    header='Error ' + str(response.json().get('status_code'))

                return render_template('landing.html',
                    header=header,
                    context_text=response.json().get('message'),
                    redirect_link='/',
                    redirect_text='Return home')
                
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
            
    else: # GET - render form
        return render_template('create_account.html')

@app.route('/account', methods=['POST','GET'])
@TokenDecorator(token='required')
def accountInfo(token, DEBUG=False):
    
    if request.method == 'GET':
        if DEBUG == True: # use dummy info
            account_info = {'name': 'User', 'email': 'user@gmail.com', 'password': 'pass'}
        else: # Get Account Info from API Gateway
            url = request_builder('getAccount', 'api_gateway')
            api_response = requests.get(url, params={'token': token})
            account_info = api_response.json()['data']

        return render_template('account.html', user=token, account_info=account_info, editable=False)

    if request.method == 'POST':
        print(request.form.get('email'))
        print('Here')
        if request.form.get('email') is None: # Conversion from viewing -> updating info
            account_info = {'name': request.form.get('hidden_name'),
                            'email': request.form.get('hidden_email'),
                            'password': request.form.get('hidden_password')}
            return render_template('account.html', user=token, account_info=account_info, editable=True)
        else:
            # ToDo - Update info via API
            new_name = request.form.get('name')
            new_email = request.form.get('email')
            new_password = request.form.get('password')

            print(new_name, new_email, new_password )
            
            # Make POST to API gateway to update
            url = request_builder('updateAccount', 'api_gateway')
            post_body = {'token': token, 'data': {'name': new_name, 'email': new_email, 'password': new_password}}
            try:
                api_response = requests.post(url, json=post_body)

                print(api_response.json())
                
                if api_response.status_code == 200:
                    header='Success!'
                else:
                    header='Error ' + str(api_response.json().get('status_code'))
                return render_template('landing.html',
                    header=header,
                    context_text=api_response.json().get('message'),
                    redirect_link='/',
                    redirect_text='Return home')

            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code

            # return redirect(url_for('accountInfo'))

@app.route('/admin')
@TokenDecorator(token='required', profile='admin')
def admin_homepage(token):
    return render_template('admin.html')

@app.route('/admin/users', methods=['POST', 'GET'])
@TokenDecorator(token='required', profile='admin')
def admin_edit_users(token):
    if request.method == 'POST':
        # ToDo - Communicate with Account Microservice
        pass
    return render_template('admin_users.html')

@app.route('/admin/auctions', methods=['POST', 'GET'])
@TokenDecorator(token='required', profile='admin')
def admin_edit_auctions(token):
    if request.method == 'POST':
        # ToDo - Communicate with Auction Microservice
        pass
    return render_template('admin_auctions.html')

# Update Account
# Delete Account
# Bid success landing page
# Checkout
# Admin - suspend/delete users
# Admin - edit listings


## Dummy routes for testing JWT
@app.route('/protected')
@TokenDecorator(token='required')
def protected(token):
    print(request.cookies.get('x-access-token'))
    return 'Protected page'

@app.route('/open')
def open():
    print(request.cookies.get('x-access-token'))
    return 'Open page'


app.run(host='0.0.0.0', port=5000)

