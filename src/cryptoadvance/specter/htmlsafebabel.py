from flask_babel import Babel, get_translations
from jinja2.utils import markupsafe
import html


class HTMLSafeBabel(Babel):
    """
    A subclass of Flash-Babel which automatically HTML escapes gettext strings

    Jinja2 treats gettext() values as HTML safe by default. This function wraps
    the gettext functions to explictly HTML escape the translated strings before
    they are used in a template.
    """

    def init_app(self, app, *args, **kwargs):
        super(HTMLSafeBabel, self).init_app(app, *args, **kwargs)
        if self._configure_jinja:
            app.jinja_env.install_gettext_callables(
                lambda x: self.reescape_string(get_translations().ugettext(x)),
                lambda s, p, n: self.reescape_string(
                    get_translations().ungettext(s, p, n)
                ),
                newstyle=True,
            )

    @staticmethod
    def reescape_string(escaped_string):
        """
        Decode HTML entities and re-encoded safely using the Jinja HTML escaper.

        Existing entities need to be decoded first to avoid double-encoding.
        """
        return markupsafe.Markup.escape(html.unescape(escaped_string))
