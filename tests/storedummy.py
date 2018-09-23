from manta.store import Store
from aiohttp import web
import traceback
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)
routes = web.RouteTableDef()
store = Store('dummy_store')


@routes.post("/merchant_order")
async def merchant_order(request: web.Request):
    try:
        json = await request.json()
        logger.info("New http requets: %s" % json)
        json['amount'] = Decimal(json['amount'])

        reply = await store.merchant_order_request(**json)


        return web.Response(body=reply.to_json(), content_type="application/json")

    except Exception:
        traceback.print_exc()
        raise web.HTTPInternalServerError()


logging.basicConfig(level=logging.INFO)
app = web.Application()
app.add_routes(routes)
web.run_app(app, port=8080)
