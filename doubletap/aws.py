import asyncio
import aiobotocore
import random
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from doubletap.utils import gen_random_ip, gen_random_string, beutify_json


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

        session = aiobotocore.get_session()
        self.client = session.create_client('apigateway', region_name=region)
        #self.region = boto3.session.Session().region_name

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

class AWSApiGatewayProxy:
    def __init__(self, name, region="us-east-2"):
        self.name = name
        self.api = AWSApiGateway(name, region=region)
        self.proxies = {}

        #self.log = logging.getLogger("AWSApiGatewayProxy")
        #self.log.setLevel(logging.DEBUG)

        asyncio.create_task(self.list())

    async def create(self, url, endpoint):
        await self.api.get_id()
        print(f"{self.name} API id: {self.api.id}")
        
        root_path_resource = await self.api.get_resource_by_path("/")
        root_path_resource_id = root_path_resource['id']
        try:
            main_resource = await self.api.create_resource(root_path_resource_id, endpoint)
            main_resource_id = main_resource['id']
        except ClientError as e:
            print(f"botocore.exceptions.ClientError: {e}")
            if 'ConflictException' in e.args[0]:
                print("Resource conflict detected, attempting overwrite")
                await self.delete(endpoint)
                return await self.create(url, endpoint)
            print(f"Unhandled botocore.exceptions.ClientError: {e}")
        else:
            print(f"Attempting to create proxy to {url} => endpoint: {endpoint}")

            # you don't even want to know how long it took me to figure out that you need to pass "method.request.path.proxy" to put_method first
            # *before* calling put_integration with that value in the request_params. where dafuq are the docs on this???
            await self.api.create_method(
                resource_id=main_resource_id,
                http_method="GET",
                request_params={
                    "method.request.path.proxy": True,
                    "method.request.header.X-My-X-Forwarded-For": False
                    #"method.request.header.X-My-X-Amzn-Apigateway-Api-Id": False
                }
            )

            await self.api.create_integration(
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

            await self.api.create_method(
                resource_id=main_resource_id,
                http_method="POST",
                request_params={
                    "method.request.path.proxy": True,
                    "method.request.header.X-My-X-Forwarded-For": False
                    #"method.request.header.X-My-X-Amzn-Apigateway-Api-Id": False
                }
            )

            await self.api.create_integration(
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

            proxy_resource = await self.api.create_resource(main_resource_id, "{proxy+}")
            proxy_resource_id = proxy_resource['id']
            await self.api.create_method(
                resource_id=proxy_resource_id,
                http_method="ANY",
                request_params={
                    "method.request.path.proxy": True,
                    "method.request.header.X-My-X-Forwarded-For": False
                    #"method.request.header.X-My-X-Amzn-Apigateway-Api-Id": False
                }
            )

            await self.api.create_integration(
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

            return f"https://{self.api.id}.execute-api.{self.api.region}.amazonaws.com/{self.name}/{endpoint}/"

    async def stage(self):
        print("Staging API")
        await self.api.create_deployment(self.name)
        #self.api.create_stage(deployment_id, self.name)

    async def list(self):
        await self.api.get_id()

        proxies = {}
        for resource in await self.api.get_resources():
            try:
                integration = await self.api.get_integration(resource["id"], "GET")
                url = integration["uri"]
            except:
                continue
            proxies[urlparse(url).netloc] = f"https://{self.api.id}.execute-api.{self.api.region}.amazonaws.com/{self.name}/{resource['pathPart']}/"

        self.proxies = proxies
        print(f"Retrieved already staged proxies: {beutify_json(proxies)}")
        return proxies

    async def delete(self, endpoint):
        resource = await self.api.get_resource_by_pathpart(endpoint)
        resource_id = resource["id"]
        await self.api.delete_resource(resource_id)

    async def unstage(self):
        await self.api.get_id()
        await self.api.delete_stage(self.name)

    async def destroy(self):
        await self.api.get_id()
        await self.api.delete_api()
