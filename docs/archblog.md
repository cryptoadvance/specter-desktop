# Purpose
Let's find a place to docoment non straightforward design decisions.

## 19nd Feb 2020 - Kim
The ApplicationFactory-pattern is not that straightforward. There are loads of pifalls and different ways to go. While finding a proper way to do it, one thing became clear: You need to separate the instantiation and the initialisation of the Application.

(from singleton.py)
```python __main__.py
app = logic.create_app()
app.app_context().push()
# (...)
logic.init_app(app)
```
If you would put everything in the create-call, you can't import code which is dependent on an initialized ApplicationContext, you can't do "from flask import current_app". So you have to push the app_context but on the other side, you don't want to do that from within the create_app-function because this would be a quite shitty side-effect which srews up your whole dependency injection.