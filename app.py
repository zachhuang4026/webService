from flask import Flask, render_template, request, jsonify, make_response, redirect, url_for, session
import jwt
from datetime import datetime, timedelta
import requests
import configparser

from decorators import TokenDecorator

app = Flask(__name__)

config = configparser.ConfigParser()
config.read('config.ini')

# Define secret key for encoding/decoding JWT tokens
app.config['SECRET_KEY'] = config['flask']['secret_key']
app.config['DEBUG'] = True

def request_builder(endpoint, service, config=config):
    """
    Helper function to build web urls based on endpoint name and service name
    """
    ip = config[service]['ip']
    port = config[service]['port']
    return f'http://{ip}:{port}/{endpoint}'

#######################################################################
## Utilities
#######################################################################

@app.route('/api')
def check_api_gateway():
    """
    Utility endpoint to check whether API Gateway is online and can be reached
    """
    try:
        url = request_builder(endpoint='', service='api_gateway')
        response = requests.get(url).json()
        status_code = response['status_code']
    except:
        status_code = 502
        response = {'message': 'Bad gateway. API Gateway could not be reached', 'status_code': status_code}
    return jsonify(response), status_code

#######################################################################
## Login / Logout
#######################################################################

@app.route('/login', methods =['POST', 'GET'])
def login(DEBUG=False):
    """
    GET interface provides interface for user to login to platform.
    POST receives email/password from form and communicates with API Gateway to authenticate
    """
    # Authenticate account, set token
    if request.method == 'GET':
        return render_template('login.html') # Response for GET

    # Handle form input
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')

        if None in [email, password]: # Throw error if POST made without required parameters
            status_code = 400
            response = {'message': 'Bad request. Did not contain required values in JSON', 'status_code': status_code}
            return jsonify(response), status_code
        
        # Make POST to Account login service
        account_info = {'email': email, 'password': password}
        
        # Dummy Function for Debugging - Create and set random token
        if DEBUG == True:
            account_id = 19
            is_admin = True
            token = jwt.encode({'account_id':account_id, 
                                'is_admin':is_admin,
                                'exp':datetime.utcnow() + timedelta(minutes=2)},
                                app.config['SECRET_KEY'])   
        else: # Communicate with API Gateway
            url = request_builder('login', 'api_gateway')
            try:
                response = requests.post(url, json=account_info)
            except:
                status_code = 502
                response = {'message': 'Bad gateway. API Gateway could not be reached', 'status_code': status_code}
                return jsonify(response), status_code
            
            if response.status_code == 200: # Login Successful - get JWT
                token = response.json().get('token')
            else: # Error logging in. Forward to error page
                return render_template('landing.html',
                    header=f"Error: {response.json()['status_code']}",
                    context_text=response.json()['message'],
                    redirect_link='/login',
                    redirect_text='Login')
        
        # User is logged in
        # Get redirect route from cookie
        callback = request.cookies.get('callback')
        if callback is None:
            callback = url_for('index')
        response = make_response(redirect(callback))
        response.set_cookie('x-access-token', token)
        session['login'] = True # Set session value to show logged in info

        # Check if user is Admin and set session info accordingly
        token_data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"]) # Secret key must match secret key used for encoding
        if token_data['is_admin']:
            session['is_admin'] = True
        return response

@app.route('/logout', methods =['GET'])
def logout():
    """
    Log user out of platform by resetting cookies/session info containing JWT
    """
    response = make_response(redirect(url_for('index')))
    # Clear cookies and session variables
    response.delete_cookie('x-access-token')
    session['login'] = False
    session['is_admin'] = False
    return response

#######################################################################
## Core Shopping Routes
#######################################################################

@app.route('/')
@TokenDecorator(token='optional')
def index(token, DEBUG=True):
    """
    eBay Home page
    Passes JWT, list of listing info to template
    """
    if DEBUG == True:
        # Dummy list of items
        listings = [{'auction_id': x, 'item_name': f'Item {x}', 'price': x} for x in range(1,5)]
    else:  
        # ToDo API Gateway call: Active auctions
        pass
    response = make_response(render_template('home.html', token=token, active_listings=listings))
    response.set_cookie('callback', url_for('index'))
    return response

