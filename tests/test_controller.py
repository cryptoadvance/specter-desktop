

def test_home(client):
    ''' The root of the app '''
    result = client.get('/')
    assert result.status_code == 401 # UNAUTHORIZED.

def test_login_logout(client):
    ''' whether we can login or logout '''
    client.get('/login')
    result = login(client,'doensnt_matter', 'secret')
    assert b'Logged in successfully.' in result.data
    result = logout(client)
    assert b'You were logged out' in result.data
    result = login(client,'testuser3', 'non_valid_password')
    assert b'Invalid username or password' in result.data
    result = login(client,'testuser3', 'blub')
    assert b'Invalid username or password' in result.data


def login(client, username, password):
    ''' login helper-function '''
    return client.post('/login', data=dict(
        username=username,
        password=password
    ), follow_redirects=True)

def logout(client):
    ''' logout helper-method '''
    return client.get('/logout', follow_redirects=True)
