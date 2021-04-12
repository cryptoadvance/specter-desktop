We have a long going issue with travis-ci which is flagging us for abuse-detection every now and then. The abuse-detection works based on users AND repos, in their words:

> This is a part of our abuse prevention system, which blocks a repo if it looks like someone is trying to mine cryptocurrency.

 So each individual user can be whitelisted but you can't whitelist a whole repo. As a result, every new developer creating a new PR needs to be whitelisted.

 But that whitelisting only lasts for so long. So after some time, whitelisted people might get flagged again.

 We don't have a reliable solution yet, so right now we just send a mail again.

# How to whitelist efficiently

Here is a template to write an email to support@travis-ci.com

```
Hi Support,

unfortunately we have been suffering from the abuse-detection system (again).

Please whitelist @someGuy as he wants to contribute to our repo in https://github.com/cryptoadvance/specter-desktop/blob/master/docs/travis-ci-abuse-detection.md.

For further details, please have a look at [insert link to this document]

Further references where this happened in the past:
* #11504
* #13317
* #13674
* #21103
* #23360
* #25690
* #25896
* #26838
* #28084

Thanks

```



When we're asking for a whitelisting, you usually get this question:
 
> Thanks for the email and apologies for the issue.
> 
> This is a part of our abuse prevention system, which blocks a repo if it looks like someone is trying to mine cryptocurrency. It is an evolving system, as we work to ensure our service is reliable and performant for the community and our customers. We make every attempt to avoid false positives, but they do happen, and we know this can cause disruptions in your work. Could I ask how you're using Travis for this repository, and how you're using cryptocurrency in relation to Travis?

This question has been answered first back in Oct 2019 for the junction-project:

> thanks for getting in contact. I understand your concerns. The work i'm doing here is for the junction-project: https://github.com/justinmoon/junction.
> Junction is a coordinator-software for bitcoin-hardware-wallets. As such, it's highly dependent on the status of a bitcoin-full-node. So the project needs, for integration-testing purposes, setup a bitcoin-full-node in order to contact its API and verify that the API is still functioning for junction.
> 
> The code for that
> https://github.com/k9ert/junction/blob/cicd/.travis.yml#L10-L44
> https://github.com/k9ert/junction/blob/cicd/test/install_bitcoind.sh
> is heavily borrowed from the HWI-bitcoin-core-project:
> https://github.com/bitcoin-core/HWI/blob/master/test/setup_environment.sh#L165-L187
> which has a very similar issue: It has a dependency towards bitcoin and needs to test compatibility with it.
> 
> These topics are also discussed here:
> https://github.com/justinmoon/junction/issues/9
> and especially:
> https://github.com/justinmoon/junction/issues/27
> 
> Does that make sense? If you whitelist my repo, can you please also whitelist justin's upstream-repo?