@app.route('/cart', methods =['GET'])
@TokenDecorator(token='required')
def viewCart(token, DEBUG=True):
    """
    GET method renders list of items currently in cart
    """
    if DEBUG == True:
        # Dummy list of items
        items = [{'auction_id': x, 'item_name': f'Item {x}', 'price': x} for x in range(1,5)]
        total_price = sum([x['price'] for x in items])
    else:
        # ToDo API Gateway call: Get cart/items for user
        pass
    return render_template('cart.html', token=token, cart_items=items, total_price=total_price)    
        

@app.route('/checkout', methods =['POST', 'GET']) # ToDo - does this take GET?
@TokenDecorator(token='required')
def checkout(token):
    """
    Receives POST from Checkout button on Cart page.
    Communicates with API Gateway to process checkout
    """
    if request.method == 'POST':
        # ToDo API Gateway call: Checkout

        return render_template('landing.html',
            header="Success!",
            context_text="Checkout complete",
            redirect_link='/',
            redirect_text='Return home')

@app.route('/watchlist', methods=['POST', 'GET'])
@TokenDecorator(token='required')
def viewWatchlist(token):
    """
    GET renders view of item on account's watchlist
    PUT adds new item to watchlist. Requires input {'token': token, 'listing_id': listing_id}
    """
    if request.method == 'GET':
        # ToDo API Gateway call: get list of items from Watchlist service
        return render_template('watchlist.html', token=token)

    if request.method == 'POST': # Handle response back from Add to Watchlist click
        token = request.form.get('token')
        listing_id = request.form.get('listing_id')

        if None in [token, listing_id]:
            status_code = 400
            response = {'message': 'Bad request. Did not contain token and listing_id in JSON', 'status_code': status_code}
            return jsonify(response), status_code

        # ToDo API Gateway call: add item to watchlist
        
        return render_template('landing.html',
            header='Success!',
            context_text=f"Item {listing_id} successfully added to watchlist. View now:",
            redirect_link='/watchlist',
            redirect_text='Watchlist')

@app.route('/auction/<listing_id>')
@TokenDecorator(token='optional')
def viewAuction(token, listing_id=None, DEBUG=True):
    """
    Returns view of a listing
    """
    if DEBUG == True:
        if int(listing_id) % 2 == 0:
            listing_type = 'buy_now'
        else:
            listing_type = 'auction'
    else:
        # ToDo API Gateway call: get auction information
        pass
    
    response = make_response(render_template('auction.html', token=token, listing_id=listing_id, listing_type=listing_type))
    response.set_cookie('callback', url_for('viewAuction', listing_id=listing_id))
    return response

@app.route('/reportItem', methods=['POST', 'GET'])
@TokenDecorator(token='required')
def reportItem(token):
    """
    Report an item as inappropriate or counterfeit 
    """
    # ToDo - handle POST
    # ToDo - get item Name
    if request.method == 'GET':
        listing_id = request.args.get('listing_id')
        return render_template('report_item.html', listing_id=listing_id)
    if request.method == 'POST':
        auction_id = request.form.get('auction_id')
        report_reason = request.form.get('reason')
        addtional_info = request.form.get('addtional_info')

        # ToDo API Gateway call: report item

        return render_template('landing.html',
            header='Item reported',
            context_text=f"Item {auction_id} successfully reported",
            redirect_link='/',
            redirect_text='Return Home')

#######################################################################
## Create Resources Routes
#######################################################################

@app.route('/create/auction', methods=['POST', 'GET'])
@TokenDecorator(token='required')
def createAuction(token, DEBUG=True):
    """
    GET displays web form for user to input info
    PUT processes info and communicates with API Gateway
    """
    if request.method == 'GET': # Render web form
        # On GET
        ts = datetime.now()
        date_str = str(ts.year) + '-' + str(ts.month) + '-' + str(ts.day)
        
        # Item Categories
        if DEBUG == True:
            category_lst = ['Clothing', 'Electronics', 'Books']
        else:
            # ToDo API Gateway call - list of item categories
            pass
        
        # Otherwise, get category info from API Gateway
        return render_template('create_auction.html', today=date_str, item_categories=category_lst)
    
    if request.method == 'POST':
        # ToDo - post results directly to API gateway?
        # ToDo - handling of timezones, listing/end times etc.
        print('Received results from create auction form')
        print(request.form.get('item_name'))
        print(request.form.get('listing_type'))
        print(request.form.get('start_time'))
        print(request.form.get('end_time'))

        # ToDo API Gateway call - list item
        listing_id = '3'

        return render_template('landing.html',
            header='Item listed',
            context_text=f"Item listed successfully",
            redirect_link=f'/auction/{listing_id}',
            redirect_text='View Item')

