# Babel multi-language support


## For Translators
Many of you translator volunteers will be new to git/github so we'll start with the basics:


### Create github account, install git
Create a free account at [github.com](https://github.com).

Go to the [Specter Desktop github repository](https://github.com/cryptoadvance/specter-desktop) (aka "repo") and "star" the project at the top right.

On your local computer install `git` by following the instructions [here](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).

_note: terminal/command line instructions often show a dollar sign ($) before the command. You do not need to type in the dollar sign._

For convenience, install the [Github Desktop app](https://desktop.github.com/).


### Clone the Specter Desktop repo
Now you're going to grab a copy of the full Specter Desktop source code, which includes the translation files.

Open the Github Desktop app and add the Specter Desktop repo via "Clone a Repository". On the "URL" tab type in "cryptoadvance/specter-desktop":

<img src="img/add_repo.png">

Select where you want to save the source code on your local computer and hit "Clone".


### Editing a translation file
Before you begin editing, ALWAYS go to Github Desktop and click the "Fetch origin" button at the top right. This pulls down all the latest changes from the repo. We'll all try our best to make sure that only one person is making changes at a time on a given translation file but if a change is submitted ahead of you, "Fetch origin" will grab it and get you in sync. We want to avoid messy conflicts where two or more people have edited the same translation file.

You'll be working with a `messages.po` file for each specific language. This file lists all the text that is displayed in Specter in English as a series of "msgid"s. Your job is to complete the matching translation in the "msgstr" field.

The `messages.po` text format is fairly straightforward but can be a little hard to work with, especially for multi-line phrases. Instead, we recommend that translators use the free tool [Poedit](https://poedit.net/download).

Navigate to the directory where you cloned the repo. The translation files can be found organized by two-letter language code (e.g. Spanish = "es") under `src/cryptoadvance/specter/translations`.

In Poedit open the `messages.po` file for your target langage (e.g. Spanish: [src/cryptoadvance/specter/translations/es/LC_MESSAGES/messages.po](../src/cryptoadvance/specter/translations/es/LC_MESSAGES/messages.po)).

Add or update translations, then save your changes.



### Submitting your changes
The updated `messages.po` file should now show up in Github Desktop as having changes.

If your changes are directly related to a Github issue, include "fixes #1234" (but use the actual issue number, obviously!) in the optional "Description" field.

Click the "Commit" button at the bottom. The "Fetch origin" button at the top right will now show that you have a new commit to push up to the repo.

_TODO: Confirm how these next steps work when you don't have write-access to the repo!_

Your change will need to be submitted as a pull request (PR). Once a reviewer accepts the changes, your contributions will be merged into the main Specter Desktop code repository. You will officially be a Specter Desktop open source contributor!



## For Developers:
### "Wrapping" text for translation
All you have to do in your code is wrap each piece of English text with the `ugettext` shorthand `_()`:
* Wrap jinja template text: `<p>Hello, world!</p>` becomes `<p>{{ _('Hello, world!') }}</p>`
* Wrap python strings: `error="No device was selected."` becomes `error=_("No device was selected.")`

There are more complex workarounds for strings that are dynamically constructed as well as locale-specific date and number formatting.

TODO: Link to resource


### Rescanning for text that needs translations
Re-generate the `messages.pot` file:
```
pybabel extract -F babel/babel.cfg -o babel/messages.pot .
```
This will rescan all wrapped text, picking up new strings as well as updating existings strings that have been edited.

Then run `update`:
```
pybabel update -i babel/messages.pot -d src/cryptoadvance/specter/translations
```

Any newly wrapped text strings will be added to each `messages.po` file. Altered strings will be flagged as needing review to see if the existing translations can still be used.

Once the next round of translations is complete, recompile the results:
```
pybabel compile -d src/cryptoadvance/specter/translations
```


### Adding support for another language
Assuming you have `extract`ed an updated `messages.pot`, all you have to do is generate the initial version of each new language file:
```
pybabel init -i babel/messages.pot -d src/cryptoadvance/specter/translations -l es
pybabel init -i babel/messages.pot -d src/cryptoadvance/specter/translations -l fr
pybabel init -i babel/messages.pot -d src/cryptoadvance/specter/translations -l de
```
