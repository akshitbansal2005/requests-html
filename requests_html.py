import sys
import asyncio
from urllib.parse import urlparse, urlunparse, urljoin
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures._base import TimeoutError
from functools import partial
from typing import Set, Union, List, MutableMapping, Optional

import pyppeteer
import requests
import http.cookiejar
from pyquery import PyQuery

from fake_useragent import UserAgent
from lxml.html.clean import Cleaner
import lxml
from lxml import etree
from lxml.html import HtmlElement
from lxml.html import tostring as lxml_html_tostring
from lxml.html.soupparser import fromstring as soup_parse
from parse import search as parse_search
from parse import findall, Result
from w3lib.encoding import html_to_unicode

DEFAULT_ENCODING = 'utf-8'
DEFAULT_URL = 'https://example.org/'
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8'
DEFAULT_NEXT_SYMBOL = ['next', 'more', 'older']

cleaner = Cleaner()
cleaner.javascript = True
cleaner.style = True

useragent = None

# Typing.
_Find = Union[List['Element'], 'Element']
_XPath = Union[List[str], List['Element'], str, 'Element']
_Result = Union[List['Result'], 'Result']
_HTML = Union[str, bytes]
_BaseHTML = str
_UserAgent = str
_DefaultEncoding = str
_URL = str
_RawHTML = bytes
_Encoding = str
_LXML = HtmlElement
_Text = str
_Search = Result
_Containing = Union[str, List[str]]
_Links = Set[str]
_Attrs = MutableMapping
_Next = Union['HTML', List[str]]
_NextSymbol = List[str]

# Sanity checking: Use explicit version checking instead of assert to avoid issues with optimizations
if sys.version_info < (3, 6):
    raise RuntimeError('Requests-HTML requires Python 3.6+!')


class MaxRetries(Exception):
    """Custom exception to handle max retry logic."""
    def __init__(self, message):
        self.message = message


class BaseParser:
    """A basic HTML/Element Parser for Humans.

    :param element: The element from which to base the parsing upon.
    :param default_encoding: The encoding to use as fallback.
    :param html: HTML from which to base the parsing (optional).
    :param url: The URL from which the HTML originated, useful for absolute links.
    """

    def __init__(self, *, element, default_encoding: _DefaultEncoding = DEFAULT_ENCODING, html: _HTML = None, url: _URL) -> None:
        self.element = element
        self.url = url
        self.skip_anchors = True
        self.default_encoding = default_encoding
        self._encoding = None
        self._html = html.encode(DEFAULT_ENCODING) if isinstance(html, str) else html
        self._lxml = None
        self._pq = None

    @property
    def raw_html(self) -> _RawHTML:
        """Bytes representation of the HTML content."""
        if self._html:
            return self._html
        # If raw HTML isn't provided, it is constructed from the element.
        return etree.tostring(self.element, encoding='unicode').strip().encode(self.encoding)

    @property
    def html(self) -> _BaseHTML:
        """Unicode representation of the HTML content."""
        if self._html:
            return self.raw_html.decode(self.encoding, errors='replace')
        return etree.tostring(self.element, encoding='unicode').strip()

    @html.setter
    def html(self, html: str) -> None:
        """Setter for HTML content."""
        self._html = html.encode(self.encoding)

    @raw_html.setter
    def raw_html(self, html: bytes) -> None:
        """Setter for raw HTML content."""
        self._html = html

    @property
    def encoding(self) -> _Encoding:
        """Determine the encoding from the HTML content or fallback."""
        if self._encoding:
            return self._encoding

        # If no encoding has been set, determine it from the HTML or use the default.
        if self._html:
            detected_encoding, _ = html_to_unicode(self.default_encoding, self._html)
            self._encoding = detected_encoding

            # Check that the HTML can be decoded properly
            try:
                self.raw_html.decode(self._encoding, errors='replace')
            except (UnicodeDecodeError, TypeError):
                self._encoding = self.default_encoding

        # Ensure a default is returned if no encoding is detected
        return self._encoding or self.default_encoding

    @encoding.setter
    def encoding(self, enc: str) -> None:
        """Setter for encoding."""
        self._encoding = enc

    @property
    def pq(self) -> PyQuery:
        """Return the PyQuery object for the HTML content."""
        if self._pq is None:
            self._pq = PyQuery(self.lxml)  # Lazy load when accessed
        return self._pq

    @property
    def lxml(self) -> HtmlElement:
        """Return the lxml object for the HTML content."""
        if self._lxml is None:
            try:
                self._lxml = soup_parse(self.html, features='html.parser')
            except ValueError:
                self._lxml = lxml.html.fromstring(self.raw_html)
        return self._lxml

    @property
