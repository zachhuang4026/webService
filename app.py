import sys
from flask import Flask, render_template, request, jsonify, make_response
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

# https://www.geeksforgeeks.org/using-jwt-for-user-authentication-in-flask/
# decorator for verifying the JWT
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # jwt is passed in the request cookies or header
        if 'x-access-token' in request.cookies:
            token = request.cookies['x-access-token']
        elif 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        print(token)

        # return 401 if token is not passed
        if not token:
            return jsonify({'message' : 'Token is missing !!'}), 401
  
        try:
            # decoding the payload to fetch the stored details
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            
            # Get user credentials from DB
            if app.config['DEBUG'] == True:
                current_user = data['public_id'] # Temporary - pass user once DB is set up
            else:
                pass
                # # Get user from DB
                # current_user = User.query\
                #     .filter_by(public_id = data['public_id'])\
                #     .first()
        except:
            return jsonify({
                'message' : 'Token is invalid !!'
            }), 401
        # returns the current logged in users context to the routes
        return f(*args, **kwargs) # f(current_user, *args, **kwargs)
    return decorated

@app.route('/login', methods =['POST', 'GET'])
def login():
    # Authenticate user, set token
    resp = None

    # ToDo - functionality should be in User microservice

    if app.config['DEBUG'] == True:
        # Create random token 
        token = jwt.encode({'public_id':19, 'exp':datetime.utcnow() + timedelta(minutes=2)}, 'your secret key')
        resp = make_response('Successfully Logged in and set cookie', 201)
        resp.set_cookie('x-access-token', token)

    return resp

@app.route('/')
@token_required
def index():
    return render_template('home.html')

@app.route('/protected')
@token_required
def protected():
    print(request.cookies.get('x-access-token'))
    return 'Protected page'

@app.route('/open')
def open():
    print(request.cookies.get('x-access-token'))
    return 'Open page'



app.run(host='0.0.0.0', port=5000)

