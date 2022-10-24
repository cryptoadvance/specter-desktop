# Service configuration
In order to separate the service-configuration from the main-configuration, you can specify your config in a file called `config.py`. Its structure is similiar to the specter-wide `config.py`, e.g.:

```python
class BaseConfig():
    MYSERVICE_API_URL="https://dev-api.myservice.com"

class ProductionConfig(BaseConfig):
    MYSERVICE_API_URL="https://api.myservice.com"
```

In your code, you can access the correct value as in any other flask-code, like `api_url = app.config.get("MYSERVICE_API_URL")`. If the instance is running a config (e.g. `DevelopmentConfig`) which is not available in your service-specific config (as above), the inheritance-hirarchy from the mainconfig will get traversed and the first hit will get configured. In this example, it would be `BaseConfig`.