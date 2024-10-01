import pytest
from requests_html import HTMLSession, AsyncHTMLSession, HTMLResponse

urls = [
    'https://xkcd.com/1957/',
    'https://www.reddit.com/',
    'https://github.com/psf/requests-html/issues',
    'https://discord.com/category/engineering',
    'https://stackoverflow.com/',
    'https://www.frontiersin.org/',
    'https://azure.microsoft.com/en-us'
]

@pytest.fixture(scope='module')
def html_session():
    """Fixture for HTMLSession."""
    session = HTMLSession()
    yield session
    session.close()


@pytest.mark.parametrize('url', urls)
@pytest.mark.internet
def test_pagination(html_session, url: str):
    r = html_session.get(url)
    assert r.html, f"Failed to retrieve HTML content for {url}"


@pytest.mark.parametrize('url', urls)
@pytest.mark.internet
@pytest.mark.asyncio
async def test_async_pagination(url):
    asession = AsyncHTMLSession()
    r = await asession.get(url)
    
    # Check if the HTML is iterable
    assert await r.html.__anext__() is not None, f"Failed to retrieve HTML content for {url}"
    await asession.close()


@pytest.mark.internet
@pytest.mark.asyncio
async def test_async_run():
    asession = AsyncHTMLSession()

    async def fetch_url(url):
        return await asession.get(url)

    async_list = [fetch_url(url) for url in urls]

    responses = await asession.run(*async_list)

    assert len(responses) == len(urls), "Number of responses does not match number of URLs"
    for response in responses:
        assert isinstance(response, HTMLResponse), "Expected HTMLResponse type for each fetched URL"

    await asession.close()
