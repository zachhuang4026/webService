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

def who_am_i(valid_token):
    try:
        token_data = jwt.decode(valid_token, app.config['SECRET_KEY'], algorithms=["HS256"]) # Secret key must match secret key used for encoding
        return token_data["account_id"]
    except:
        raise


#######################################################################
## Utilities
#######################################################################

@app.template_filter('format_timestamp')
def format_timestamp(ts):
    return datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %-I:%M %p')

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
def index(token, DEBUG=False):
    """
    eBay Home page
    Passes JWT, list of listing info to template
    """
    # Get Search terms if they exist
    if DEBUG == True:
        # Dummy list of items
        listings = [{'auction_id': x, 'name': f'Item {x}', 'currPrice': x, 'bids':x} for x in range(1,5)]
        page_subtitle = 'Active Listings'
    
    # Handle Search
    else:
        auction_filter = request.args.get('search_terms')
   
        if auction_filter is None: # return all auctions
            page_subtitle = 'Active Listings'
            # [WIP] ToDo API Gateway call. Get active auctions: /getAuctions
            url = request_builder('searchAuctions', 'api_gateway')
            try:
                api_response = requests.get(url, params={'auction_status': 'active'})
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
            
            if api_response.status_code != 200:
                return render_template('landing.html',
                    header='Error ' + str(api_response.json().get('status_code')),
                    context_text=api_response.json().get('message'),
                    redirect_link='/',
                    redirect_text='Return home')
            listings = api_response.json()['auctions']
            
        else: # User search
            page_subtitle = f'Showing results for "{auction_filter}"'
            
            # [WIP] API Gateway call. (Item service). Search auctions for auction_filter
            url = request_builder('searchItems', 'api_gateway')
            try:
                api_response = requests.get(url, 
                                    params={'categoryName': auction_filter,
                                            'description': auction_filter,
                                            'name': auction_filter})
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
        
            if api_response.status_code != 200:
                header='Error ' + str(api_response.json().get('status_code'))
                return render_template('landing.html',
                    header=header,
                    context_text=api_response.json().get('message'),
                    redirect_link='/',
                    redirect_text='Return home')
            
            # ToDo - add filter for active auctions
            listings = api_response.json()['items']
    
    response = make_response(render_template('home.html', token=token, listings=listings, page_subtitle=page_subtitle))
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
        items = [{'auction_id': x, 'name': f'Item {x}', 'price': x} for x in range(1,5)]
    else:
        # API Gateway call: Get cart/items for user
        url = request_builder('getShoppingCart', 'api_gateway')
        try:
            api_response = requests.get(url, params={'token': token})
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        
        items = api_response.json()['items']
    
    total_price = sum([x['price'] for x in items])
    return render_template('cart.html', token=token, cart_items=items, total_price=total_price)    
        

