import pytest
from requests_html import HTMLSession, AsyncHTMLSession, HTMLResponse

# List of URLs to test
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
    """Fixture for synchronous HTMLSession."""
    session = HTMLSession()
    yield session
    session.close()


@pytest.fixture(scope='module')
async def async_html_session():
    """Fixture for asynchronous HTMLSession."""
    session = AsyncHTMLSession()
    yield session
    await session.close()


@pytest.mark.parametrize('url', urls)
@pytest.mark.internet
def test_pagination(html_session, url: str):
    """Test pagination for synchronous HTML requests."""
    r = html_session.get(url)
    assert r.html, f"Failed to retrieve HTML content for {url}"
    assert r.status_code == 200, f"Expected status code 200, got {r.status_code} for {url}"


@pytest.mark.parametrize('url', urls)
@pytest.mark.internet
@pytest.mark.asyncio
async def test_async_pagination(async_html_session, url: str):
    """Test pagination for asynchronous HTML requests."""
    r = await async_html_session.get(url)
    # Check that the HTML response was successfully parsed
    assert r.html.find('html'), f"Failed to retrieve or parse HTML content for {url}"


@pytest.mark.internet
@pytest.mark.asyncio
async def test_async_run(async_html_session):
    """Test concurrent fetching of multiple URLs asynchronously."""
    async def fetch_url(url):
        return await async_html_session.get(url)

    # Create a list of tasks for fetching URLs concurrently
    async_list = [fetch_url(url) for url in urls]
    responses = await async_html_session.run(*async_list)

    # Ensure the number of responses matches the number of URLs
    assert len(responses) == len(urls), "Number of responses does not match the number of URLs"

    # Check each response's type and status
    for url, response in zip(urls, responses):
        assert isinstance(response, HTMLResponse), f"Expected HTMLResponse for {url}, got {type(response)}"
        assert response.status_code == 200, f"Expected status code 200 for {url}, got {response.status_code}"