def text(self) -> _Text:
    """Return the text content of the element."""
    return self.pq.text()

@property
def full_text(self) -> _Text:
    """Return the full text content (including links) of the element."""
    return self.lxml.text_content()

def find(
    self,
    selector: str = "*",
    *,
    containing: _Containing = None,
    clean: bool = False,
    first: bool = False,
    _encoding: str = None
) -> _Find:
    """
    Find elements matching the CSS selector.

    :param selector: CSS Selector to use.
    :param containing: Only return elements that contain the provided text.
    :param clean: Sanitize the found HTML by removing <script> and <style> tags.
    :param first: Return only the first matching element.
    :param _encoding: The encoding format to use.
    :return: A single Element or a list of Elements.
    """
    if isinstance(containing, str):
        containing = [containing]

    encoding = _encoding or self.encoding
    elements = [
        Element(element=found, url=self.url, default_encoding=encoding)
        for found in self.pq(selector)
    ]

    if containing:
        elements = [
            element for element in elements
            if any(c.lower() in element.full_text.lower() for c in containing)
        ]

    if clean:
        for element in elements:
            cleaned_html = cleaner.clean_html(element.lxml)
            element.raw_html = lxml_html_tostring(cleaned_html)

    return _get_first_or_list(elements, first)

def xpath(
    self,
    selector: str,
    *,
    clean: bool = False,
    first: bool = False,
    _encoding: str = None
) -> _XPath:
    """
    Find elements matching the XPath selector.

    :param selector: XPath Selector to use.
    :param clean: Sanitize the found HTML by removing <script> and <style> tags.
    :param first: Return only the first matching element.
    :param _encoding: The encoding format to use.
    :return: A single Element or a list of Elements or strings.
    """
    selected = self.lxml.xpath(selector)
    encoding = _encoding or self.encoding

    elements = []
    for selection in selected:
        if isinstance(selection, (etree._ElementStringResult, str)):
            elements.append(str(selection))
        elif isinstance(selection, etree._Element):
            elements.append(
                Element(element=selection, url=self.url, default_encoding=encoding)
            )
        else:
            elements.append(selection)

    if clean:
        for element in elements:
            if isinstance(element, Element):
                cleaned_html = cleaner.clean_html(element.lxml)
                element.raw_html = lxml_html_tostring(cleaned_html)

    return _get_first_or_list(elements, first)

def search(self, template: str) -> Optional[Result]:
    """
    Search the element's HTML for the given parse template.

    :param template: The parse template to use.
    :return: A Result object if a match is found, otherwise None.
    """
    return parse_search(template, self.html)

def search_all(self, template: str) -> List[Result]:
    """
    Search the element's HTML for all occurrences of the given parse template.

    :param template: The parse template to use.
    :return: A list of Result objects.
    """
    return [match for match in findall(template, self.html)]

# Helper function to return the first element or the list
def _get_first_or_list(elements, first):
    if first:
        return elements[0] if elements else None
    return elements

   @property
def links(self) -> _Links:
    """All found links on the page in their original form."""
    
    def gen_links():
        for link in self.find('a'):
            href = link.attrs.get('href', '').strip()
            if href and not href.startswith(('#', 'javascript:', 'mailto:')) and (not href.startswith('#') or not self.skip_anchors):
                yield href

    return set(gen_links())

def _make_absolute(self, link: str) -> str:
    """Converts a relative link to an absolute link based on the base URL."""

    # Parse the link
    parsed_link = urlparse(link)._asdict()

    # If link is relative, join it with the base URL
    if not parsed_link['netloc']:
        return urljoin(self.base_url, link)

    # If the link has no scheme, add the scheme from the base URL
    if not parsed_link['scheme']:
        base_scheme = urlparse(self.base_url).scheme
        parsed_link['scheme'] = base_scheme

    # Reconstruct the full URL
    return urlunparse(parsed_link.values())

@property
def absolute_links(self) -> _Links:
    """All found links on the page, converted to absolute URLs."""
    
    return {self._make_absolute(link) for link in self.links}

@property
def base_url(self) -> _URL:
    """Determine the base URL for the page, with support for the <base> tag."""
    
    # Check if the page has a <base> tag, and use its href if available
    base_tag = self.find('base', first=True)
    if base_tag:
        base_href = base_tag.attrs.get('href', '').strip()
        if base_href:
            return base_href

    # Fallback to the URL of the current page, with the path adjusted
    parsed_url = urlparse(self.url)._asdict()
    # Remove everything after the last '/' in the path to get the base path
    parsed_url['path'] = '/'.join(parsed_url['path'].split('/')[:-1]) + '/'

    return urlunparse(parsed_url.values())

