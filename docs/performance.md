# Perfomance Hints

Specter is a very flexible tool. It has several deployment-models and different ways to use it. Some people use it on Node-implementations like umbrel, MyNode or raspiblitz. Many people use it as dedicated Desktop-Electron-Apps. Also tor is used a lot. Specter needs a Bitcoin Core node either on the same machine or on a different one. All these different usage differences do have performance impacts which might not be obvious for the average users:
* If two components are talking via the network and are not on the same computer, that might slow down things
* If components are talking via tor, this will have an impact on performance

So here is a small checklist which you can use to improve your performance on specter-Desktop:

## Mempool-Space
Currently (`v1.7.0`) , Mempool-space is the default fee-estimation implementation and it's used via tor. Changing it to Bitcoin-Core in the General settings should speed it up.

# Bitcoin Core via Tor
It's possible to connect to your Bitcoin-Node via Tor. This doesn't make so much sense, though. If you want to have access to your specter from the street, expose Specter over Tor. If you want to run Bitcoin Core on a different machine than specter, do that on the same network at home but not via Tor.

# Tor-only-mode
Yes, we have a tor-only mode but it's also coming with a huge performance impact. Think twice before you activate it and have it on your mind while waiting.
