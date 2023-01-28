Inspired by strawberry and the small [POC](https://github.com/k9ert/nomstr)

# potential issues

There might be a dependency conflict:
```
  typing_extensions<5.0.0,>=3.7.4 (from strawberry-graphql==0.155.2->-r requirements.in (line 35))
  typing-extensions<4.0,>=3.7 (from hwi==2.1.1->-r requirements.in (line 11))
```