class Element(BaseParser):
    """An element of HTML.

    :param element: The element from which to base the parsing upon.
    :param url: The URL from which the HTML originated, used for ``absolute_links``.
    :param default_encoding: Which encoding to default to.
    """

    __slots__ = [
        'element', 'url', 'skip_anchors', 'default_encoding', '_encoding',
        '_html', '_lxml', '_pq', '_attrs', 'session', 'tag', 'lineno'
    ]

    def __init__(self, *, element, url: _URL, default_encoding: _DefaultEncoding = None) -> None:
        super().__init__(element=element, url=url, default_encoding=default_encoding)
        self.element = element
        self.tag = element.tag
        self.lineno = element.sourceline
        self._attrs = None

    def __repr__(self) -> str:
        attrs = ['{}={}'.format(attr, repr(self.attrs[attr])) for attr in self.attrs]
        return f"<Element {self.tag!r} {' '.join(attrs)}>"

    @property
    def attrs(self) -> _Attrs:
        """Returns a dictionary of the attributes of the :class:`Element <Element>`."""
        if self._attrs is None:
            self._attrs = {k: v for k, v in self.element.items()}

            # Split class and rel attributes as there are usually many values.
            for attr in ['class', 'rel']:
                if attr in self._attrs:
                    self._attrs[attr] = tuple(self._attrs[attr].split())

        return self._attrs


class HTML(BaseParser):
    """An HTML document, ready for parsing.

    :param url: The URL from which the HTML originated, used for ``absolute_links``.
    :param html: HTML content to parse (optional).
    :param default_encoding: The default encoding for the HTML.
    """

    def __init__(self, *, session: Union['HTMLSession', 'AsyncHTMLSession'] = None, url: str = DEFAULT_URL, html: _HTML, default_encoding: str = DEFAULT_ENCODING, async_: bool = False) -> None:
        
        if isinstance(html, str):
            html = html.encode(default_encoding)

        pq = PyQuery(html)
        super().__init__(
            element=pq('html') or pq.wrapAll('<html></html>')('html'),
            html=html,
            url=url,
            default_encoding=default_encoding
        )
        self.session = session or (async_ and AsyncHTMLSession()) or HTMLSession()
        self.page = None
        self.next_symbol = [DEFAULT_NEXT_SYMBOL]

    def __repr__(self) -> str:
        return f"<HTML url={self.url!r}>"

    def next(self, fetch: bool = False, next_symbol: _NextSymbol = None) -> _Next:
        """Attempts to find the next page. If ``fetch`` is ``True``,
        returns the :class:`HTML <HTML>` object for the next page, 
        otherwise returns the next page URL.
        """
        next_symbol = next_symbol or self.next_symbol

        def find_next():
            candidates = self.find('a', containing=next_symbol)

            for candidate in candidates:
                href = candidate.attrs.get('href')
                if href:
                    # Prioritize 'next' rel or 'next' in class attributes.
                    if 'next' in candidate.attrs.get('rel', []):
                        return href
                    if any('next' in cls for cls in candidate.attrs.get('class', [])):
                        return href
                    if 'page' in href:
                        return href

            return candidates[-1].attrs.get('href') if candidates else None

        next_url = find_next()

        if next_url:
            full_url = self._make_absolute(next_url)
            if fetch:
                return self.session.get(full_url)
            return full_url
        return None

    def __iter__(self):
        next_page = self
        while next_page:
            yield next_page
            next_page = next_page.next(fetch=True, next_symbol=self.next_symbol)

    def __next__(self):
        return self.next(fetch=True, next_symbol=self.next_symbol)

    def __aiter__(self):
        return self

    async def __anext__(self):
        next_url = self.next(fetch=False, next_symbol=self.next_symbol)
        if next_url:
            response = await self.session.get(next_url)
            return response.html
        raise StopAsyncIteration

    def add_next_symbol(self, next_symbol: str):
        """Add a next symbol if it's not already present."""
        if next_symbol not in self.next_symbol:
            self.next_symbol.append(next_symbol)

    async def _async_render(self, *, url: str, script: str = None, scrolldown: int = 0, sleep: int = 1, wait: float = 1.0, reload: bool = False, content: Optional[str] = None, timeout: Union[float, int] = 10, keep_page: bool = False, cookies: list = [{}]):
        """Handles page creation and rendering JavaScript-heavy pages."""
        try:
            page = await self.browser.newPage()
            await asyncio.sleep(wait)

            if cookies:
                for cookie in cookies:
                    await page.setCookie(cookie)

            if reload:
                await page.goto(url, options={'timeout': int(timeout * 1000)})
            else:
                await page.goto(f'data:text/html,{self.html}', options={'timeout': int(timeout * 1000)})

            result = None
            if script:
                result = await page.evaluate(script)

            if scrolldown:
                for _ in range(scrolldown):
                    await page.keyboard.down('PageDown')
                    await asyncio.sleep(sleep)
                await page.keyboard.up('PageDown')
            else:
                await asyncio.sleep(sleep)

            content = await page.content()
            if not keep_page:
                await page.close()
                return content, result, None

            return content, result, page
        except TimeoutError as e:
            if page:
                await page.close()
            raise e


   def _convert_cookiejar_to_render(self, session_cookiejar):
    """
    Convert HTMLSession.cookies:cookiejar[] for browser.newPage().setCookie
    """
    # Define the required keys for the cookie dictionary.
    keys = ['name', 'value', 'url', 'domain', 'path', 'sameSite', 'expires', 'httpOnly', 'secure']

    cookie_render = {}
    # Iterate over each key and check if it exists in the cookie jar.
    for key in keys:
        value = getattr(session_cookiejar, key, None)
        if value is not None:
            cookie_render[key] = value
    return cookie_render


