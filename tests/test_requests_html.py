import os
from functools import partial

import pytest
from requests_html import HTMLSession, AsyncHTMLSession, HTML
from requests_file import FileAdapter

# Constants for test parameters
TEST_HTML_PATH = os.path.sep.join((os.path.dirname(os.path.abspath(__file__)), 'python.html'))
TEST_URL = f'file://{TEST_HTML_PATH}'
EXPECTED_ABOUT_LINKS = 6

# Set up sessions for file handling
session = HTMLSession()
session.mount('file://', FileAdapter())

async_session = AsyncHTMLSession()
async_session.mount('file://', FileAdapter())


def get():
    return session.get(TEST_URL)


@pytest.fixture
def async_get(event_loop):
    return partial(async_session.get, TEST_URL)


def test_file_get():
    r = get()
    assert r.status_code == 200, "Expected status code 200"


@pytest.mark.asyncio
async def test_async_file_get(async_get):
    r = await async_get()
    assert r.status_code == 200, "Expected status code 200"


def test_about_class_count():
    r = get()
    about = r.html.find('#about', first=True)
    assert len(about.attrs['class']) == 2, "Expected class count to be 2"


def test_css_selector():
    r = get()
    about = r.html.find('#about', first=True)

    expected_menu_items = [
        'About', 'Applications', 'Quotes', 'Getting Started', 'Help',
        'Python Brochure'
    ]
    
    for menu_item in expected_menu_items:
        assert menu_item in about.text.split('\n'), f"{menu_item} not found in about text"
        assert menu_item in about.full_text.split('\n'), f"{menu_item} not found in about full text"


def test_python_occurrences():
    r = get()
    python_elements = r.html.find(containing='python')
    assert len(python_elements) == 192, "Expected 192 elements containing 'python'"

    for e in python_elements:
        assert 'python' in e.full_text.lower(), "'python' not found in element full text"


def test_about_attributes():
    r = get()
    about = r.html.find('#about', first=True)

    assert 'aria-haspopup' in about.attrs, "'aria-haspopup' attribute not found in about"
    assert len(about.attrs['class']) == 2, "Expected class count to be 2"


def test_about_links_count():
    r = get()
    about = r.html.find('#about', first=True)

    assert len(about.links) == EXPECTED_ABOUT_LINKS, f"Expected {EXPECTED_ABOUT_LINKS} links"
    assert len(about.absolute_links) == EXPECTED_ABOUT_LINKS, f"Expected {EXPECTED_ABOUT_LINKS} absolute links"


@pytest.mark.asyncio
async def test_async_about_links(async_get):
    r = await async_get()
    about = r.html.find('#about', first=True)

    assert len(about.links) == EXPECTED_ABOUT_LINKS, f"Expected {EXPECTED_ABOUT_LINKS} links"
    assert len(about.absolute_links) == EXPECTED_ABOUT_LINKS, f"Expected {EXPECTED_ABOUT_LINKS} absolute links"


def test_search_functionality():
    r = get()
    style = r.html.search('Python is a {} language')[0]
    assert style == 'programming', "Expected 'programming' as the search result"


def test_xpath_validity():
    r = get()
    html = r.html.xpath('/html', first=True)
    assert 'no-js' in html.attrs['class'], "'no-js' not found in HTML class attributes"

    a_hrefs = r.html.xpath('//a/@href')
    assert '#site-map' in a_hrefs, "'#site-map' link not found"


def test_html_loading():
    doc = """<a href='https://httpbin.org'>"""
    html = HTML(html=doc)

    assert 'https://httpbin.org' in html.links, "Expected link not found"
    assert isinstance(html.raw_html, bytes), "Expected raw HTML to be bytes"
    assert isinstance(html.html, str), "Expected HTML content to be a string"


def test_anchor_links():
    r = get()
    r.html.skip_anchors = False

    assert '#site-map' in r.html.links, "'#site-map' link not found"


@pytest.mark.parametrize('url,link,expected', [
    ('http://example.com/', 'test.html', 'http://example.com/test.html'),
    ('http://example.com', 'test.html', 'http://example.com/test.html'),
    ('http://example.com/foo/', 'test.html', 'http://example.com/foo/test.html'),
    ('http://example.com/foo/bar', 'test.html', 'http://example.com/foo/test.html'),
    ('http://example.com/foo/', '/test.html', 'http://example.com/test.html'),
    ('http://example.com/', 'http://xkcd.com/about/', 'http://xkcd.com/about/'),
    ('http://example.com/', '//xkcd.com/about/', 'http://xkcd.com/about/'),
])
def test_absolute_links(url, link, expected):
    head_template = """<head><base href='{}'></head>"""
    body_template = """<body><a href='{}'>Next</a></body>"""

    # Test without `<base>` tag (url is base)
    html = HTML(html=body_template.format(link), url=url)
    assert html.absolute_links.pop() == expected, "Unexpected absolute link without <base> tag"

    # Test with `<base>` tag (url is other)
    html = HTML(
        html=head_template.format(url) + body_template.format(link),
        url='http://example.com/foobar/')
    assert html.absolute_links.pop() == expected, "Unexpected absolute link with <base> tag"


