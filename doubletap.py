import asyncio
import random
import logging
from urllib.parse import urlparse, urljoin
from mitmproxy import ctx
from mitmproxy.script import concurrent
from mitmproxy.net.http import Headers
from doubletap.aws import AWSProxies
from doubletap.utils import USER_AGENTS, gen_random_ip, beautify_json

REGIONS = [
	"us-east-1","us-west-1","us-east-2",
	"us-west-2","eu-central-1","eu-west-1",
	"eu-west-2","eu-west-3","sa-east-1","eu-north-1"
]

class DoubleTap:
    def __init__(self):
        self.proxies = AWSProxies(regions=REGIONS)

    def load(self, entry):
        ctx.log.info("Starting DOUBLETAP, please wait...")
        asyncio.create_task(self.proxies.setup())

    async def redirect(self, flow, proxy_urls):
        proxy_url = random.choice(proxy_urls)
        ctx.log.info(f"Redirecting request to {proxy_url}")

        flow.request.url = proxy_url if flow.request.path == '/' else urljoin(proxy_url, flow.request.path[1:])
        flow.request.host = urlparse(proxy_url).netloc
        flow.request.headers['User-Agent'] = random.choice(USER_AGENTS)
        flow.request.headers['X-My-X-Forwarded-For'] = gen_random_ip()

        flow.resume()

    async def proxy_request(self, flow):
        proxy_urls = await self.proxies.create(f"{flow.request.scheme}://{flow.request.host}/")
        await self.redirect(flow, proxy_urls)

    def request(self, flow):
        ctx.log.info(f"Processing URL: {flow.request.url}")
        flow.intercept()
        asyncio.create_task(self.proxy_request(flow))

    @concurrent
    def response(self, flow):
        remapped_headers = {}
        for k,v in flow.response.headers.items():
            header = k
            if k.lower().startswith('x-amzn-remapped'):
                #header = '-'.join(map(lambda x: x.title(), k.split('-',3)[-1].split('-')))
                header = k.split('-',3)[-1]

            remapped_headers[header.encode()] = v.encode()

        #ctx.log.debug(beautify_json(remapped_headers))
        flow.response.headers = Headers(remapped_headers.items())

    def done(self):
        ctx.log.info("DOUBLETAP exiting...")

addons = [
    DoubleTap()
]
