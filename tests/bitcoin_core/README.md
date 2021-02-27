These files have been directly copied from bitcoin core's `test` directory in order to test against more complicated node conditions.

* messages.py:
    * Copied as-is. There are quite a number of classes and utility functions in here and it was more straightforward to leave them all intact.
    * `siphash` and `util` imports edited to relative imports so they'll work within the context of Specter's test runner.
* siphash.py:
    * Copied as-is due to its simplicity.
* util.py:
    * Heavily stripped down to its bare minimum.
    * Edits to `create_lots_of_big_transactions` to be compatible with Specter's test suite node handling.
