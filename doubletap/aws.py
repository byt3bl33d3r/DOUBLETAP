import os
import asyncio
import logging
import aiobotocore
import httpx
import random
import pathlib
import json
from contextlib import AsyncExitStack
from configparser import ConfigParser
from botocore.exceptions import ClientError
from doubletap.utils import gen_random_ip, gen_random_string, beautify_json

log = logging.getLogger("doubletap.aws")

class AWSProxierError(Exception):
    pass

class AWSApiResponse:
    def __init__(self, api_response):
        self.raw = api_response
        self.metadata = self.raw['ResponseMetadata']
        self.response = self.raw['items'] if "items" in self.raw else {k: self.raw[k] for k in self.raw if k != "ResponseMetadata"}

def apiresponse(func):
    async def wrapper(*args, **kwargs):
        return AWSApiResponse( await func(*args, **kwargs) ).response
    return wrapper

class AWSApiGateway:
    def __init__(self, name, region='us-east-2'):
        self.id = None
        self.name = name
        self.region = region
        self._exit_stack = AsyncExitStack()
        self.client = None
        self.log = logging.getLogger(f"doubletap.aws.apigateway.{region}")

        self.aws_access_key, self.aws_secret_key = self.get_credentials()

        #self.region = boto3.session.Session().region_name

    def get_credentials(self):
        self.log.debug("Checking for AWS credentials in environment variables")
        aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')

        if not aws_access_key or not aws_secret_key:
            aws_credentials_path = pathlib.Path('~/.aws/credentials').expanduser()
            if aws_credentials_path.exists():
                self.log.debug("Checking for AWS credentials in ~/.aws/credentials")

                aws_credentials_file = ConfigParser()
                aws_credentials_file.read(
                    aws_credentials_path
                )

                if not aws_access_key:
                    aws_access_key = aws_credentials_file.get('default', 'aws_access_key_id')

                if not aws_secret_key:
                    aws_secret_key = aws_credentials_file.get('default', 'aws_secret_access_key')

        return aws_access_key, aws_secret_key

    async def get_id(self):
        if not self.id:
            api = await self.create()
            self.id = api['id']
        return self.id

    async def create(self):
        api = await self.get_by_name(self.name)
        return api if api else await self.client.create_rest_api(name=self.name)

    async def get_resource_by_path(self, path):
        r = await self.get_resources()
        try:
            return list(filter(lambda r: True if r["path"] == path else False, r))[0]
        except IndexError:
            return None

    async def get_resource_by_pathpart(self, pathpart):
        r = await self.get_resources()
        try:
            return list(filter(lambda r: True if "pathPart" in r and r["pathPart"] == pathpart else False, r))[0]
        except IndexError:
            return None

    async def get_by_name(self, name):
        for api in await self.get():
            if api['name'] == name:
                return api

    @apiresponse
    async def get(self):
        return await self.client.get_rest_apis()

    @apiresponse
    async def get_resources(self):
        return await self.client.get_resources(restApiId=self.id)

    @apiresponse
    async def get_deployments(self):
        return await self.client.get_deployments(restApiId=self.id)

    @apiresponse
    async def get_stages(self):
        return await self.client.get_stages(restApiId=self.id)

    @apiresponse
    async def get_integration(self, resource_id, http_method):
        return await self.client.get_integration(
            restApiId=self.id,
            resourceId=resource_id,
            httpMethod=http_method
        )

    @apiresponse
    async def create_resource(self, parent_id, path_part):
        return await self.client.create_resource(
            restApiId=self.id,
            parentId=parent_id,
            pathPart=path_part,
        )

    @apiresponse
    async def create_method(self, resource_id, http_method, request_params={}):
        return await self.client.put_method(
            restApiId=self.id,
            resourceId=resource_id,
            httpMethod=http_method,
            authorizationType="NONE",
            apiKeyRequired=False,
            requestParameters=request_params
        )

    @apiresponse
    async def create_integration(self, resource_id, http_method, type, uri, passthrough_behavior="WHEN_NO_MATCH", request_params={}, cache_key_params=[]):
        return await self.client.put_integration(
            restApiId=self.id,
            resourceId=resource_id,
            httpMethod=http_method,
            integrationHttpMethod=http_method,
            passthroughBehavior=passthrough_behavior,
            type=type,
            uri=uri,
            requestParameters=request_params,
            cacheKeyParameters=cache_key_params
        )

    @apiresponse
    async def create_integration_response(self, resource_id, http_method, status_code, response_tmpls={}):
        return await self.client.put_integration_response(
            restApiId=self.id,
            resourceId=resource_id,
            httpMethod=http_method,
            statusCode=str(status_code),
            responseTemplates=response_tmpls
        )

    @apiresponse
    async def create_method_response(self, resource_id, http_method, status_code):
        return await self.client.put_method_response(
            restApiId=self.id,
            resourceId=resource_id,
            httpMethod=http_method,
            statusCode=str(status_code)
        )

    @apiresponse
    async def create_deployment(self, name, description=''):
        return await self.client.create_deployment(
            restApiId=self.id,
            stageName=name,
            stageDescription=description,
            description=description
        )

    @apiresponse
    async def create_stage(self, deployment_id, stage_name, description=''):
        return await self.client.create_stage(
            restApiId=self.id,
            deploymentId=deployment_id,
            stageName=stage_name,
            description=description
        )

    @apiresponse
    async def delete_stage(self, stage_name):
        return await self.client.delete_stage(
            restApiId=self.id,
            stageName=stage_name
        )

    @apiresponse
    async def delete_resource(self, resource_id):
        return await self.client.delete_resource(
            restApiId=self.id,
            resourceId=resource_id
        )

    @apiresponse
    async def delete_api(self):
        return await self.client.delete_rest_api(
            restApiId=self.id,
        )

    async def __aenter__(self):
        session = aiobotocore.session.AioSession()
        self.client = await self._exit_stack.enter_async_context(
                session.create_client(
                'apigateway',
                region_name=self.region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key
            )
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)