@app.route('/checkout', methods =['POST'])
@TokenDecorator(token='required')
def checkout(token):
    """
    Receives POST from Checkout button on Cart page.
    Communicates with API Gateway to process checkout
    """
    if request.method == 'POST':
        # API Gateway call: Checkout
        url = request_builder('checkout', 'api_gateway')
        try:
            post_body = {'token': token}
            api_response = requests.post(url, json=post_body)
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code

        if api_response.status_code == 200:
            return render_template('landing.html',
                header="Success!",
                context_text="Checkout complete",
                redirect_link='/',
                redirect_text='Return home')
        else:
            header='Error ' + str(response.json().get('status_code'))
            return render_template('landing.html',
                header=header,
                context_text=response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')


@app.route('/buy', methods=['POST'])
@TokenDecorator(token='required')
def buy(token, DEBUG=False):
    """
    Receives POST from auction page and either performs bid or add to cart
    """
    listing_id = request.form.get('listing_id')
    listing_type = request.form.get('listing_type')
    item_id = request.form.get('item_id')
    token = request.form.get('token')
    bid = request.form.get('bid') # could be null of buy now listing

    if DEBUG == True:
        # If auction, return to item. If buy now, view cart
        if listing_type == 'auction':
            return render_template('landing.html',
                header="Success!",
                context_text="Bid accepted",
                redirect_link=f'/auction/{listing_id}',
                redirect_text='Return to Item')
        else:
            return render_template('landing.html',
                header="Success!",
                context_text="Item added to cart",
                redirect_link=f'/cart',
                redirect_text='View cart')
    else:
        if listing_type == 'auction':
            # [WIP] ToDo - communicate with API gateway to place bid
            url = request_builder('bid', 'api_gateway')
            post_body = {'token': token, 'data': {'auction_id': listing_id, 'price': bid}}
            try:
                api_response = requests.post(url, json=post_body)
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
            
            if api_response.status_code != 200:
                return render_template('landing.html',
                    header='Error ' + str(api_response.json().get('status_code')),
                    context_text=api_response.json().get('message'),
                    redirect_link=f'/auction/{listing_id}',
                    redirect_text='Return to Item')
            
            return render_template('landing.html',
                        header="Success!",
                        context_text="Bid placed successfully",
                        redirect_link=f'/auction/{listing_id}',
                        redirect_text='Return to Item')

        else:  # Buy Now - Add directly to cart
            url = request_builder('addToShoppingCart', 'api_gateway')
            try:
                post_body = {'token': token, 'data': {'item_id': item_id}}
                api_response = requests.post(url, json=post_body)
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code

            if api_response.status_code != 200:
                return render_template('landing.html',
                    header='Error ' + str(api_response.json().get('status_code')),
                    context_text=api_response.json().get('message'),
                    redirect_link='/',
                    redirect_text='Return home')

            return render_template('landing.html',
                    header="Success!",
                    context_text="Item added to cart",
                    redirect_link=f'/cart',
                    redirect_text='View cart')
                

@app.route('/watchlist', methods=['GET'])
@TokenDecorator(token='required')
def viewWatchlist(token):
    """
    GET renders view of item on account's watchlist
    PUT adds new item to watchlist. Requires input {'token': token, 'listing_id': listing_id}
    """
    if request.method == 'GET':
        # API Gateway call: get list of items from Watchlist service

        url = request_builder('getWatchList', 'api_gateway')
        try:
            api_response = requests.get(url, params={'token': token})
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        
        items = api_response.json()['items']

        return render_template('watchlist.html', token=token, items=items)

@app.route('/watchlist/add', methods=['POST'])
@TokenDecorator(token='required')
def addToWatchlist(token):
    """
    Handles POST from the 'Add to Watchlist' button on an auction page.
    Communicates with the API gateway and Shopping microservice
    Inputs: {'token': 'xxx', 'listing_id': 'xxx', 'item_id': 'xxx'}
    """
    # Handle response back from Add to Watchlist click
    token = request.form.get('token')
    listing_id = request.form.get('listing_id')
    item_id = request.form.get('item_id')

    if None in [token, listing_id]:
        status_code = 400
        response = {'message': 'Bad request. Did not contain token and listing_id in JSON', 'status_code': status_code}
        return jsonify(response), status_code

    # API Gateway call: add item to watchlist
    url = request_builder('addToWatchList', 'api_gateway')
    post_body = {'token': token, 'data': {'item_id': item_id}}
    try:
        api_response = requests.post(url, json=post_body)
    except:
        status_code = 500
        response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
        return jsonify(response), status_code

    if api_response.status_code == 200:
        return render_template('landing.html',
                header="Success!",
                context_text=f"Item {listing_id} successfully added to watchlist. View now:",
                redirect_link='/watchlist',
                redirect_text='Watchlist')
    else:
        header='Error ' + str(response.json().get('status_code'))
        return render_template('landing.html',
            header=header,
            context_text=response.json().get('message'),
            redirect_link='/',
            redirect_text='Return home')

@app.route('/watchlist/update', methods=['POST'])
@TokenDecorator(token='required')
def updateWatchlist(token):
    """
    Receives POST from /watchlist to remove items from a user's watchlist
    Input: {'token': 'xxx', 'data': {'item_id': 'xxx'}}
    """
    remove_item_id_lst = [k for (k,v) in request.form.items() if v == 'Remove']
    print(remove_item_id_lst)

    url = request_builder('deleteFromWatchList', 'api_gateway')
    for item_id in remove_item_id_lst:
        post_body = {'token': token, 'data': {'item_id': item_id}}
        try:
            api_response = requests.post(url, json=post_body)
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        if api_response.status_code != 200:
            header='Error ' + str(api_response.json().get('status_code'))
            return render_template('landing.html',
                header=header,
                context_text=api_response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')
    
    return render_template('landing.html',
                header="Items removed from watchlist",
                context_text="The following items were removed from watchlist: {}".format(', '.join(remove_item_id_lst)),
                redirect_link='/watchlist',
                redirect_text='View watchlist')



@app.route('/auction/<listing_id>')
@TokenDecorator(token='optional')
def viewAuction(token, listing_id, DEBUG=False):
    """
    Returns view of a listing
    """
    if DEBUG == True:
        if int(listing_id) % 2 == 0:
            listing_type = 'BUY_NOW'
        else:
            listing_type = 'AUCTION'
        price = 4.69
        listing_info = {'listing_id': listing_id, 'listing_type': listing_type, 'price':price, 'item_id': listing_id}
    else:
        # [WIP] ToDo API Gateway call: get auction information
        # /getAuctionsDetailed?auction_ids=xxxx
        
        url = request_builder('getAuctionsDetailed', 'api_gateway')
        api_response = requests.get(url, params={'auction_ids': listing_id})
        listing_info = api_response.json()['auctions'][0]
    
    response = make_response(render_template('auction.html', token=token, listing_info=listing_info))
    response.set_cookie('callback', url_for('viewAuction', listing_id=listing_id))
    return response

@app.route('/reportItem', methods=['POST', 'GET'])
@TokenDecorator(token='required')
def reportItem(token):
    """
    Report an item as inappropriate or counterfeit 
    """
    if request.method == 'GET':
        item_id = request.args.get('item_id')

        # [WIP] ToDo API Gateway call: get Item name from item_id
        url = request_builder('getItems', 'api_gateway')
        try:
            api_response = requests.get(url, params={'item_ids': item_id})
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        
        if api_response.status_code != 200:
            header='Error ' + str(api_response.json().get('status_code'))
            return render_template('landing.html',
                header=header,
                context_text=api_response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')

        item = api_response.json()['items'][0]
        return render_template('report_item.html', item=item)
    
    if request.method == 'POST': # Handle input from Report Item form

        item_id = request.form.get('item_id')
        report_reason = request.form.get('reason')
        addtional_info = request.form.get('addtional_info')

        # [WIP] ToDo API Gateway call: report item
        url = request_builder('flagItem', 'api_gateway')
        post_body = {'item_id': item_id} # 'report_reason':report_reason, 'addtional_info':addtional_info
        try:
            api_response = requests.post(url, json=post_body)
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        
        if api_response.status_code == 200:
            return render_template('landing.html',
                    header='Item reported',
                    context_text=f"Item {item_id} successfully reported",
                    redirect_link='/',
                    redirect_text='Return Home')
        else:
            header='Error ' + str(api_response.json().get('status_code'))
            return render_template('landing.html',
                header=header,
                context_text=api_response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')


#######################################################################
## Create Resources Routes
#######################################################################

@app.route('/create/auction', methods=['POST', 'GET'])
@TokenDecorator(token='required')
def createAuction(token, DEBUG=False):
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
            item_categories = [{'id': '1', 'name': 'shoes'},
                                {'id': '2', 'name': 'clothing'},
                                {'id': '3', 'name': 'electronics'}]
        else:
            # [WIP] ToDo API Gateway call - list of item categories
            url = request_builder('getItemCategories', 'api_gateway')
            try:
                api_response = requests.get(url)

            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
            
            item_categories = api_response.json()['item_categories']
        
        # Otherwise, get category info from API Gateway
        return render_template('create_auction.html', today=date_str, item_categories=item_categories)
    
    if request.method == 'POST':
        # ToDo - handling of timezones, listing/end times etc.
        print('Received results from create auction form')
        print(request.form.get('item_name'))
        print(request.form.get('listing_type'))
        start_time = int(datetime.timestamp(datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')))
        end_time = int(datetime.timestamp(datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M')))
        print(start_time)
        print(end_time)
        category_id, category_name = request.form.get('item_category').split('|')
        print(category_id, category_name)
        print(request.form.get('item_details'))
        print(request.form.get('item_price'))

        # [WIP] ToDo API Gateway call - list item (Auction Service)
        # /createAuction
        url = request_builder('createAuction', 'api_gateway')
        post_body = {'token': token,
                    'data': {'item_name': request.form.get('item_name'),
                            'item_details': request.form.get('item_details'),
                            'item_category': category_name,
                            'starting_price': float(request.form.get('item_price')),
                            'listing_type': request.form.get('listing_type'),
                            'listing_start_time': start_time,
                            'listing_end_time': end_time}}
        try:
            api_response = requests.post(url, json=post_body)
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        
        if api_response.status_code != 200:
            return render_template('landing.html',
                header='Error ' + str(api_response.json().get('status_code')),
                context_text=api_response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')

        # ToDo - uncomment this section
        # listing_id = '3'
        listing_id = api_response.json().get('auction_id')
        print(listing_id)

        return render_template('landing.html',
            header='Item listed',
            context_text="Item listed successfully",
            redirect_link=f'/auction/{listing_id}',
            redirect_text='View Item')

@app.route('/create/category', methods=['POST','GET'])
@TokenDecorator(token='required')
def createCategory(token):
    if request.method == 'GET':
        return render_template('create_category.html')
    
    if request.method == 'POST':
        new_category_name = request.form.get('category')
        
        # [WIP] ToDO API Gateway call - add new category
        url = request_builder('addItemCategory', 'api_gateway')
        post_body = {'token': token, 'name': new_category_name}
        try:
            api_response = requests.post(url, json=post_body)
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        
        if api_response.status_code == 200:
            return render_template('landing.html',
                    header='Item reported',
                    context_text="Item category created",
                    redirect_link='/create/auction',
                    redirect_text='Return to item listing')
        else:
            header='Error ' + str(api_response.json().get('status_code'))
            return render_template('landing.html',
                header=header,
                context_text=api_response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')

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

@app.route('/account/delete', methods=['POST'])
@TokenDecorator(token='required')
def delete_account(token):
    """
    After delete account button click from account page,
    receives POST and processes request
    """
    url = request_builder('deleteAccount', 'api_gateway')
    post_body = {'token': token}

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
        session['login'] = False # Remove session vars/cookies
        session['is_admin'] = False
    else:
        header='Error ' + str(api_response.json().get('status_code'))

    response = make_response(
                    render_template(
                            'landing.html',
                            header=header,
                            context_text=api_response.json().get('message'),
                            redirect_link='/',
                            redirect_text='Return home'))
    
    if api_response.status_code == 200:
        response.delete_cookie('x-access-token')
    
    return response

@app.route('/account/listings/<role>', methods=['GET'])
@TokenDecorator(token='required')
def account_listings(token, role, DEBUG=True):
    """
    GET - display account's listings
    """
    if role not in ['seller', 'buyer']:
        return render_template('landing.html',
                header='Error',
                context_text='Error rendering auctions',
                redirect_link='/',
                redirect_text='Return home')

    if DEBUG == True: # use dummy info
        listings = [{'auction_id': x, 'name': f'{role} item {x}', 'currPrice': x, 'end_time': 1669773466.727793, 'bid_history': []} for x in range(1,5)]      
    else: 
        # [WIP] ToDo API Gateway call - listings for seller (Auction Service)
        # /searchAuctions?seller_id=xxxx
        
        # Try to get identity from token, otherwise just redirect to home
        try:
            account_id = who_am_i(token)
        except:
            return redirect('/')
        
        # Get auctions from API gateway
        if role == 'seller':
            url = request_builder('searchAuctions', 'api_gateway')
            try:
                api_response = requests.get(url, params={'seller_id': account_id})
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
        else:
            url = request_builder('searchAuctions', 'api_gateway')
            try:
                api_response = requests.get(url, params={'buyer_id': account_id})
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
        
        if api_response.status_code != 200:
            return render_template('landing.html',
                header='Error ' + str(api_response.json().get('status_code')),
                context_text=api_response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')
        
        listings = api_response.json().get('auctions')

    return render_template('account_listings.html', token=token, role=role, listings=listings)

@app.route('/endAuction', methods=['POST'])
@TokenDecorator(token='required', profile='user')
def end_auction(token):
    auction_id = request.form.get('auction_id')
    post_body = {'token': token, 'auction_id': auction_id}
    url = request_builder('endAuction', 'api_gateway')
    try:
        api_response = requests.post(url, json=post_body)
    except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
    
    if api_response.status_code != 200:
            return render_template('landing.html',
                header='Error ' + str(api_response.json().get('status_code')),
                context_text=api_response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')
    
    return render_template('landing.html',
                header='Success!',
                context_text=f'Auction {auction_id} successfully ended',
                redirect_link='/account/listings/seller',
                redirect_text='View Seller Auctions')

#######################################################################
## Admin routes
#######################################################################

@app.route('/admin')
@TokenDecorator(token='required', profile='admin')
def admin_homepage(token, DEBUG=False):
    """
    Route to admin console
    """
    if DEBUG == True:
        # Dummy list of items
        listings = [{'auction_id': x, 'item_name': f'Item {x}', 'price': x} for x in range(1,5)]
    else:
        # [WIP] ToDo API Gateway call. Get active auctions: /getAuctions
        # /getAuctions?auction_status=active
        url = request_builder('searchAuctions', 'api_gateway')
        try:
            api_response = requests.get(url, params={'auction_status': 'active'})
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        
        if api_response.status_code != 200:
            return render_template('landing.html',
                header='Error ' + str(api_response.json().get('status_code')),
                context_text=api_response.json().get('message'),
                redirect_link='/',
                redirect_text='Return home')
        listings = api_response.json()['auctions']
    # return render_template('admin.html', active_listings=listings)
    return make_response(render_template('admin.html', token=token, listings=listings))

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
            post_body = {'token': token, 'data': {'account_id': account_id}}
            url = request_builder('deleteAccount', 'api_gateway')
        else:
            # Else call update method
            if action == 'Suspend':
                post_body = {'token': token, 'data': {'account_id': account_id, 'account_status': 'Suspended'}}
            elif action == 'Activate':
                post_body = {'token': token, 'data': {'account_id': account_id, 'account_status': 'Active'}}
            elif action == 'Make_Admin':
                post_body = {'token': token, 'data': {'account_id': account_id, 'is_admin': True}}
            elif action == 'Remove_Admin':
                post_body = {'token': token, 'data': {'account_id': account_id, 'is_admin': False}}
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
            redirect_link='/admin/users',
            redirect_text='Return to Admin User Access Control Pannel') 

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
        # ToDo API Gateway call: Update auction /updateAuction

        auction_id = request.form.get('auction_id')
        post_body = {'token': token, 'auction_id': auction_id}
        url = request_builder('endAuction', 'api_gateway')
        try:
            api_response = requests.post(url, json=post_body)
        except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
        
        if api_response.status_code != 200:
                return render_template('landing.html',
                    header='Error ' + str(api_response.json().get('status_code')),
                    context_text=api_response.json().get('message'),
                    redirect_link='/',
                    redirect_text='Return home')
        
        return render_template('landing.html',
                    header='Success!',
                    context_text=f'Auction {auction_id} successfully ended',
                    redirect_link='/admin/auctions',
                    redirect_text='Return to Auction Control Pannel')

@app.route('/admin/flagged_items')
@TokenDecorator(token='required', profile='admin')
def admin_view_flagged_items(token, DEBUG=False):
    """
    GET - Display table of items flagged by users
    """
    if DEBUG == True:
        # Dummy list of items
        listings = [{'auctionID': x, 'name': f'Item {x}', 'bidPrice': x} for x in range(1,5)]
    else:
        # [WIP] ToDo API Gateway call: flagged items
        url = request_builder('getFlaggedItems', 'api_gateway')
        try:
            api_response = requests.get(url, params={'token': token})
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code

        # Parse response
        if api_response.status_code != 200:
            return render_template('landing.html',
                header='Error ' + str(api_response.json().get('status_code')),
                context_text=api_response.json().get('message'),
                redirect_link='/admin/users',
                redirect_text='Return to Admin User Access Control Pannel') 
        else:
            return render_template('admin_flagged_items.html', flagged_items=api_response.json().get('items'))

@app.route('/admin/metrics', methods=['POST', 'GET'])
@TokenDecorator(token='required', profile='admin')
def admin_metrics(token, DEBUG=True):
    """
    GET - Render Form
    POST - Render Form + Results
    """
    if request.method == 'GET':
        return render_template('admin_metrics.html')
    
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        start_ts = datetime.timestamp(datetime.strptime(start_date, '%Y-%m-%d'))
        end_ts = datetime.timestamp(datetime.strptime(end_date, '%Y-%m-%d'))
        # [WIP] ToDo API Gateway call - get closed auctions
        # /searchAuctions?auction_status=closed
        url = request_builder('searchAuctions', 'api_gateway')
        try:
            api_response = requests.get(url, params={'auction_status': 'closed'})
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        # Parse response
        if api_response.status_code != 200:
            return render_template('landing.html',
                header='Error ' + str(api_response.json().get('status_code')),
                context_text=api_response.json().get('message'),
                redirect_link='/admin/users',
                redirect_text='Return to Admin User Access Control Pannel') 
        
        auctions = api_response.json()['auctions']

        # Calculate basic metrics
        # Ideally this would this would happen in a microservice method but we didn't expose one and this serves as a work-around
        closed_auctions = [x for x in auctions if (x['end_time'] >= start_ts and x['end_time'] <= end_ts)]
        num_auctions = sum([1 for x in closed_auctions if x['listing_type'] == 'auction'])
        if num_auctions > 0:
            auction_avg_price = sum([x['currPrice'] for x in closed_auctions if x['listing_type'] == 'auction'])
        else:
            auction_avg_price = 0
        num_buy_now = sum([1 for x in closed_auctions if x['listing_type'] == 'buy_now'])
        if num_buy_now > 0:
            buy_now_avg_price = sum([x['currPrice'] for x in closed_auctions if x['listing_type'] == 'buy_now'])
        else:
            buy_now_avg_price = 0
        
        return render_template('admin_metrics.html',
                    metrics = f'Displaying metrics from {start_date} to {end_date}',
                    num_auctions=num_auctions,
                    auction_avg_price=auction_avg_price,
                    num_buy_now=num_buy_now,
                    buy_now_avg_price=buy_now_avg_price)

@app.route('/admin/categories', methods=['POST', 'GET'])
@TokenDecorator(token='required', profile='admin')
def admin_edit_categories(token, DEBUG=False):
    """
    GET - renders input form for Admin to view/select categories to remove
    PUT - process submission of form, communicating with API gateway to remove categories
    """
    if request.method == 'GET':
        if DEBUG == True:
            item_categories = [{'id': '92829c12-ac6b-48cb-a4c0-1cb8d43d6856', 'name': 'shoes'},
                            {'id': 'ca570235-f00e-436d-8b9a-d432a8e27d30', 'name': 'clothing'},
                            {'id': 'a0a269d1-6b27-4121-9483-17dfad1701bf', 'name': 'electronics'},
                            {'id': '3b48839a-c205-4ec3-9b12-52a3d25857da', 'name': 'books'}]
        else:
            # [WIP] ToDo API Gateway call - list of item categories
            url = request_builder('getItemCategories', 'api_gateway')
            try:
                api_response = requests.get(url)
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
            
            item_categories = api_response.json()['item_categories']
            
        return render_template('admin_categories.html', categories=item_categories)
    
    if request.method == 'POST':
        remove_category_lst = [k.split('|') for (k,v) in request.form.items() if v == 'Remove']
        print(remove_category_lst)

        category_names = [x[1] for x in remove_category_lst]
        category_ids = [x[0] for x in remove_category_lst]
        
        # [WIP] ToDo API Gateway call - delete categories
        url = request_builder('removeItemCategory', 'api_gateway')
        for i in remove_category_lst:
            post_body = {'token': token, 'id': i[0]}
            try:
                api_response = requests.post(url, json=post_body)
            except:
                status_code = 500
                response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
                return jsonify(response), status_code
            if api_response.status_code != 200:
                return render_template('landing.html',
                    header='Error ' + str(api_response.json().get('status_code')),
                    context_text=api_response.json().get('message'),
                    redirect_link='/admin',
                    redirect_text='Return to Admin Control Pannel')
        
        return render_template('landing.html',
                    header='Success',
                    context_text='Removed the following item categories: {}'.format(', '.join([x[1] for x in remove_category_lst])),
                    redirect_link='/admin',
                    redirect_text='Return to Admin Control Pannel')


@app.route('/admin/email', methods=['POST', 'GET'])
@TokenDecorator(token='required', profile='admin')
def admin_email_inbox(token, DEBUG=True):
    """
    GET - renders input form for Admin to view/select categories to remove
    PUT - process submission of form, communicating with API gateway to remove categories
    """
    url = request_builder('getEmails', 'api_gateway')
    try:
        api_response = requests.get(url, params={'token': token})
    except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code

    # Parse response
    if api_response.status_code != 200:
        header='Error ' + str(api_response.json().get('status_code'))
        return render_template('landing.html',
            header=header,
            context_text=api_response.json().get('message'),
            redirect_link='/admin',
            redirect_text='Return to Admin Control Pannel')
    
    emails = api_response.json()['messages']
    return render_template('admin_email_inbox.html', emails=emails)

@app.route('/admin/email/create_reply', methods=['POST'])
@TokenDecorator(token='required', profile='admin')
def admin_email_create_reply(token):
    """
    Receives POST from inbox when Admin wants to reply to an email.
    Routes request to email composer tool
    """
    to_email = request.form.get('to_email')
    subject = request.form.get('subject')
    return render_template('admin_email_reply.html', to_email=to_email, subject=subject, token=token)

@app.route('/admin/email/send', methods=['POST'])
@TokenDecorator(token='required', profile='admin')
def admin_email_send(token):
    """
    Receives POST from email composer tool and communicates 
    with API gateway to send email
    """
    if request.method == 'POST':
        to_email = request.form.get('to_email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        url = request_builder('sendEmail', 'api_gateway')
        post_body = {'token': token, 'to_email': to_email, 'subject': subject, 'message': message}

        try:
            api_response = requests.post(url, json=post_body)
        except:
            status_code = 500
            response = {'message': 'Error communicating with API Gateway', 'status_code': status_code}
            return jsonify(response), status_code
        
        if api_response.status_code != 200:
            header='Error ' + str(api_response.json().get('status_code'))
            return render_template('landing.html',
                header=header,
                context_text=api_response.json().get('message'),
                redirect_link='/admin',
                redirect_text='Return to Admin console')
    
        return render_template('landing.html',
                    header="Success!",
                    context_text="Email successfuly sent",
                    redirect_link='/admin/email',
                    redirect_text='Return to inbox')
        
        

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

