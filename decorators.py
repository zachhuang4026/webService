from functools import wraps
from flask import  request, make_response, redirect, url_for, render_template
import jwt

# https://www.geeksforgeeks.org/using-jwt-for-user-authentication-in-flask/
# Todo - Get key from config file

class TokenDecorator:
    # https://stackoverflow.com/questions/10176226/how-do-i-pass-extra-arguments-to-a-python-decorator
    def __init__(self, token='required', profile='user'):
        self.token = token
        self.profile = profile

    def __call__(self, f):
        @wraps(f)
        def decorated_func(*args, **kwargs):
            # Decorator logic
            
            # Check if JWT is present in cookies or request header 
            token = None
            if 'x-access-token' in request.cookies:
                token = request.cookies['x-access-token']
            elif 'x-access-token' in request.headers:
                token = request.headers['x-access-token']
            print(token)

            # Scenario 1: No token provided
            if not token:
                if self.token == 'optional':
                    return f(token=None, *args, **kwargs)
                else:
                    response = make_response(redirect(url_for('login')))
                    response.set_cookie('callback', url_for(f.__name__)) # set cookie to return to intended page
                    return response
            
            try: # Scenario 2/3: Token is provided - check if valid, access profile
                # Decode payload to fetch the stored details
                # ToDo - import secret key from central config
                data = jwt.decode(token, 'your secret key', algorithms=["HS256"]) # app.config['SECRET_KEY'] = 'your secret key'
                userid = data['userid']
                is_admin = data['is_admin']
            except: # Scenario 3: Token is invalid
                response = make_response(redirect(url_for('login')))
                response.set_cookie('callback', url_for(f.__name__)) # set cookie to return to intended page
                return response
            
            # Scenario 4: Token is valid, but admin required and not authorized
            if self.profile == 'admin' and not is_admin:
                # ToDo - redirect to failure page
                return render_template('landing.html', context_text="Access forbidden. User is not Admin",
                    redirect_link='foo',
                    redirect_text='bar')

            # Scenario 5: User is authenticated - return context to routes
            return f(token, *args, **kwargs) # f(current_user, *args, **kwargs)
        return decorated_func