import asyncio
import random
import aiohttp
from urllib.parse import urlparse, urljoin
from mitmproxy.script import concurrent
#from mitmproxy.http import HTTPResponse
from mitmproxy.net.http import Headers
from doubletap.aws import AWSApiGatewayProxy
from doubletap.utils import USER_AGENTS, gen_random_ip, gen_random_string, beutify_json


class DoubleTap:
    def __init__(self):
        #self.loop = asyncio.get_event_loop()
        self.api = AWSApiGatewayProxy("AWSProxier")
        self.tasks = {}

        self._aiohttp_session = None
        #self.log = logging.getLogger("AWSProxier")
        #self.log.setLevel(logging.DEBUG)

    async def create_aiohttp_client_session(self):
        print("Creating client session...")
        connector = aiohttp.TCPConnector(ssl=False)
        self._aiohttp_session = aiohttp.ClientSession(
            connector=connector,
            cookie_jar=aiohttp.DummyCookieJar()
        )

    def load(self, entry):
        asyncio.create_task(self.create_aiohttp_client_session())

    """
    async def create_response(self, flow):
        print("Sending request on behalf of client")
        while not self.api.proxies.get(flow.request.host):
            print("API not staged")
            await asyncio.sleep(0.1)

        proxy_url = self.api.proxies[flow.request.host]
        url = proxy_url if flow.request.path == '/' else urljoin(proxy_url, flow.request.path[1:])
        
        if flow.request.http_version.startswith("HTTP/2"):
            request_headers = dict(flow.request.headers)
            request_headers[":authority"] = urlparse(proxy_url).netloc
            request_headers['user-agent'] = random.choice(USER_AGENTS)
            request_headers['x-my-x-forwarded-for'] = gen_random_ip()
            request_headers['host'] = urlparse(proxy_url).netloc
        else:
            request_headers = dict(flow.request.headers)
            request_headers['User-Agent'] = random.choice(USER_AGENTS)
            request_headers['X-My-X-Forwarded-For'] = gen_random_ip()
            request_headers['Host'] = urlparse(proxy_url).netloc

        print(beutify_json(request_headers))

        async with self._aiohttp_session.request(
            method=flow.request.method,
            url=url,
            data=flow.request.raw_content,
            headers=request_headers,
            allow_redirects=False,
        ) as resp:
            print(f"Generating response...")
            crafted_http_resp = HTTPResponse.make(
                status_code=resp.status,
                content=await resp.read(),
                headers=dict(resp.headers)
            )

            flow.response = crafted_http_resp
            flow.resume()
    """

    async def check_if_staged(self, url):
        print("Checking if API has staged")
        while True:
            async with self._aiohttp_session.get(url) as r:
                try:
                    data = await r.json()
                    if (r.status == 403 and data['message'] == 'Forbidden') or (r.status == 403 and data['message'] == 'Missing Authentication Token'):
                        await asyncio.sleep(0.1)
                        continue
                except Exception as e:
                    pass
                    #print(f"Error when checking if API staged: {e}")

                print("API Staged")
                return True

    async def redirect(self, flow):
        print("Redirecting")

        while not self.api.proxies.get(flow.request.host):
            print("API not staged")
            await asyncio.sleep(0.1)

        proxy_url = self.api.proxies[flow.request.host]

        flow.request.url = proxy_url if flow.request.path == '/' else urljoin(proxy_url, flow.request.path[1:])
        flow.request.host = urlparse(proxy_url).netloc
        flow.request.headers['User-Agent'] = random.choice(USER_AGENTS)
        flow.request.headers['X-My-X-Forwarded-For'] = gen_random_ip()

        flow.resume()

    async def create_proxy_endpoint(self, flow):
        proxy_url = await self.api.create(f"{flow.request.scheme}://{flow.request.host}/", gen_random_string())
        await self.api.stage()
        await self.check_if_staged(proxy_url)
        self.api.proxies[flow.request.host] = proxy_url

    def request(self, flow):
        print(f"Processing URL: {flow.request.url}")

        flow.intercept()
        if (flow.request.host not in self.api.proxies) and (flow.request.host not in self.tasks):
            self.tasks[flow.request.host] = asyncio.create_task(self.create_proxy_endpoint(flow))
        asyncio.create_task(self.redirect(flow))
        #asyncio.create_task(self.create_response(flow))

    @concurrent
    def response(self, flow):
        remapped_headers = {}
        for k,v in flow.response.headers.items():
            header = k
            if k.lower().startswith('x-amzn-remapped'):
                #header = '-'.join(map(lambda x: x.title(), k.split('-',3)[-1].split('-')))
                header = k.split('-',3)[-1]

            remapped_headers[header.encode()] = v.encode()

        #print(beutify_json(remapped_headers))
        flow.response.headers = Headers(remapped_headers.items())

    """
    def done(self):
        if self._aiohttp_session:
            task = asyncio.create_task(self._aiohttp_session.close())
            while not task.done():
                time.sleep(0.1)
        self.api.unstage()
        self.api.destroy()
    """

addons = [
    DoubleTap()
]