def _convert_cookiesjar_to_render(self):
    """
    Convert HTMLSession.cookies for browser.newPage().setCookie.
    Return a list of dict.
    """
    if isinstance(self.session.cookies, http.cookiejar.CookieJar):
        return [self._convert_cookiejar_to_render(cookie) for cookie in self.session.cookies]
    return None


def render(self, retries: int = 8, script: str = None, wait: float = 0.2, scrolldown=False, sleep: int = 0, reload: bool = True, timeout: Union[float, int] = 8.0, keep_page: bool = False, cookies: list = [{}], send_cookies_session: bool = False):
    """
    Reloads the response in Chromium, and replaces HTML content with an updated version, with JavaScript executed.
    """
    self.browser = self.session.browser  # Automatically create a event loop and browser
    content = None

    # Automatically set Reload to False, if example URL is being used.
    if self.url == DEFAULT_URL:
        reload = False

    if send_cookies_session:
        cookies = self._convert_cookiesjar_to_render()

    for _ in range(retries):
        if content:
            break
        try:
            content, result, page = self.session.loop.run_until_complete(
                self._async_render(
                    url=self.url, script=script, sleep=sleep, wait=wait, 
                    content=self.html, reload=reload, scrolldown=scrolldown, 
                    timeout=timeout, keep_page=keep_page, cookies=cookies
                )
            )
        except TimeoutError:
            raise TimeoutError("Rendering the page took too long. Consider increasing the timeout.")
        except Exception as e:
            logging.error(f"Error during rendering: {e}")

    if not content:
        raise MaxRetries("Unable to render the page. Try increasing timeout")

    html = HTML(url=self.url, html=content.encode(DEFAULT_ENCODING), default_encoding=DEFAULT_ENCODING)
    self.__dict__.update(html.__dict__)
    self.page = page
    return result


async def arender(self, retries: int = 8, script: str = None, wait: float = 0.2, scrolldown=False, sleep: int = 0, reload: bool = True, timeout: Union[float, int] = 8.0, keep_page: bool = False, cookies: list = [{}], send_cookies_session: bool = False):
    """
    Async version of render. Takes the same parameters.
    """
    self.browser = await self.session.browser
    content = None

    # Automatically set Reload to False, if example URL is being used.
    if self.url == DEFAULT_URL:
        reload = False

    if send_cookies_session:
        cookies = self._convert_cookiesjar_to_render()

    for _ in range(retries):
        if content:
            break
        try:
            content, result, page = await self._async_render(
                url=self.url, script=script, sleep=sleep, wait=wait, 
                content=self.html, reload=reload, scrolldown=scrolldown, 
                timeout=timeout, keep_page=keep_page, cookies=cookies
            )
        except TimeoutError:
            raise TimeoutError("Rendering the page took too long. Consider increasing the timeout.")
        except Exception as e:
            logging.error(f"Error during rendering: {e}")

    if not content:
        raise MaxRetries("Unable to render the page. Try increasing timeout")

    html = HTML(url=self.url, html=content.encode(DEFAULT_ENCODING), default_encoding=DEFAULT_ENCODING)
    self.__dict__.update(html.__dict__)
    self.page = page
    return result