@app.route('/create/account', methods =['POST', 'GET'])
def createAccount(DEBUG=False):
    """
    GET renders web form for getting account info
    PUT receives form info, communicates with API Gateway
    """
    # Render web form
    if request.method == 'GET':
        return render_template('create_account.html')

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
            url = request_builder('createAccount', 'api_gateway')
            try:
                response = requests.post(url, json=account_info)    
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
            
            # Parse response
            if response.status_code == 201:
                header='Success!'
            else:
                header='Error ' + str(response.json().get('status_code'))

            return render_template('landing.html',
                header=header,
                context_text=response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')
        

@app.route('/account', methods=['POST','GET'])
@TokenDecorator(token='required')
def accountInfo(token, DEBUG=False):
    """
    GET - display account information
    POST - either allow updates to information or new save information
    """
    if request.method == 'GET':
        if DEBUG == True: # use dummy info
            account_info = {'name': 'User', 'email': 'user@gmail.com', 'password': 'pass'}
        else: # Get Account Info from API Gateway
            url = request_builder('getAccount', 'api_gateway')
            api_response = requests.get(url, params={'token': token})
            account_info = api_response.json()['data']

        return render_template('account.html', token=token, account_info=account_info, editable=False)
    
    # Update information
    if request.method == 'POST':
        # Scenario 1: Conversion from viewing -> updating info
        if request.form.get('email') is None: # Render form in editable mode
            account_info = {'name': request.form.get('hidden_name'),
                            'email': request.form.get('hidden_email'),
                            'password': request.form.get('hidden_password')}
            return render_template('account.html', token=token, account_info=account_info, editable=True)
        else:
            new_name = request.form.get('name')
            new_email = request.form.get('email')
            new_password = request.form.get('password')
            
            # Make POST to API gateway to update
            url = request_builder('updateAccount', 'api_gateway')
            post_body = {'token': token, 'data': {'name': new_name, 'email': new_email, 'password': new_password}}
            try:
                api_response = requests.post(url, json=post_body)
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
            
            # Parse response
            if api_response.status_code == 200:
                header='Success!'
            else:
                header='Error ' + str(api_response.json().get('status_code'))
            return render_template('landing.html',
                header=header,
                context_text=api_response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')

#######################################################################
## Admin routes
#######################################################################

@app.route('/admin')
@TokenDecorator(token='required', profile='admin')
def admin_homepage(token):
    """
    Route to admin console
    """
    return render_template('admin.html')

@app.route('/admin/users', methods=['POST', 'GET'])
@TokenDecorator(token='required', profile='admin')
def admin_edit_users(token):
    """
    GET: render form for user access modifications
    POST: process form input, communicate with API gateway
    """
    if request.method == 'GET':
        return render_template('admin_users.html')

    # On POST, communicate with Account Microservice via API Gateway
    if request.method == 'POST': 
        account_id = request.form.get('account_id')
        action = request.form.get('action')

        if action == 'Delete':
            # ToDo - call delete method    
            pass
        else:
            # Else call update method
            if action == 'Suspend':
                post_body = {'token': token, 'data': {'account_id': account_id, 'account_status': 'Suspended'}}
            elif action == 'Activate':
                post_body = {'token': token, 'data': {'account_id': account_id, 'account_status': 'Active'}}
            elif action == 'Make_Admin':
                post_body = {'token': token, 'data': {'account_id': account_id, 'is_admin': True}}
            else:
                pass
            url = request_builder('updateAccount', 'api_gateway')
        
        # Communicate with API gateway
        try:
            api_response = requests.post(url, json=post_body)
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code

        # Parse response
        if api_response.status_code == 200:
            header='Success!'
        else:
            header='Error ' + str(api_response.json().get('status_code'))
        return render_template('landing.html',
            header=header,
            context_text=api_response.json().get('message'),
            redirect_link='/',
            redirect_text='Return home') 

@app.route('/admin/auctions', methods=['POST', 'GET'])
@TokenDecorator(token='required', profile='admin')
def admin_edit_auctions(token):
    """
    GET - render admin page to update auction info
    POST - process form input
    """
    if request.method == 'GET':
        return render_template('admin_auctions.html')
    if request.method == 'POST':
        # ToDo API Gateway call: Update auction
        
        return render_template('landing.html',
            header='Updated auction',
            context_text='Update this text',
            redirect_link='/',
            redirect_text='Return home') 
        
#######################################################################
## Dummy routes (for testing JWT)
#######################################################################

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

