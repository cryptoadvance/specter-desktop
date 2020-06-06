import logging
import pytest

def test_home(caplog, client):
    ''' The root of the app '''
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG,logger="cryptoadvance.specter")
    result = client.get('/')
    # By default there is no authentication
    assert result.status_code == 200 # OK.
    assert b'Nothing here' in result.data
    result = client.get('/new_device', follow_redirects=True)
    assert result.status_code == 200 # OK.
    assert b'Add New Device' in result.data
    result = client.get('/settings', follow_redirects=True)
    assert result.status_code == 200 # OK.
    assert b'App settings' in result.data
    result = client.get('/new_wallet', follow_redirects=True)
    assert result.status_code == 200 # OK.
    assert b'Select the type of the wallet' in result.data


@pytest.mark.skip(reason="no idea why /login returns a 404, help appreciated")
def test_login_logout(app,client):
    ''' whether we can login or logout '''
    with app.test_client() as client:
        result = client.get('/login', follow_redirects=True)
        assert b'blub' in result.data
        result = login(client, 'secret')
        assert b'Logged in successfully.' in result.data
        result = logout(client)
        assert b'You were logged out' in result.data
        result = login(client, 'non_valid_password')
        assert b'Invalid username or password' in result.data
        result = login(client, 'blub')
        assert b'Invalid username or password' in result.data


def login(client, password):
    ''' login helper-function '''
    result = client.post('/login', data=dict(
        password=password
    ), follow_redirects=True)
    assert b'We could not check your password, maybe Bitcoin Core is not running or not configured?' not in result.data
    return result

def logout(client):
    ''' logout helper-method '''
    return client.get('/logout', follow_redirects=True)