class HTMLResponse(requests.Response):
    """An HTML-enabled :class:`requests.Response <requests.Response>` object.
    Extends `requests.Response` with an intelligent ``.html`` property for parsing HTML content.
    """

    def __init__(self, session: Union['HTMLSession', 'AsyncHTMLSession']) -> None:
        super().__init__()
        self._html = None  # HTML parsing is lazy-loaded
        self.session = session

    @property
    def html(self) -> 'HTML':
        """Lazy-load and cache the HTML content when first accessed."""
        if not self._html:
            self._html = HTML(session=self.session, url=self.url, html=self.content, default_encoding=self.encoding)
        return self._html

    @classmethod
    def _from_response(cls, response, session: Union['HTMLSession', 'AsyncHTMLSession']) -> 'HTMLResponse':
        """Create an HTMLResponse object from a standard Response."""
        html_response = cls(session=session)
        html_response.__dict__.update(response.__dict__)
        return html_response


def user_agent(style=None) -> str:
    """Returns a user-agent string, either a default or based on a given style."""
    global useragent
    if (not useragent) and style:
        useragent = UserAgent()

    return useragent.get(style, DEFAULT_USER_AGENT) if style else DEFAULT_USER_AGENT


def _get_first_or_list(items, first=False):
    """Returns the first element of a list if requested, else returns the whole list."""
    if first:
        return items[0] if items else None
    return items


class BaseSession(requests.Session):
    """ A session class with additional capabilities such as cookie persistence, 
    user-agent spoofing, and browser launching for rendering JavaScript content.
    """

    def __init__(self, mock_browser: bool = True, verify: bool = True, browser_args: list = ['--no-sandbox']):
        super().__init__()

        # Spoof a web browser's user-agent if required.
        if mock_browser:
            self.headers['User-Agent'] = user_agent()

        # Hook the response to convert it to an HTMLResponse.
        self.hooks['response'].append(self.response_hook)
        self.verify = verify
        self.__browser_args = browser_args

    def response_hook(self, response, **kwargs) -> HTMLResponse:
        """Ensures the response is converted to an HTMLResponse and has correct encoding."""
        if not response.encoding:
            response.encoding = DEFAULT_ENCODING
        return HTMLResponse._from_response(response, self)

    @property
    async def browser(self):
        """Launch the browser if it hasn't been launched already."""
        if not hasattr(self, "_browser"):
            self._browser = await pyppeteer.launch(
                ignoreHTTPSErrors=not self.verify, 
                headless=True, 
                args=self.__browser_args
            )
        return self._browser


class HTMLSession(BaseSession):
    """A synchronous session with HTML rendering capabilities using a browser."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def browser(self):
        """Launch a browser synchronously using asyncio's event loop."""
        if not hasattr(self, "_browser"):
            self.loop = asyncio.get_event_loop()
            if self.loop.is_running():
                raise RuntimeError("Cannot use HTMLSession within an existing event loop. Use AsyncHTMLSession instead.")
            self._browser = self.loop.run_until_complete(super().browser)
        return self._browser

    def close(self):
        """Close the browser (if opened) and the session."""
        if hasattr(self, "_browser"):
            self.loop.run_until_complete(self._browser.close())
        super().close()


import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

class AsyncHTMLSession(BaseSession):
    """An asynchronous consumable session with support for executing 
    HTTP requests in parallel and managing browser interactions.
    """

    def __init__(self, loop=None, workers=None, mock_browser: bool = True, *args, **kwargs):
        """Initialize the session with a custom event loop and thread pool.

        :param loop: An existing asyncio event loop to use.
        :param workers: Number of threads for executing async calls.
                         Defaults to (number of processors) x 5 if not provided.
        """
        super().__init__(mock_browser=mock_browser, *args, **kwargs)
        
        # Set up the event loop and thread pool for handling requests
        self.loop = loop or asyncio.get_event_loop()
        self.thread_pool = ThreadPoolExecutor(max_workers=workers or (os.cpu_count() * 5))

    def request(self, *args, **kwargs):
        """Overrides the request method to run in a separate thread."""
        func = partial(super().request, *args, **kwargs)
        return self.loop.run_in_executor(self.thread_pool, func)

    async def close(self):
        """Close the browser if it was created, then close the session."""
        if hasattr(self, "_browser"):
            await self._browser.close()
        await super().close()  # Ensure the base class close method is awaited

    def run(self, *coros):
        """Run multiple coroutines concurrently and return their results.

        :param coros: Coroutines to be executed.
        :return: A list of results corresponding to the order of coros.
        """
        tasks = [asyncio.ensure_future(coro()) for coro in coros]
        done, _ = self.loop.run_until_complete(asyncio.wait(tasks))
        return [task.result() for task in done]