def test_parser_functionality():
    doc = """<a href='https://httpbin.org'>httpbin.org\n</a>"""
    html = HTML(html=doc)

    assert html.find('html'), "HTML element not found"
    assert html.element('a').text().strip() == 'httpbin.org', "Link text does not match"


@pytest.mark.render
def test_render_functionality():
    r = get()
    script = """
    () => {
        return {
            width: document.documentElement.clientWidth,
            height: document.documentElement.clientHeight,
            deviceScaleFactor: window.devicePixelRatio,
        }
    }
    """
    val = r.html.render(script=script)
    for value in ('width', 'height', 'deviceScaleFactor'):
        assert value in val, f"{value} not found in rendered output"

    about = r.html.find('#about', first=True)
    assert len(about.links) == EXPECTED_ABOUT_LINKS, f"Expected {EXPECTED_ABOUT_LINKS} links"


@pytest.mark.render
@pytest.mark.asyncio
async def test_async_render(async_get):
    r = await async_get()
    script = """
    () => {
        return {
            width: document.documentElement.clientWidth,
            height: document.documentElement.clientHeight,
            deviceScaleFactor: window.devicePixelRatio,
        }
    }
    """
    val = await r.html.arender(script=script)
    for value in ('width', 'height', 'deviceScaleFactor'):
        assert value in val, f"{value} not found in async rendered output"

    about = r.html.find('#about', first=True)
    assert len(about.links) == EXPECTED_ABOUT_LINKS, f"Expected {EXPECTED_ABOUT_LINKS} links"
    await r.html.browser.close()


@pytest.mark.render
def test_bare_render_functionality():
    doc = """<a href='https://httpbin.org'>"""
    html = HTML(html=doc)
    script = """
        () => {
            return {
                width: document.documentElement.clientWidth,
                height: document.documentElement.clientHeight,
                deviceScaleFactor: window.devicePixelRatio,
            }
        }
    """
    val = html.render(script=script, reload=False)
    for value in ('width', 'height', 'deviceScaleFactor'):
        assert value in val, f"{value} not found in bare render output"

    assert html.find('html'), "HTML element not found"
    assert 'https://httpbin.org' in html.links, "Expected link not found"


@pytest.mark.render
@pytest.mark.asyncio
async def test_bare_async_render():
    doc = """<a href='https://httpbin.org'>"""
    html = HTML(html=doc, async_=True)
    script = """
        () => {
            return {
                width: document.documentElement.clientWidth,
                height: document.documentElement.clientHeight,
                deviceScaleFactor: window.devicePixelRatio,
            }
        }
    """
    val = await html.arender(script=script, reload=False)
    for value in ('width', 'height', 'deviceScaleFactor'):
        assert value in val, f"{value} not found in bare async render output"

    assert html.find('html'), "HTML element not found"
    assert 'https://httpbin.org' in html.links, "Expected link not found"
    await html.browser.close()


@pytest.mark.render
def test_bare_js_eval_functionality():
    doc = """
    <!DOCTYPE html>
    <html>
    <body>
    <div id="replace">This gets replaced</div>

    <script type="text/javascript">
      document.getElementById("replace").innerHTML = "yolo";
    </script>
    </body>
    </html>
    """

    html = HTML(html=doc)
    html.render()

    assert html.find('#replace', first=True).text == 'yolo', "Expected text not found after JS execution"


@pytest.mark.render
@pytest.mark.asyncio
async def test_bare_js_async_eval():
    doc = """
    <!DOCTYPE html>
    <html>
    <body>
    <div id="replace">This gets replaced</div>

    <script type="text/javascript">
      document.getElementById("replace").innerHTML = "yolo";
    </script>
    </body>
    </html>
    """

    html = HTML(html=doc, async_=True)
    await html.arender()

    assert html.find('#replace', first=True).text == 'yolo', "Expected text not found after async JS execution"
    await html.browser.close()


def test_browser_session():
    """ Test browser instance creation and proper closure when session is closed. """
    session = HTMLSession()
    assert isinstance(session.browser, Browser), "Expected Browser instance"
    assert hasattr(session, "loop"), "Expected session to have a loop attribute"
    session.close()
    # assert count_chromium_process() == 0


def test_browser_process():
    for _ in range(3):
        r = get()
        r.html.render()

        assert r.html.page is None, "Expected page to be None after render"


@pytest.mark.asyncio
async def test_browser_session_fail():
    """ HTMLSession.browser should not be called within an existing event loop. """
    session = HTMLSession()
    with pytest.raises(RuntimeError, match="already running"):
        await session.browser


@pytest.mark.asyncio
async def test_async_browser_session():
    session = AsyncHTMLSession()
    browser = await session.browser
    assert isinstance(browser, Browser), "Expected Browser instance"
    await session.close()
