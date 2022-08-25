# Perfomance Hints

Specter is a very flexible tool. It has several deployment models and different ways to use it. Some people use it on Node implementations like Umbrel, MyNode or RaspiBlitz. Many people use it as dedicated Electron desktop-app. Tor is also used a lot. Specter needs a Bitcoin Core node either on the same machine or on a different one. All these different usage differences do have performance impacts which might not be obvious for the average user:
* If two components are talking via the network and are not on the same computer, that might slow down things
* If components are talking via Tor, this will have an impact on performance

So here is a small checklist which you can use to improve your performance on Specter Desktop:

## Mempool.Space
Currently (`v1.7.0`) , Mempool.Space is the default fee-estimation implementation and it's used via Tor. Changing it to Bitcoin Core in the general settings should speed up performance.

## Bitcoin Core via Tor
It's possible to connect to your Bitcoin Node via Tor. However, if you want to have access to your Specter instance from the street, perhaps rather expose Specter over Tor. If you want or have to run Bitcoin Core on a different machine than Specter, it is more advisable do that on the same network at home and not via Tor.

## Tor only-mode
Yes, we have a Tor only-mode but it's also coming with a huge performance impact. Think twice before you activate it and keep it in mind while waiting.