class AWSApiGatewayProxy:
    def __init__(self, name, region="us-east-2"):
        self.name = name
        self.region = region
        self.proxies = {}
        self.apigw = AWSApiGateway(name, region=region)
        self.log = logging.getLogger(f"doubletap.aws.apigatewayproxy.{region}")

    async def create(self, url, endpoint):
        async with self.apigw as apigw_client:
            await apigw_client.get_id()

            self.log.debug(f"{self.name} API id: {self.apigw.id}")

            root_path_resource = await apigw_client.get_resource_by_path("/")
            root_path_resource_id = root_path_resource['id']
            try:
                main_resource = await apigw_client.create_resource(root_path_resource_id, endpoint)
                main_resource_id = main_resource['id']
            except ClientError as e:
                self.log.error(f"botocore.exceptions.ClientError: {e}")
                if 'ConflictException' in e.args[0]:
                    self.log.warning("resource conflict detected, attempting overwrite")
                    await self.delete(endpoint)
                    return await self.create(url, endpoint)
                self.log.error(f"unhandled botocore.exceptions.ClientError: {e}")
            else:
                self.log.debug(f"attempting to create proxy to {url} => endpoint: {endpoint}")

                # you don't even want to know how long it took me to figure out that you need to pass "method.request.path.proxy" to put_method first
                # *before* calling put_integration with that value in the request_params. where dafuq are the docs on this???
                await apigw_client.create_method(
                    resource_id=main_resource_id,
                    http_method="GET",
                    request_params={
                        "method.request.path.proxy": True,
                        "method.request.header.X-My-X-Forwarded-For": False
                        #"method.request.header.X-My-X-Amzn-Apigateway-Api-Id": False
                    }
                )

                await apigw_client.create_integration(
                    resource_id=main_resource_id,
                    http_method="GET",
                    type="HTTP_PROXY",
                    uri=url,
                    request_params={
                        "integration.request.path.proxy": "method.request.path.proxy",
                        "integration.request.header.X-Forwarded-For": "method.request.header.X-My-X-Forwarded-For"
                        #"integration.request.header.X-Amzn-Apigateway-Api-Id": "method.request.header.X-My-X-Amzn-Apigateway-Api-Id"
                    },
                    cache_key_params=["method.request.path.proxy"]
                )

                await apigw_client.create_method(
                    resource_id=main_resource_id,
                    http_method="POST",
                    request_params={
                        "method.request.path.proxy": True,
                        "method.request.header.X-My-X-Forwarded-For": False
                        #"method.request.header.X-My-X-Amzn-Apigateway-Api-Id": False
                    }
                )

                await apigw_client.create_integration(
                    resource_id=main_resource_id,
                    http_method="POST",
                    type="HTTP_PROXY",
                    uri=url,
                    request_params={
                        "integration.request.path.proxy": "method.request.path.proxy",
                        "integration.request.header.X-Forwarded-For": "method.request.header.X-My-X-Forwarded-For"
                        #"integration.request.header.X-Amzn-Apigateway-Api-Id": "method.request.header.X-My-X-Amzn-Apigateway-Api-Id"
                    },
                    cache_key_params=["method.request.path.proxy"]
                )

                proxy_resource = await apigw_client.create_resource(main_resource_id, "{proxy+}")
                proxy_resource_id = proxy_resource['id']
                await apigw_client.create_method(
                    resource_id=proxy_resource_id,
                    http_method="ANY",
                    request_params={
                        "method.request.path.proxy": True,
                        "method.request.header.X-My-X-Forwarded-For": False
                        #"method.request.header.X-My-X-Amzn-Apigateway-Api-Id": False
                    }
                )

                await apigw_client.create_integration(
                    resource_id=proxy_resource_id,
                    http_method="ANY",
                    type="HTTP_PROXY",
                    uri=url + "{proxy}" if "{proxy}" not in url else url,
                    request_params={
                        "integration.request.path.proxy": "method.request.path.proxy",
                        "integration.request.header.X-Forwarded-For": "method.request.header.X-My-X-Forwarded-For"
                        #"integration.request.header.X-Amzn-Apigateway-Api-Id": "method.request.header.X-My-X-Amzn-Apigateway-Api-Id"
                    },
                    cache_key_params=["method.request.path.proxy"]
                )

                proxy_url = f"https://{self.apigw.id}.execute-api.{self.apigw.region}.amazonaws.com/{self.name}/{endpoint}/"
                self.proxies[url] = proxy_url
                return proxy_url

    async def stage(self):
        self.log.debug("staging API")
        async with self.apigw as apigw_client:
            await apigw_client.create_deployment(self.name)
            #apigw_client.create_stage(deployment_id, self.name)

    async def get(self):
        self.log.debug("retrieving available proxies")
        async with self.apigw as apigw_client:
            await apigw_client.get_id()

            for resource in await apigw_client.get_resources():
                try:
                    integration = await apigw_client.get_integration(resource["id"], "GET")
                    url = integration["uri"]
                except:
                    continue
                self.proxies[url] = f"https://{self.apigw.id}.execute-api.{self.apigw.region}.amazonaws.com/{self.name}/{resource['pathPart']}/"

            if self.proxies:
                self.log.debug(f"retrieved already staged proxies: {beautify_json(self.proxies)}")

            return self.proxies

    async def delete(self, endpoint):
        async with self.apigw as apigw_client:
            resource = await apigw_client.get_resource_by_pathpart(endpoint)
            resource_id = resource["id"]
            await apigw_client.delete_resource(resource_id)

    async def unstage(self):
        async with self.apigw as apigw_client:
            await apigw_client.get_id()
            await apigw_client.delete_stage(self.name)

    async def destroy(self):
        async with self.apigw as apigw_client:
            await apigw_client.get_id()
            await apigw_client.delete_api()

    def __getitem__(self, value):
        return self.proxies.get(value)

