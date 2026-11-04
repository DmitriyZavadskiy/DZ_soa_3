import grpc


class AuthInterceptor(grpc.aio.ServerInterceptor):
    def __init__(self, key: str):
        self.key = key

    async def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        if metadata.get("x-api-key") != self.key:
            return grpc.unary_unary_rpc_method_handler(self.deny)
        return await continuation(handler_call_details)

    async def deny(self, request, context):
        await context.abort(grpc.StatusCode.UNAUTHENTICATED, "missing or invalid x-api-key")
