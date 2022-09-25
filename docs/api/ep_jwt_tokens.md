# Token Endpoint

Creates a new token for the user and Gives all the tokens created by the user.

**URL** : `/v1alpha/token`

## GET

**Method** : `GET`

**Auth required** : Yes

**Permissions required** : None

### Success Response

**Code** : `200 OK`

**Content examples**

### Get Result 

```json
{
    "message": "Tokens exists",
    "jwt_tokens": {
        "94f10f9b-2139-4f31-ab57-52ac175b9acc": {
            "jwt_token_description": "Token beta",
            "jwt_token_life": 5400,
            "jwt_token_remaining_life": 5395.147431612015
        },
        "2bc0160d-edf4-4ab6-9801-52d185f65b59": {
            "jwt_token_description": "Token alpha",
            "jwt_token_life": 360,
            "jwt_token_remaining_life": 232.19542360305786
        }
    }
}
```

## POST

**Method** : `POST`

**Auth required** : YES

**Permissions required** : None

```
curl -u admin:password --location --request POST 'http://127.0.0.1:25441/api/v1alpha/token' \
--header 'Content-Type: application/json' \
-d '{
    "jwt_token_description": "Token specter",
    "jwt_token_life": "6 hours"
}'
```

As a result, you get all the created tokens.

### Success Response

**Code** : `201 Created`

**Content examples**

### Post Result

```json
{
    "message": "Token generated",
    "jwt_token_id": "b56929f3-54f1-4dc2-9984-9bba615e26e6",
    "jwt_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwiand0X3Rva2VuX2lkIjoiYjU2OTI5ZjMtNTRmMS00ZGMyLTk5ODQtOWJiYTYxNWUyNmU2Iiwiand0X3Rva2VuX2Rlc2NyaXB0aW9uIjoiVG9rZW4gc3BlY3RlciIsImV4cCI6MTY2Mjc0MTczNSwiaWF0IjoxNjYyNzIwMTM1fQ.gBE7S4lJfpPQctt2Dk_581-6v1YOzn4UPHYO18LZpF8",
    "jwt_token_description": "Token specter",
    "jwt_token_life": 21600
}
```

Gives the token details of which the id is passed in the URL and deletes the same token.

**URL** : `/v1alpha/token/<jwt_token_id>`

## GET

**Method** : `GET`

**Auth required** : Yes

**Permissions required** : None

```
curl -u admin:secret --location --request GET 'http://127.0.0.1:25441/api/v1alpha/token/<jwt_token_id>' | jq .
```

### Success Response

**Code** : `200 OK`

**Content examples**

### Get Result 

```json
{
    "message": "Tokens exists",
    "jwt_token_description": "Token alpha",
    "jwt_token_life": 360,
    "jwt_token_life_remaining": 232.19542360305786,
    "expiry_status": "Valid"
}
```
## DELETE

**Method** : `DELETE`

**Auth required** : Yes

**Permissions required** : None

```
curl -u admin:secret --location --request DELETE 'http://127.0.0.1:25441/api/v1alpha/token/<jwt_token_id>' | jq .
```

### Success Response

**Code** : `200 OK`

**Content examples**

### Delete Result
  
```json
{
    "message": "Token deleted"
}
```