class AWSProxies:
    def __init__(self, regions, name="DOUBLETAP"):
        self.name = name
        self.regions = regions
        self.proxies = [AWSApiGatewayProxy(name, region=region) for region in regions]
        self._httpx_client = httpx.AsyncClient(verify=False)

    async def setup(self):
        return await asyncio.gather(*[proxy.get() for proxy in self.proxies])

    async def cleanup(self):
        log.debug("cleaning up")
        await asyncio.gather(*[proxy.unstage() for proxy in self.proxies])
        await asyncio.gather(*[proxy.destroy() for proxy in self.proxies])
 
    async def create(self, url):
        proxy_urls = [proxy[url] for proxy in self.proxies]
        if all(proxy_urls):
            return proxy_urls

        log.debug(f"creating proxy endpoints for {url}")

        proxy_urls = await asyncio.gather(*[proxy.create(url, gen_random_string()) for proxy in self.proxies])
        await asyncio.gather(*[proxy.stage() for proxy in self.proxies])
        await asyncio.gather(*[self.check_if_staged(url) for url in proxy_urls])

        return proxy_urls

    async def check_if_staged(self, url):
        log.debug(f"checking if API has staged ({url})")
        while True:
            r = await self._httpx_client.get(url)
            if r.status_code != 403 and not r.headers.get("x-amzn-ErrorType"):
                log.debug("API seems to have staged, reason: response status code was not 403 or 'x-amzn-ErrorType' header not present")
                return True

            try:
                data = r.json()
                if data['message'] in ['Forbidden', 'Missing Authentication Token']:
                    await asyncio.sleep(0.1)
                    continue
            except json.JSONDecodeError:
                log.debug("API seems to have staged, reason: response failed to decode to JSON")
                return True
            except IndexError:
                log.debug("API seems to have staged, reason: returned JSON doesn't have 'message' key")
                return True

    async def get(self, url):
        proxy = random.choice(self.proxies)
        return proxy[url]
