import traceback


class JSONRPC:
    """
    Base JSON-RPC class. Add methods to self.exposed_rpc
    to make it available with jsonrpc() call.
    """
    def __init__(self):
        self.exposed_rpc = {}

    def jsonrpc(self, request):
        """Processes json-rpc request"""
        # if it is a list (not bundled) run one by one
        if isinstance(request, list):
            responses = []
            for req in request:
                responses.append(self.jsonrpc(req))
            return responses
        if "id" not in request:
            request["id"] = None
        response = { "jsonrpc": "2.0", "id": request["id"] }
        if "method" not in request:
            response["error"] = { "code": -32600, "message": "Invalid Request. Request must specify a 'method'." }
            return response
        if request["method"] not in self.exposed_rpc:
            response["error"] = { "code": -32601, "message": "Method not found" }
            return response
        method = self.exposed_rpc[request["method"]]
        try:
            if "params" not in request:
                response["result"] = method()
            elif isinstance(request["params"], list):
                response["result"] = method(*request["params"]) # list -> *args
            else:
                response["result"] = method(**request["params"]) # dict -> **kwargs
        except Exception as e:
            traceback.print_exc()
            response["error"] = { "code": -32000, "message": f"Internal error: {e}" }
        return response
