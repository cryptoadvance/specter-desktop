# Babel multi-language support


## For Developers:
### Initial steps
_Should only need to be run once to initialize translations and then once per new language._

Extract all to-be-translated wrapped text strings:
```
pybabel extract -F babel/babel.cfg -o babel/messages.pot .
```

Generate the initial version of each new language file:
```
pybabel init -i babel/messages.pot -d src/cryptoadvance/specter/translations -l es
pybabel init -i babel/messages.pot -d src/cryptoadvance/specter/translations -l fr
pybabel init -i babel/messages.pot -d src/cryptoadvance/specter/translations -l de
```

Manually edit the `messages.po` file for that new language and add translations.

Then compile it:
```
pybabel compile -d src/cryptoadvance/specter/translations
```


### Adding new translation strings or updating existing ones
Re-generate the `messages.pot` file:
```
pybabel extract -F babel/babel.cfg -o babel/messages.pot .
```

Then run `update`:
```
pybabel update -i babel/messages.pot -d src/cryptoadvance/specter/translations
```

Any newly wrapped text strings will be added to each `messages.po` file. Altered strings will be flagged as needing review to see if the existing translations can still be used.

Once the next round of translations is complete, recompile the results:
```
pybabel compile -d src/cryptoadvance/specter/translations
```


## For Translators
Translators can use the free tool [Poedit](https://poedit.net/download) to add their translations to the `messages.po` file for each language. The translation files can be found organized by two-letter language code (e.g. Spanish = "es") under `src/cryptoadvance/specter/translations`.

Load the `messages.po` file for your target langage (e.g. Spanish: [src/cryptoadvance/specter/translations/es/LC_MESSAGES/messages.po](../src/cryptoadvance/specter/translations/es/LC_MESSAGES/messages.po)) in Poedit, add or update translations, and then save your changes.

The updated `messages.po` file should be submitted as a pull request (PR) to the [Specter-Desktop github repo](https://github.com/cryptoadvance/specter-desktop).

TODO: record tutorial screencast for how to do the github submission.